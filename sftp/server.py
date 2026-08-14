import errno
import functools
import logging
import os
import socket
import stat as stdlib_stat
import threading
import time
from django.utils import timezone
from django.contrib.auth import authenticate
import paramiko
from paramiko import SFTPServer, SFTPServerInterface
from paramiko.sftp import SFTP_OK, SFTP_OP_UNSUPPORTED
from paramiko.common import o666
from bioshareX.models import Share, ShareLog, SSHKey
from paramiko.sftp_handle import SFTPHandle
from bioshareX.utils import paths_contain
from django.conf import settings
from django.contrib.auth.models import User

SFTP_UPDATE_SHARE_MODIFIED_DATE_FREQUENCY_SECONDS = getattr(settings, 'SFTP_UPDATE_SHARE_MODIFIED_DATE_FREQUENCY_SECONDS',60)

# Ceiling on live SSH transports. Every connection costs a file descriptor and
# at least one thread, and neither is reclaimed until the client goes away, so
# without a bound a connection flood exhausts the process fd limit -- at which
# point accept() starts failing for everyone. SOCKET_BACKLOG bounds only the
# pending-accept queue, not live sessions.
SFTP_MAX_SESSIONS = getattr(settings, 'SFTP_MAX_SESSIONS', 100)
# Seconds a connection may stay open without completing authentication.
SFTP_AUTH_TIMEOUT_SECONDS = getattr(settings, 'SFTP_AUTH_TIMEOUT_SECONDS', 30)
# How often the reaper sweeps for stalled and finished sessions.
SFTP_SESSION_SWEEP_INTERVAL_SECONDS = getattr(settings, 'SFTP_SESSION_SWEEP_INTERVAL_SECONDS', 5)
# Keepalive interval for established transports; detects clients that vanished
# without closing (NAT timeouts, killed laptops) so their slot is released.
SFTP_KEEPALIVE_SECONDS = getattr(settings, 'SFTP_KEEPALIVE_SECONDS', 60)

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

    SOCKET_BACKLOG = 50

    # Seconds to pause after an accept() failure caused by resource exhaustion.
    # Those errors recur instantly, so continuing without a pause would spin the
    # accept loop at full speed and log-flood the disk.
    ACCEPT_ERROR_BACKOFF_SECONDS = 1

    # accept() errors that mean "out of a resource" rather than "that one client
    # went away", and so warrant backing off before trying again.
    _EXHAUSTION_ERRNOS = frozenset(
        e for e in (getattr(errno, name, None)
                    for name in ('EMFILE', 'ENFILE', 'ENOBUFS', 'ENOMEM'))
        if e is not None)

    def __init__(self, host_key_path, get_user=None, get_user_by_key=None):
        self.host_key = paramiko.PKey.from_path(host_key_path)
        if get_user is not None:
            self.get_user = get_user
        if get_user_by_key is not None:
            self.get_user_by_key = get_user_by_key
        # Transport -> monotonic timestamp of the accept() that produced it.
        # Read and written by both the accept loop and the reaper thread.
        self._sessions = {}
        self._sessions_lock = threading.Lock()

    def serve_forever(self, host, port):
        server_socket = socket.socket()
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        server_socket.bind((host, port))
        server_socket.listen(self.SOCKET_BACKLOG)
        threading.Thread(target=self._reap_sessions_forever, name='sftp-session-reaper',
                         daemon=True).start()
        logging.info('SFTP server listening on %s:%s (max %s sessions)', host, port, SFTP_MAX_SESSIONS)
        while True:
            # Nothing in this loop may be allowed to escape: this thread is the
            # only acceptor, and startup.sh backgrounds `manage.py start_sftp`
            # with no supervisor, so an exception here takes SFTP down for every
            # user until the container is restarted.
            try:
                conn, address = server_socket.accept()
            except Exception as e:
                # accept() itself fails on ECONNABORTED (peer reset between SYN
                # and accept) and on fd exhaustion. The former is routine; the
                # latter repeats until something frees a descriptor.
                logging.exception('SFTP accept() failed')
                if getattr(e, 'errno', None) in self._EXHAUSTION_ERRNOS:
                    time.sleep(self.ACCEPT_ERROR_BACKOFF_SECONDS)
                continue
            try:
                if not self._has_session_capacity():
                    logging.warning('Refusing SFTP connection from %s: %s live sessions',
                                    address, SFTP_MAX_SESSIONS)
                    conn.close()
                    continue
                self.start_sftp_session(conn)
            except Exception:
                # Only reachable if setup failed, in which case paramiko never
                # took ownership of the socket and we still have to close it.
                # (Handshake and auth failures are *not* seen here: start_server
                # returns as soon as the negotiation thread is running, so those
                # surface as paramiko.transport log records instead.)
                logging.exception('SFTP session setup failed for %s', address)
                conn.close()

    # Algorithms considered weak/legacy that should not be negotiated.
    # `keys` covers the host key we present; `pubkeys` covers client keys offered
    # for publickey auth. SSHKey.KEY_TYPES already refuses to store an ssh-dss
    # key, so this is belt-and-braces -- but it rejects one at negotiation rather
    # than after a pointless database lookup.
    DISABLED_ALGORITHMS = {
        'ciphers': ['blowfish-cbc', '3des-cbc', 'aes128-cbc', 'aes192-cbc', 'aes256-cbc'],
        'macs': ['hmac-md5', 'hmac-md5-96', 'hmac-sha1-96'],
        'kex': ['diffie-hellman-group1-sha1', 'diffie-hellman-group-exchange-sha1'],
        'keys': ['ssh-dss'],
        'pubkeys': ['ssh-dss'],
    }

    def start_sftp_session(self, conn):
        # Note: no conn.settimeout() here. Transport.__init__ immediately
        # replaces any socket timeout with its own 0.1s active-check interval,
        # so setting one has no effect. Liveness is handled by set_keepalive()
        # below and by _reap_sessions_forever().
        transport = paramiko.Transport(conn, disabled_algorithms=self.DISABLED_ALGORITHMS)
        transport.add_server_key(self.host_key)
        transport.set_subsystem_handler(
            'sftp', SFTPServer, SFTPInterface)
        if SFTP_KEEPALIVE_SECONDS:
            transport.set_keepalive(SFTP_KEEPALIVE_SECONDS)
        # The SFTP session runs in a separate thread. We pass in `event`
        # so `start_server` doesn't block; we're not actually interested
        # in waiting for the event though.
        transport.start_server(
                server=SSHInterface(self.get_user, self.get_user_by_key),
                event=threading.Event())
        self._register_session(transport)
        return transport

    def _has_session_capacity(self):
        """Drop finished sessions and report whether there is room for one more."""
        with self._sessions_lock:
            for transport in [t for t in self._sessions if not t.is_active()]:
                del self._sessions[transport]
            return len(self._sessions) < SFTP_MAX_SESSIONS

    def _register_session(self, transport):
        with self._sessions_lock:
            self._sessions[transport] = time.monotonic()

    def _sweep_sessions(self):
        """Forget finished sessions and close ones stuck before authentication.

        paramiko has no server-side auth timeout -- Transport.auth_timeout is
        only consulted by the *client* -- so a peer that completes the handshake
        and then simply stops holds a thread and a file descriptor forever. That
        is what lets an idle attacker fill SFTP_MAX_SESSIONS, and past the
        process fd limit it is what makes accept() start failing.

        Returns the transports it closed, for logging and tests.
        """
        now = time.monotonic()
        stalled = []
        with self._sessions_lock:
            for transport, started in list(self._sessions.items()):
                if not transport.is_active():
                    del self._sessions[transport]
                elif (not transport.is_authenticated()
                        and now - started > SFTP_AUTH_TIMEOUT_SECONDS):
                    del self._sessions[transport]
                    stalled.append(transport)
        for transport in stalled:
            logging.warning('Closing SFTP connection that did not authenticate within %ss',
                            SFTP_AUTH_TIMEOUT_SECONDS)
            try:
                transport.close()
            except Exception:
                logging.exception('Error closing stalled SFTP transport')
        return stalled

    def _reap_sessions_forever(self):
        while True:
            time.sleep(SFTP_SESSION_SWEEP_INTERVAL_SECONDS)
            try:
                self._sweep_sessions()
            except Exception:
                # The reaper is the only thing reclaiming slots; letting it die
                # would silently reintroduce the exhaustion it exists to prevent.
                logging.exception('SFTP session reaper error')

    ALLOW_ANONYMOUS = getattr(settings, 'SFTP_ALLOW_ANONYMOUS', False)

    def get_user(self, username, password):
        if username == 'anonymous':
            if not self.ALLOW_ANONYMOUS:
                return None
            return User.objects.filter(id=-1).first()
        return authenticate(username=username, password=password)

    def get_user_by_key(self, username, key):
        """Resolve a User from a public key paramiko received from the client.

        `authenticate()` is unusable here because there is no password, which
        means the is_active check ModelBackend.user_can_authenticate() normally
        applies has to be made explicitly -- otherwise a deactivated account
        would keep SFTP access for as long as one of its keys was on file.

        Anonymous access is not reachable this way: it is a password-path
        concept and has no key to present.
        """
        if username == 'anonymous':
            return None
        user = User.objects.filter(username=username, is_active=True).first()
        if user is None:
            return None
        # Public keys are not secrets, so a plain comparison is fine. Comparing
        # the parsed wire-format blob rather than the stored text sidesteps
        # comments and whitespace, and means the algorithm name the client chose
        # (rsa-sha2-512 vs ssh-rsa) doesn't affect the match.
        presented = key.asbytes()
        for ssh_key in SSHKey.objects.filter(user=user):
            try:
                stored = ssh_key.blob
            except ValueError:
                logging.warning('Ignoring unparseable stored SSH key id=%s for %s',
                                ssh_key.id, username)
                continue
            if stored == presented:
                return user
        return None


class SSHInterface(paramiko.ServerInterface):

    # Password auth runs Django's password hasher (PBKDF2, ~100ms of CPU per
    # call), so its budget is deliberately tight.
    MAX_AUTH_ATTEMPTS = 5
    # Public key auth gets its own, larger budget rather than sharing the above.
    # A stock OpenSSH client offers every key in ~/.ssh before falling back to a
    # password, and paramiko calls check_auth_publickey *twice* per key -- once
    # for the client's unsigned "would you accept this?" probe, once with the
    # signature. Sharing one counter would therefore lock a legitimate user with
    # three keys out of the password fallback they were heading for anyway. A
    # key comparison is a single indexed query, so a looser bound costs little.
    MAX_PUBLICKEY_ATTEMPTS = 20

    def __init__(self, get_user, get_user_by_key=None):
        self.get_user = get_user
        self.get_user_by_key = get_user_by_key
        self._auth_attempts = 0
        self._publickey_attempts = 0

    def get_allowed_auths(self, username):
        # paramiko's default advertises password only, so clients never try a
        # key. Listing publickey first is what makes them offer one before
        # prompting.
        if self.get_user_by_key is None:
            return 'password'
        return 'publickey,password'

    def check_auth_password(self, username, password):
        self._auth_attempts += 1
        if self._auth_attempts > self.MAX_AUTH_ATTEMPTS:
            logging.warning(u'Auth attempt limit exceeded for %s' % username)
            return paramiko.AUTH_FAILED
        user = self.get_user(username, password)
        if user:
            logging.info(u'Auth successful for %s' % username)
            self.user = user
            return paramiko.AUTH_SUCCESSFUL
        else:
            logging.info(u'Auth failed for %s' % username)
            return paramiko.AUTH_FAILED

    def check_auth_publickey(self, username, key):
        if self.get_user_by_key is None:
            return paramiko.AUTH_FAILED
        self._publickey_attempts += 1
        if self._publickey_attempts > self.MAX_PUBLICKEY_ATTEMPTS:
            logging.warning(u'Public key attempt limit exceeded for %s' % username)
            return paramiko.AUTH_FAILED
        try:
            user = self.get_user_by_key(username, key)
        except Exception:
            # A database error here must not be reported as a successful auth,
            # and must not escape into paramiko's auth handler either.
            logging.exception(u'Error resolving public key for %s' % username)
            return paramiko.AUTH_FAILED
        if user:
            # Returning AUTH_SUCCESSFUL only tells paramiko the key is
            # acceptable; it then verifies the client's signature over the
            # session blob and fails the auth itself if that doesn't check out.
            # No channel can be opened unless that verification passes, so
            # setting self.user on the unsigned probe is safe.
            logging.info(u'Public key auth successful for %s' % username)
            self.user = user
            return paramiko.AUTH_SUCCESSFUL
        logging.info(u'Public key auth failed for %s' % username)
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
        string_args = u':'.join([arg for arg in args if isinstance(arg, str)])
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

SYMLINK_RECHECK_INTERVAL_SECONDS = getattr(settings, 'SFTP_SYMLINK_RECHECK_INTERVAL_SECONDS', 300)

class SFTPInterface (SFTPServerInterface):
    def __init__(self, server):
        self.server = server
        self.user = server.user
        self.shares = {}
        self.shares_accessed = set()
        self.modified_date = {}
        self._symlink_checked = {}
        for share in Share.user_queryset(self.user,include_stats=False):
            self.shares[share.slug_or_id] = share
    def session_ended(self):
        SFTPServerInterface.session_ended(self)
        Share.objects.filter(id__in=list(self.shares_accessed)).update(last_data_access=timezone.now())
    def _get_share(self,path):
        parts = path.split(os.path.sep)
        if len(parts) < 2:
            logging.warning('Received an invalid path: %s', path)
            raise PermissionDenied("Received an invalid path: %s"%path)
        if parts[1] not in self.shares and self.user.id == -1: #Anonymous users don't yet have a dictionary of shares.
            try:
                share = Share.get_by_slug_or_id(parts[1])
                self.shares[share.slug_or_id] = share
            except Share.DoesNotExist:
                pass
        if parts[1] not in self.shares:
            logging.warning('Share does not exist: {}, {}'.format(path, self.shares))
            raise PermissionDenied("Share does not exist: {}, {}}".format(path[1], self.shares))
        share = self.shares[parts[1]]
        now = timezone.now()
        last_checked = self._symlink_checked.get(share.id)
        if not last_checked or (now - last_checked).total_seconds() > SYMLINK_RECHECK_INTERVAL_SECONDS:
            if share.symlinks_found:
                share.check_paths()
            self._symlink_checked[share.id] = now
        if share.locked:
            raise PermissionDenied('Share is locked.  Contact the application administrator.')
        return share
    def _path_modified(self,path):
        share = self._get_share(path)
        previous_date = self.modified_date.get(share.id,None)
        current_date = timezone.now()
        if not previous_date or (current_date-previous_date).seconds > SFTP_UPDATE_SHARE_MODIFIED_DATE_FREQUENCY_SECONDS:
            self.modified_date[share.id] = current_date
            Share.objects.filter(id=share.id,updated__lt=current_date).update(updated=current_date)
    def _get_subpath(self, path): # takes /<share_id>/subpath
        parts = path.split(os.path.sep)
        return os.path.sep.join(parts[2:])
    def _create_log(self, path, action, text): # takes /<share_id>/subpath for path
        ShareLog.create(share=self._get_share(path),user=self.user,action=action,paths=[self._get_subpath(path)], text=text)
    def _get_bioshare_path_permissions(self,path):
        share = self._get_share(path)
        self.shares_accessed.add(share.id)
        permissions = share.get_user_permissions(self.user)
#         print permissions
        if not self.is_realpath(path): # Don't allow any write operations if it isn't a real directory under the share root
            if Share.PERMISSION_DELETE in permissions:
                permissions.remove(Share.PERMISSION_DELETE)
            if Share.PERMISSION_WRITE in permissions:
                permissions.remove(Share.PERMISSION_WRITE)
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
        # Containment must be to THIS share's own root (plus legitimate symlink
        # targets), NOT the global DIRECTORY_WHITELIST.  DIRECTORY_WHITELIST
        # includes FILESYSTEM_DIRECTORIES (e.g. /data/shares), the parent of every
        # share, so checking against it lets a `..` in an SFTP path escape into a
        # sibling share that the session was never granted access to.  The HTTP
        # layer avoids this by running test_path() (which rejects `..`); SFTP has
        # no such step, so we enforce per-share containment here instead.
        allowed_roots = [share.get_realpath()] + list(getattr(settings, 'LINK_TO_DIRECTORIES', []))
        if not paths_contain(allowed_roots,realpath):
            share.check_paths()
            raise PermissionDenied("Encountered a path outside the share")
        return realpath
#         print self.ROOT + self.canonicalize(path)
#         return self.ROOT + self.canonicalize(path)
    def is_realpath(self, path):
        parts = path.split(os.path.sep)
        share = self._get_share(path)
        # print('is_realpath', share.is_realpath(os.path.sep.join(parts[2:])), os.path.sep.join(parts[2:]))
        return share.is_realpath(os.path.sep.join(parts[2:]))
    def _root_attributes(self):
        """Synthetic attrs for the virtual SFTP root '/' (no real fs path)."""
        now = int(timezone.now().timestamp())
        attr = paramiko.SFTPAttributes()
        attr.st_mode = stdlib_stat.S_IFDIR | 0o755
        attr.st_size = 0
        attr.st_uid = 0
        attr.st_gid = 0
        attr.st_atime = now
        attr.st_mtime = now
        return attr
    @sftp_response
    def list_shares(self):
#         print "LIST SHARES"
        if self.user.id == -1:
            return []
        try:
            out = []
            for id,share in self.shares.items():
                try:
#                     print id
                    attr = paramiko.SFTPAttributes.from_stat(os.stat(share.get_realpath()))
                    attr.filename = id
                    out.append(attr)
                except Exception as e:
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
                    logging.warning('Error reading file attributes: %s: %s', os.path.join(path, fname), e)
            return out
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

    @sftp_response
    @permissions_required([Share.PERMISSION_VIEW])
    def stat(self, path):
        if path == '/':
            return self._root_attributes()
        path = self._realpath(path)
        try:
            return paramiko.SFTPAttributes.from_stat(os.stat(path))
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
    @sftp_response
    @permissions_required([Share.PERMISSION_VIEW])
    def lstat(self, path):
        if path == '/':
            return self._root_attributes()
        path = self._realpath(path)
        try:
            return paramiko.SFTPAttributes.from_stat(os.lstat(path))
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
    @sftp_response
    def open(self, path, flags, attr):
        permissions = self._get_bioshare_path_permissions(path)
        IS_WRITE = flags & os.O_CREAT or flags & os.O_WRONLY or flags & os.O_RDWR or flags & os.O_APPEND
        if not ((not IS_WRITE and Share.PERMISSION_VIEW in permissions and Share.PERMISSION_DOWNLOAD in permissions) or  (IS_WRITE and Share.PERMISSION_WRITE in permissions and Share.PERMISSION_VIEW in permissions)):
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
            logging.error('Error setting file flags: %s', e)
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
            self._create_log(path, ShareLog.ACTION_DELETED, 'SFTP delete')
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK
    @sftp_response
    @permissions_required([Share.PERMISSION_DELETE,Share.PERMISSION_WRITE])
    def rename(self, oldpath, newpath):
        # Verify write permission on destination share (decorator only checks oldpath)
        dest_permissions = self._get_bioshare_path_permissions(newpath)
        if Share.PERMISSION_WRITE not in dest_permissions:
            raise PermissionDenied()
        oldpath = self._realpath(oldpath)
        newpath = self._realpath(newpath)
        try:
            os.rename(oldpath, newpath)
            self._path_modified(oldpath)
            old = os.path.basename(oldpath)
            new = os.path.basename(newpath)
            self._create_log(oldpath, ShareLog.ACTION_RENAMED, 'SFTP renamed {} to {}'.format(old, new))
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
            self._create_log(path, ShareLog.ACTION_FOLDER_CREATED, 'SFTP folder created')
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
            self._create_log(path, ShareLog.ACTION_DELETED, 'SFTP directory deleted')
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