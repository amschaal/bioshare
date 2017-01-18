import errno
import functools
import logging
import os
import socket
import threading
from django.contrib.auth import authenticate
import paramiko
from paramiko.sftp import SFTP_OK
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


class StubSFTPHandle (paramiko.SFTPHandle):
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
    def _realpath(self, path):
        print 'realpath'
        print path
        parts = path.split(os.path.sep)
        print parts
        if len(parts) < 2:
            print 'bad length'
            raise PermissionDenied("Received an invalid path: %s"%path) 
        if not self.shares.has_key(parts[1]):
            print 'no share exists'
            raise PermissionDenied("Share does not exist: %s"%path[1])
        share = self.shares[parts[1]]
        realpath = os.path.join(share.get_realpath(),os.path.sep.join(parts[2:]))
        return realpath
#         print self.ROOT + self.canonicalize(path)
#         return self.ROOT + self.canonicalize(path)
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
    def list_folder(self, path):
        if path == '/':
            return self.list_shares()
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

    def stat(self, path):
        path = self._realpath(path)
        try:
            return paramiko.SFTPAttributes.from_stat(os.stat(path))
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

    def lstat(self, path):
        path = self._realpath(path)
        try:
            return paramiko.SFTPAttributes.from_stat(os.lstat(path))
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

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
        fobj = StubSFTPHandle(flags)
        fobj.filename = path
        fobj.readfile = f
        fobj.writefile = f
        return fobj

    def remove(self, path):
        path = self._realpath(path)
        try:
            os.remove(path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def rename(self, oldpath, newpath):
        oldpath = self._realpath(oldpath)
        newpath = self._realpath(newpath)
        try:
            os.rename(oldpath, newpath)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def mkdir(self, path, attr):
        path = self._realpath(path)
        try:
            os.mkdir(path)
            if attr is not None:
                SFTPServer.set_file_attr(path, attr)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def rmdir(self, path):
        path = self._realpath(path)
        try:
            os.rmdir(path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def chattr(self, path, attr):
        path = self._realpath(path)
        try:
            SFTPServer.set_file_attr(path, attr)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def symlink(self, target_path, path):
        path = self._realpath(path)
        if (len(target_path) > 0) and (target_path[0] == '/'):
            # absolute symlink
            target_path = os.path.join(self.ROOT, target_path[1:])
            if target_path[:2] == '//':
                # bug in os.path.join
                target_path = target_path[1:]
        else:
            # compute relative to path
            abspath = os.path.join(os.path.dirname(path), target_path)
            if abspath[:len(self.ROOT)] != self.ROOT:
                # this symlink isn't going to work anyway -- just break it immediately
                target_path = '<error>'
        try:
            os.symlink(target_path, path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def readlink(self, path):
        path = self._realpath(path)
        try:
            symlink = os.readlink(path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        # if it's absolute, remove the root
        if os.path.isabs(symlink):
            if symlink[:len(self.ROOT)] == self.ROOT:
                symlink = symlink[len(self.ROOT):]
                if (len(symlink) == 0) or (symlink[0] != '/'):
                    symlink = '/' + symlink
            else:
                symlink = '<error>'
        return symlink
"""
class SFTPInterfaceExample(paramiko.SFTPServerInterface):

    FILE_MODE = 0664
    DIRECTORY_MODE = 0775

    def __init__(self, server, root):
        self.user = server.user
        self.root = root

    def realpath_for_read(self, path):
        return self._realpath(path, self.user.has_read_access)

    def realpath_for_write(self, path):
        return self._realpath(path, self.user.has_write_access)

    def _realpath(self, path, permission_check):
        path = self.canonicalize(path).lstrip('/')
        if not permission_check(path):
            raise PermissionDenied()
        return os.path.join(self.root, path)

    @sftp_response
    @log_event
    def open(self, path, flags, attr):
        # We ignore `attr` -- we choose the permissions around here,
        # not the client
        read_only = (flags == os.O_RDONLY)
        if read_only:
            realpath = self.realpath_for_read(path)
        else:
            realpath = self.realpath_for_write(path)
        fd = os.open(realpath, flags, self.FILE_MODE)
        fileobj = os.fdopen(fd, flags_to_string(flags), self.FILE_MODE)
        handle = SFTPFileHandle(flags)
        handle.readfile = fileobj
        if not read_only:
            handle.writefile = fileobj
        return handle

    @sftp_response
    @log_event
    def list_folder(self, path):
        realpath = self.realpath_for_read(path)
        return [sftp_attributes(os.path.join(realpath, filename))
                    for filename in os.listdir(realpath)]

    @sftp_response
    @log_event
    def stat(self, path):
        return sftp_attributes(self.realpath_for_read(path), follow_links=True)

    @sftp_response
    def lstat(self, path):
        return sftp_attributes(self.realpath_for_read(path))

    @sftp_response
    @log_event
    def remove(self, path):
        os.unlink(self.realpath_for_write(path))

    @sftp_response
    @log_event
    def rename(self, oldpath, newpath):
        realpath_old = self.realpath_for_write(oldpath)
        realpath_new = self.realpath_for_write(newpath)
        # SFTP dictates that renames should be non-destructive
        # (Yes, there's a race-condition here, but we can live
        # with it)
        if os.path.exists(realpath_new):
            raise OSError(errno.EEXIST)
        os.rename(realpath_old, realpath_new)

    @sftp_response
    @log_event
    def mkdir(self, path, attr):
        # We ignore `attr` -- we choose the permissions around here,
        # not the client
        os.mkdir(self.realpath_for_write(path), self.DIRECTORY_MODE)

    @sftp_response
    @log_event
    def rmdir(self, path):
        os.rmdir(self.realpath_for_write(path))

    @sftp_response
    @log_event
    def chattr(self, path, attr):
        # We flat-out lie and pretend that we've executed this
        # but don't actually do anything
        pass

    @sftp_response
    @log_event
    def readlink(self, path):
        # We only allow `readlink` on relative links that stay within the
        # shared root directory
        realpath = self.realpath_for_read(path)
        target = os.readlink(realpath)
        if os.path.isabs(target):
            return paramiko.SFTP_OP_UNSUPPORTED
        target_abs = os.path.normpath(os.path.join(
            os.path.dirname(realpath), target))
        if not target_abs.startswith(self.root + '/'):
            return paramiko.SFTP_OP_UNSUPPORTED
        return target
"""
"""
class SFTPFileHandle(paramiko.SFTPHandle):

    @sftp_response
    def chattr(self, path, attr):
        # We flat-out lie and pretend that we've executed this
        # but don't actually do anything
        pass

    @sftp_response
    def stat(self):
        return paramiko.SFTPAttributes.from_stat(
                os.fstat(self.readfile.fileno()))

"""
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