import errno
import functools
import logging
import os
import socket
import threading
from django.contrib.auth import authenticate
import paramiko
from paramiko.sftp import SFTP_OK, SFTP_OP_UNSUPPORTED
from paramiko.common import o666
from bioshareX.models import Share

class SFTPServer(object):
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
            'sftp', paramiko.SFTPServer, SFTPInterface)
        # The SFTP session runs in a separate thread. We pass in `event`
        # so `start_server` doesn't block; we're not actually interested
        # in waiting for the event though.
        transport.start_server(
                server=SSHInterface(self.get_user),
                event=threading.Event())

    def get_user(self, username, password):
        print 'get_user'
        print username
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
    Dectorator which converts exceptions into appropriate SFTP error codes,
    returns OK for functions which don't have a return value
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            value = fn(*args, **kwargs)
        except (OSError, IOError) as e:
            return paramiko.SFTPServer.convert_errno(e.errno)
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


class BioshareSFTPHandle (paramiko.SFTPHandle):
    def stat(self):
        try:
            return paramiko.SFTPAttributes.from_stat(os.fstat(self.readfile.fileno()))
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

    def chattr(self, attr):
        # python doesn't have equivalents to fchown or fchmod, so we have to
        # use the stored filename
        try:
            SFTPServer.set_file_attr(self.filename, attr)
            return SFTP_OK
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

class SFTPInterface (paramiko.SFTPServerInterface):
    # assume current folder is a fine root
    # (the tests always create and eventualy delete a subfolder, so there shouldn't be any mess)
#     ROOT = os.getcwd()
#     def __init__(self, server, *largs, **kwargs):
#         """
#         Create a new SFTPServerInterface object.  This method does nothing by
#         default and is meant to be overridden by subclasses.
#         
#         :param .ServerInterface server:
#             the server object associated with this channel and SFTP subsystem
#         """
#         super(SFTPServerInterface, self).__init__(*largs, **kwargs)
    def __init__(self, server):
        self.server = server
        self.user = server.user
        self.shares = {}
        for share in Share.user_queryset(self.user,include_stats=False):
            self.shares[share.id] = share#{'path':share.get_realpath()}
        print self.shares.keys()
        print 'user'
        print self.user
#         self.ROOT = root
    def _get_share(self,path):
        parts = path.split(os.path.sep)
        print parts
        if len(parts) < 2:
            print 'bad length'
            raise PermissionDenied("Received an invalid path: %s"%path) 
        if not self.shares.has_key(parts[1]):
            print 'no share exists'
            raise PermissionDenied("Share does not exist: %s"%path[1])
        return self.shares[parts[1]]
    def _get_bioshare_path_permissions(self,path):
        share = self._get_share(path)
        permissions = share.get_user_permissions(self.user)
        print permissions
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
        print 'realpath'
        print path
        parts = path.split(os.path.sep)
        share = self._get_share(path)
        realpath = os.path.join(share.get_realpath(),os.path.sep.join(parts[2:]))
        return realpath
#         print self.ROOT + self.canonicalize(path)
#         return self.ROOT + self.canonicalize(path)
    @sftp_response
    def list_shares(self):
        print "LIST SHARES"
        try:
            out = []
            for id,share in self.shares.iteritems():
                try:
                    print id
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
            print flist
            for fname in flist:
                attr = paramiko.SFTPAttributes.from_stat(os.stat(os.path.join(path, fname)))
                attr.filename = fname
                out.append(attr)
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
        try:
            f = os.fdopen(fd, fstr)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        fobj = BioshareSFTPHandle(flags)
        fobj.filename = path
        fobj.readfile = f
        fobj.writefile = f
        return fobj
    @sftp_response
    @permissions_required([Share.PERMISSION_DELETE])
    def remove(self, path):
#         if not Share.PERMISSION_DELETE in self._get_bioshare_path_permissions(path):
#             return PermissionDenied()
        path = self._realpath(path)
        try:
            os.remove(path)
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
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK
    @sftp_response
    @permissions_required([Share.PERMISSION_WRITE])
    def mkdir(self, path, attr):
        path = self._realpath(path)
        try:
            os.mkdir(path)
            if attr is not None:
                SFTPServer.set_file_attr(path, attr)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK
    @sftp_response
    @permissions_required([Share.PERMISSION_DELETE])
    def rmdir(self, path):
        path = self._realpath(path)
        try:
            os.rmdir(path)
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