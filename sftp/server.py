import errno
import functools
import logging
import os
import socket
import threading
from django.utils import timezone
from django.contrib.auth import authenticate
import paramiko
from paramiko import SFTPServer, SFTPServerInterface
from paramiko.sftp import SFTP_OK, SFTP_OP_UNSUPPORTED
from paramiko.common import o666
from bioshareX.models import Share
from paramiko.sftp_handle import SFTPHandle
from bioshareX.utils import paths_contain
from django.conf import settings

SFTP_UPDATE_SHARE_MODIFIED_DATE_FREQUENCY_SECONDS = getattr(settings, 'SFTP_UPDATE_SHARE_MODIFIED_DATE_FREQUENCY_SECONDS',60)

class BioshareSFTPServer(object):
    """
    Create an SFTP server which serves the files in `root` and authenticates
    itself with the supplied `host key` file.

    `serve_forver` starts the server listening on the supplied host and port
    and handles each connection in a new thread.

    A `get_user` method must be supplied. This should accept a username and
    password and return either a User object or None if the credentials are
    invalid.

    A User object should implement two methods: `has_read_access` and
    `has_write_access`.  Each method should accept a path (relative to `root`)
    and return True or False appropriately. Users should also have a sensible
    `__str__` representation for use in logging.
    """

    SOCKET_BACKLOG = 10

    def __init__(self, host_key_path, get_user=None):
        self.host_key = paramiko.RSAKey.from_private_key_file(host_key_path)
        if get_user is not None:
            self.get_user = get_user

    def serve_forever(self, host, port):
        server_socket = socket.socket()
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        server_socket.bind((host, port))
        server_socket.listen(self.SOCKET_BACKLOG)
        while True:
            conn = server_socket.accept()[0]
            self.start_sftp_session(conn)

    def start_sftp_session(self, conn):
        transport = paramiko.Transport(conn)
        transport.add_server_key(self.host_key)
        transport.set_subsystem_handler(
            'sftp', SFTPServer, SFTPInterface)
        # The SFTP session runs in a separate thread. We pass in `event`
        # so `start_server` doesn't block; we're not actually interested
        # in waiting for the event though.
        transport.start_server(
                server=SSHInterface(self.get_user),
                event=threading.Event())

    def get_user(self, username, password):
        return authenticate(username=username, password=password)
#         raise NotImplementedError()


class SSHInterface(paramiko.ServerInterface):

    def __init__(self, get_user):
        self.get_user = get_user
    
    def check_auth_password(self, username, password):
        user =  authenticate(username=username, password=password)
        if user:
            logging.info((u'Auth successful for %s' % username).encode('utf-8'))
            self.user = user
            return paramiko.AUTH_SUCCESSFUL
        else:
            logging.info((u'Auth failed for %s' % username).encode('utf-8'))
            return paramiko.AUTH_FAILED

    def check_channel_request(self, kind, chanid):
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        else:
            return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

class PermissionDenied(Exception):
    pass

def sftp_response(fn):
    """
    Decorator which converts exceptions into appropriate SFTP error codes,
    returns OK for functions which don't have a return value
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            value = fn(*args, **kwargs)
        except (OSError, IOError) as e:
            return SFTPServer.convert_errno(e.errno)
        except PermissionDenied:
            return paramiko.SFTP_PERMISSION_DENIED
        if value is None:
            return paramiko.SFTP_OK
        else:
            return value
    return wrapper


class permissions_required(object):

    def __init__(self, permissions=[],path_arg_ind=1,operator='AND'):
        self.permissions = permissions
        self.path_arg_index = path_arg_ind
        self.operator = operator
    def __call__(self, f):
        def wrapped_f(*args,**kwargs):
            interface = args[0]
            path = args[self.path_arg_index]
            if path == '/':
                return f(*args,**kwargs)
            permissions = interface._get_bioshare_path_permissions(path)
            perm_num = len(set(permissions).intersection(set(self.permissions)))
            if self.operator == 'OR' and perm_num == 0 or self.operator == 'AND' and len(self.permissions) != perm_num: 
                raise PermissionDenied()
            return f(*args,**kwargs)
        return wrapped_f

def log_event(method):
    """
    Decorator which logs SFTP events along with the current user
    """
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        string_args = u':'.join([arg for arg in args if isinstance(arg, basestring)])
        msg = u'%s:%%s:%s:%s' % (method.__name__, self.user, string_args)
        try:
            response = method(self, *args, **kwargs)
        except Exception:
            logging.info((msg % 'error').encode('utf-8'))
            raise
        else:
            logging.info((msg % 'ok').encode('utf-8'))
        return response
    return wrapper

def _SFTPHandle_stat(self):
    try:
        return paramiko.SFTPAttributes.from_stat(os.fstat(self.readfile.fileno()))
    except OSError as e:
        return SFTPServer.convert_errno(e.errno)

def _SFTPHandle_chattr(self, attr):
    # python doesn't have equivalents to fchown or fchmod, so we have to
    # use the stored filename
    try:
        SFTPServer.set_file_attr(self.filename, attr)
        return SFTP_OK
    except OSError as e:
        return SFTPServer.convert_errno(e.errno)

def _SFTPHandle_write(self, offset, data):
    #Custom Auth
    if Share.PERMISSION_WRITE not in self.permissions:
        print 'permission denied'
        raise PermissionDenied()
    #Below this is implementation from SFTPHandle
    writefile = getattr(self, 'writefile', None)
    if writefile is None:
        return SFTP_OP_UNSUPPORTED
    try:
        # in append mode, don't care about seeking
        if (self.__flags & os.O_APPEND) == 0:
            if self.__tell is None:
                self.__tell = writefile.tell()
            if offset != self.__tell:
                writefile.seek(offset)
                self.__tell = offset
        writefile.write(data)
        writefile.flush()
    except IOError as e:
        self.__tell = None
        return SFTPServer.convert_errno(e.errno)
    if self.__tell is not None:
        self.__tell += len(data)
    return SFTP_OK
def _SFTPHandle_read(self, offset, length):
    """
    Read up to ``length`` bytes from this file, starting at position
    ``offset``.  The offset may be a Python long, since SFTP allows it
    to be 64 bits.

    If the end of the file has been reached, this method may return an
    empty string to signify EOF, or it may also return `.SFTP_EOF`.

    The default implementation checks for an attribute on ``self`` named
    ``readfile``, and if present, performs the read operation on the Python
    file-like object found there.  (This is meant as a time saver for the
    common case where you are wrapping a Python file object.)

    :param offset: position in the file to start reading from.
    :type offset: int or long
    :param int length: number of bytes to attempt to read.
    :return: data read from the file, or an SFTP error code, as a `str`.
    """
    if Share.PERMISSION_VIEW not in self.permissions:
        print 'permission denied'
        raise PermissionDenied()
    readfile = getattr(self, 'readfile', None)
    if readfile is None:
        return SFTP_OP_UNSUPPORTED
    try:
        if self.__tell is None:
            self.__tell = readfile.tell()
        if offset != self.__tell:
            readfile.seek(offset)
            self.__tell = offset
        data = readfile.read(length)
    except IOError as e:
        self.__tell = None
        return SFTPServer.convert_errno(e.errno)
    self.__tell += len(data)
    return data

def _SFTPHandle___init__(self, flags=0,permissions=[]):
    self.permissions = permissions
    #Below this is implementation from SFTPHandle
    self.__flags = flags
    self.__name = None
    # only for handles to folders:
    self.__files = {}
    self.__tell = None
    
SFTPHandle.__init__ = _SFTPHandle___init__
SFTPHandle.stat = _SFTPHandle_stat
SFTPHandle.chattr = _SFTPHandle_chattr
SFTPHandle.write = _SFTPHandle_write
SFTPHandle.read = _SFTPHandle_read

class SFTPInterface (SFTPServerInterface):
    def __init__(self, server):
        self.server = server
        self.user = server.user
        self.shares = {}
        self.modified_date = {}
        for share in Share.user_queryset(self.user,include_stats=False):
            self.shares[share.slug_or_id] = share#{'path':share.get_realpath()}
#         print 'user'
#         print self.user
#         self.ROOT = root
    def _get_share(self,path):
        parts = path.split(os.path.sep)
        if len(parts) < 2:
            print 'bad length'
            raise PermissionDenied("Received an invalid path: %s"%path) 
        if not self.shares.has_key(parts[1]):
            print 'no share exists'
            print path
            raise PermissionDenied("Share does not exist: %s"%path[1])
        return self.shares[parts[1]]
    def _path_modified(self,path):
        share = self._get_share(path)
        previous_date = self.modified_date.get(share.id,None)
        current_date = timezone.now()
        if not previous_date or (current_date-previous_date).seconds > SFTP_UPDATE_SHARE_MODIFIED_DATE_FREQUENCY_SECONDS:
            self.modified_date[share.id] = current_date
            Share.objects.filter(id=share.id,updated__lt=current_date).update(updated=current_date) 
    def _get_bioshare_path_permissions(self,path):
        share = self._get_share(path)
        permissions = share.get_user_permissions(self.user)
#         print permissions
        return permissions
    def _get_path_permissions(self,path):
        permissions = self._get_bioshare_path_permissions(path)
        #translate
#         PERMISSION_VIEW = 'view_share_files'
#         PERMISSION_DELETE = 'delete_share_files'
#         PERMISSION_DOWNLOAD = 'download_share_files'
#         PERMISSION_WRITE = 'write_to_share'
#         PERMISSION_LINK_TO_PATH = 'link_to_path'
#         PERMISSION_ADMIN
        return permissions
    def _realpath(self, path):
#         print 'realpath'
#         print path
        parts = path.split(os.path.sep)
        share = self._get_share(path)
        realpath = os.path.realpath(os.path.join(share.get_realpath(),os.path.sep.join(parts[2:])))
        if not paths_contain(settings.DIRECTORY_WHITELIST,realpath):
            raise PermissionDenied("Encountered a path outside the whitelist")
        return realpath
#         print self.ROOT + self.canonicalize(path)
#         return self.ROOT + self.canonicalize(path)
    @sftp_response
    def list_shares(self):
#         print "LIST SHARES"
        try:
            out = []
            for id,share in self.shares.iteritems():
                try:
#                     print id
                    attr = paramiko.SFTPAttributes.from_stat(os.stat(share.get_realpath()))
                    attr.filename = id
                    out.append(attr)
                except Exception, e:
                    pass #directory may be missing
            return out
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
    @sftp_response
    @permissions_required([Share.PERMISSION_VIEW])
    def list_folder(self, path):
        if path == '/':
            return self.list_shares()
        permissions = self._get_path_permissions(path)
        path = self._realpath(path)
        try:
            out = []
            flist = os.listdir(path)
            for fname in flist:
                try:
                    attr = paramiko.SFTPAttributes.from_stat(os.stat(os.path.join(path, fname)))
                    attr.filename = fname
                    out.append(attr)
                except Exception as e:
#                     @todo: Add the file to the list anyway.  It will fail on download.
                    print 'OSError with file: '+os.stat(os.path.join(path, fname))
                    print e
            return out
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

    @sftp_response
    @permissions_required([Share.PERMISSION_VIEW])
    def stat(self, path):
        path = self._realpath(path)
        try:
            return paramiko.SFTPAttributes.from_stat(os.stat(path))
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
    @sftp_response
    @permissions_required([Share.PERMISSION_VIEW])
    def lstat(self, path):
        path = self._realpath(path)
        try:
            return paramiko.SFTPAttributes.from_stat(os.lstat(path))
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
    @sftp_response
    def open(self, path, flags, attr):
        permissions = self._get_bioshare_path_permissions(path)
        if Share.PERMISSION_VIEW not in permissions or (flags & os.O_CREAT or flags & os.O_WRONLY or flags & os.O_RDWR or flags & os.O_APPEND) and Share.PERMISSION_WRITE not in permissions:
#         if Share.PERMISSION_WRITE not in permissions:
            raise PermissionDenied()
        if flags & os.O_CREAT or flags & os.O_WRONLY or flags & os.O_RDWR or flags & os.O_APPEND:
            self._path_modified(path)
        path = self._realpath(path)
        try:
            binary_flag = getattr(os, 'O_BINARY', 0)
            flags |= binary_flag
            mode = getattr(attr, 'st_mode', None)
            if mode is not None:
                fd = os.open(path, flags, mode)
            else:
                # os.open() defaults to 0777 which is
                # an odd default mode for files
                fd = os.open(path, flags, o666)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        try:
            if (flags & os.O_CREAT) and (attr is not None):
                attr._flags &= ~attr.FLAG_PERMISSIONS
                SFTPServer.set_file_attr(path, attr)
            if flags & os.O_WRONLY:
                if flags & os.O_APPEND:
                    fstr = 'ab'
                else:
                    fstr = 'wb'
            elif flags & os.O_RDWR:
                if flags & os.O_APPEND:
                    fstr = 'a+b'
                else:
                    fstr = 'r+b'
            else:
                # O_RDONLY (== 0)
                fstr = 'rb'
        except Exception as e:
            print e.message
        try:
            f = os.fdopen(fd, fstr)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        fobj = SFTPHandle(flags,permissions=permissions)
        fobj.filename = path
        fobj.readfile = f
        fobj.writefile = f
        return fobj
    @sftp_response
    @permissions_required([Share.PERMISSION_DELETE])
    def remove(self, path):
#         if not Share.PERMISSION_DELETE in self._get_bioshare_path_permissions(path):
#             return PermissionDenied()
        real_path = self._realpath(path)
        try:
            os.remove(real_path)
            self._path_modified(path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK
    @sftp_response
    @permissions_required([Share.PERMISSION_DELETE,Share.PERMISSION_WRITE])
    def rename(self, oldpath, newpath):
        oldpath = self._realpath(oldpath)
        newpath = self._realpath(newpath)
        try:
            os.rename(oldpath, newpath)
            self._path_modified(oldpath)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK
    @sftp_response
    @permissions_required([Share.PERMISSION_WRITE])
    def mkdir(self, path, attr):
        real_path = self._realpath(path)
        try:
            os.mkdir(real_path)
            self._path_modified(path)
            if attr is not None:
                SFTPServer.set_file_attr(real_path, attr)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK
    @sftp_response
    @permissions_required([Share.PERMISSION_DELETE])
    def rmdir(self, path):
        real_path = self._realpath(path)
        try:
            os.rmdir(real_path)
            self._path_modified(path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK
    @sftp_response
    def chattr(self, path, attr):
        return SFTP_OP_UNSUPPORTED
#         path = self._realpath(path)
#         try:
#             SFTPServer.set_file_attr(path, attr)
#         except OSError as e:
#             return SFTPServer.convert_errno(e.errno)
#         return SFTP_OK
    @sftp_response
    def symlink(self, target_path, path):
        return SFTP_OP_UNSUPPORTED
#         path = self._realpath(path)
#         if (len(target_path) > 0) and (target_path[0] == '/'):
#             # absolute symlink
#             target_path = os.path.join(self.ROOT, target_path[1:])
#             if target_path[:2] == '//':
#                 # bug in os.path.join
#                 target_path = target_path[1:]
#         else:
#             # compute relative to path
#             abspath = os.path.join(os.path.dirname(path), target_path)
#             if abspath[:len(self.ROOT)] != self.ROOT:
#                 # this symlink isn't going to work anyway -- just break it immediately
#                 target_path = '<error>'
#         try:
#             os.symlink(target_path, path)
#         except OSError as e:
#             return SFTPServer.convert_errno(e.errno)
#         return SFTP_OK
    @sftp_response
    def readlink(self, path):
        return SFTP_OP_UNSUPPORTED
#         path = self._realpath(path)
#         try:
#             symlink = os.readlink(path)
#         except OSError as e:
#             return SFTPServer.convert_errno(e.errno)
#         # if it's absolute, remove the root
#         if os.path.isabs(symlink):
#             if symlink[:len(self.ROOT)] == self.ROOT:
#                 symlink = symlink[len(self.ROOT):]
#                 if (len(symlink) == 0) or (symlink[0] != '/'):
#                     symlink = '/' + symlink
#             else:
#                 symlink = '<error>'
#         return symlink

def sftp_attributes(filepath, follow_links=False):
    """
    Return an SFTPAttributes object for the given path
    """
    filename = os.path.basename(filepath)
    stat = os.stat if follow_links else os.lstat
    return paramiko.SFTPAttributes.from_stat(
        stat(filepath), filename=filename)


def flags_to_string(flags):
    """
    Convert bitmask of flags as taken by `os.open` into a mode string
    as taken by `open`
    """
    if flags & os.O_WRONLY:
        if flags & os.O_APPEND:
            mode = 'a'
        else:
            mode = 'w'
    elif flags & os.O_RDWR:
        if flags & os.O_APPEND:
            mode = 'a+'
        else:
            mode = 'r+'
    else:
        mode = 'r'
    # Force binary mode
    mode += 'b'
    return mode