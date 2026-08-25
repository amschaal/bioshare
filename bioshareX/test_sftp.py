"""
Tests for the paramiko SFTP daemon in sftp/server.py.

Four concerns are covered here:

  * **Availability** -- the accept loop in ``BioshareSFTPServer.serve_forever``
    is the single acceptor for the whole daemon, and ``startup.sh`` backgrounds
    it with no supervisor, so anything that escapes it takes SFTP down for every
    user until the container restarts. These tests drive the loop with a fake
    listening socket and assert it survives, cleans up, and enforces its
    session ceiling.

  * **Public key authentication** -- that a stored SSHKey admits its owner, that
    nothing else does, and that the per-method attempt budgets don't lock out a
    legitimate client.

  * **Permission caching** -- a bulk transfer used to cost one guardian query
    per file opened. These tests assert the memo holds within its window, and
    pin down what it costs: a revocation is not seen until the window passes,
    while locking the share still bites immediately.

  * **Upload buffering** -- writes are no longer flushed per block, which moves
    the reporting of a failed write from the write to the close. These tests
    assert the bytes still land, and that a failure draining the buffer reaches
    both the client and the log rather than passing as a complete upload.

They live in bioshareX/ rather than sftp/ so ``manage.py test bioshareX`` picks
them up; the sftp package is not in INSTALLED_APPS.

Run with:  python manage.py test bioshareX.test_sftp
"""

import base64
import contextlib
import datetime
import errno
import logging
import os
from unittest import mock

import paramiko
from django.test import TestCase
from django.utils import timezone
from guardian.shortcuts import remove_perm
from paramiko.sftp import (CMD_CLOSE, SFTP_BAD_MESSAGE, SFTP_FAILURE, SFTP_OK,
                           SFTP_OP_UNSUPPORTED, SFTP_PERMISSION_DENIED)

from bioshareX.models import Share, ShareLog, SSHKey
from bioshareX.test_base import ShareTestBase, make_public_key
from sftp import server as sftp_server
from sftp.server import BioshareSFTPServer, PermissionDenied, SSHInterface


class _StopLoop(BaseException):
    """Breaks out of serve_forever's `while True`.

    Deliberately a BaseException: serve_forever catches Exception around every
    part of the loop precisely so that nothing escapes, so an ordinary exception
    could not end the test.
    """


class _FakeTransport:
    def __init__(self, active=True, authenticated=False):
        self._active = active
        self._authenticated = authenticated
        self.closed = False

    def is_active(self):
        return self._active

    def is_authenticated(self):
        return self._authenticated

    def close(self):
        self.closed = True
        self._active = False


def _fake_conn():
    conn = mock.Mock()
    conn.closed = False
    conn.close.side_effect = lambda: setattr(conn, 'closed', True)
    return conn


class TestServeForeverResilience(TestCase):
    """The accept loop must survive everything short of process death."""

    def setUp(self):
        super().setUp()
        with mock.patch.object(paramiko.PKey, 'from_path', return_value=mock.Mock()):
            self.server = BioshareSFTPServer('/nonexistent/host_key')

    def _run_loop(self, accept_results, **patches):
        """Drive serve_forever over a scripted accept() sequence, then stop.

        Each entry is either an exception to raise or a (conn, address) tuple.

        Every path through the loop is required to log, both because a silent
        crash-turned-continue leaves no breadcrumb to debug and because
        assertLogs captures the records instead of letting the tracebacks print
        over the test runner's output.
        """
        listening = mock.Mock()
        accepted = []

        def accept():
            if not accept_results:
                raise _StopLoop()
            result = accept_results.pop(0)
            if isinstance(result, BaseException):
                raise result
            accepted.append(result[0])
            return result

        listening.accept.side_effect = accept
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(sftp_server.socket, 'socket',
                                                  return_value=listening))
            stack.enter_context(mock.patch.object(BioshareSFTPServer,
                                                  '_reap_sessions_forever'))
            self.sleep = stack.enter_context(mock.patch.object(sftp_server.time, 'sleep'))
            if patches:
                stack.enter_context(mock.patch.multiple(BioshareSFTPServer, **patches))
            logs = stack.enter_context(self.assertLogs(level='WARNING'))
            with self.assertRaises(_StopLoop):
                self.server.serve_forever('0.0.0.0', 2233)
        self.logs = logs.output
        return accepted

    def test_accept_error_does_not_kill_the_loop(self):
        """A failed accept() is logged and the next connection is still served."""
        conn = _fake_conn()
        started = []
        self._run_loop(
            [OSError(errno.ECONNABORTED, 'aborted'), (conn, ('10.0.0.1', 5000))],
            start_sftp_session=lambda self_, c: started.append(c))
        self.assertEqual(started, [conn])
        self.assertFalse(conn.closed)  # handed to paramiko, not closed by us
        self.assertIn('SFTP accept() failed', self.logs[0])

    def test_non_oserror_from_accept_also_survived(self):
        """The loop catches Exception, not just OSError: nothing may escape it."""
        conn = _fake_conn()
        started = []
        self._run_loop([RuntimeError('unexpected'), (conn, ('10.0.0.1', 1))],
                       start_sftp_session=lambda self_, c: started.append(c))
        self.assertEqual(started, [conn])
        self.assertIn('SFTP accept() failed', self.logs[0])

    def test_fd_exhaustion_backs_off_instead_of_spinning(self):
        self._run_loop([OSError(errno.EMFILE, 'too many open files')])
        self.sleep.assert_called_once_with(BioshareSFTPServer.ACCEPT_ERROR_BACKOFF_SECONDS)

    def test_transient_accept_error_does_not_back_off(self):
        self._run_loop([OSError(errno.ECONNABORTED, 'aborted')])
        self.sleep.assert_not_called()

    def test_session_setup_failure_closes_socket_and_continues(self):
        """A handshake-time blowup must not leak the fd or stop the daemon."""
        bad, good = _fake_conn(), _fake_conn()
        calls = []

        def start(self_, conn):
            calls.append(conn)
            if conn is bad:
                raise paramiko.SSHException('negotiation exploded')

        self._run_loop([(bad, ('10.0.0.1', 1)), (good, ('10.0.0.2', 2))],
                       start_sftp_session=start)
        self.assertEqual(calls, [bad, good])
        self.assertTrue(bad.closed)     # we still owned it, so we closed it
        self.assertFalse(good.closed)   # paramiko owns this one
        self.assertIn('SFTP session setup failed', self.logs[0])

    def test_thread_exhaustion_does_not_kill_the_daemon(self):
        """The realistic crash: Transport.start_server() calls Thread.start(),
        which raises RuntimeError once the process is out of threads. Under a
        connection flood that is what used to take SFTP down for everyone."""
        first, second = _fake_conn(), _fake_conn()
        seen = []

        def start(self_, conn):
            seen.append(conn)
            if conn is first:
                raise RuntimeError("can't start new thread")

        self._run_loop([(first, ('10.0.0.1', 1)), (second, ('10.0.0.2', 2))],
                       start_sftp_session=start)
        self.assertEqual(seen, [first, second])
        self.assertTrue(first.closed)
        self.assertIn('SFTP session setup failed', self.logs[0])

    def test_connection_refused_past_session_ceiling(self):
        self.server._sessions = {_FakeTransport(): 0.0
                                 for _ in range(sftp_server.SFTP_MAX_SESSIONS)}
        conn = _fake_conn()
        started = []
        self._run_loop([(conn, ('10.0.0.1', 1))],
                       start_sftp_session=lambda self_, c: started.append(c))
        self.assertEqual(started, [])
        self.assertTrue(conn.closed)
        self.assertIn('Refusing SFTP connection', self.logs[0])

    def test_capacity_reclaimed_from_finished_sessions(self):
        """Dead transports must not permanently consume the session budget."""
        self.server._sessions = {_FakeTransport(active=False): 0.0
                                 for _ in range(sftp_server.SFTP_MAX_SESSIONS)}
        self.assertTrue(self.server._has_session_capacity())
        self.assertEqual(self.server._sessions, {})


class TestSessionReaper(TestCase):
    """paramiko applies no server-side auth timeout; _sweep_sessions is ours."""

    def setUp(self):
        super().setUp()
        with mock.patch.object(paramiko.PKey, 'from_path', return_value=mock.Mock()):
            self.server = BioshareSFTPServer('/nonexistent/host_key')

    def test_closes_connections_stalled_before_authentication(self):
        stalled = _FakeTransport(authenticated=False)
        fresh = _FakeTransport(authenticated=False)
        now = sftp_server.time.monotonic()
        self.server._sessions = {
            stalled: now - sftp_server.SFTP_AUTH_TIMEOUT_SECONDS - 1,
            fresh: now,
        }
        with self.assertLogs(level='WARNING') as logs:
            self.assertEqual(self.server._sweep_sessions(), [stalled])
        self.assertTrue(stalled.closed)
        self.assertFalse(fresh.closed)
        self.assertEqual(list(self.server._sessions), [fresh])
        self.assertIn('did not authenticate', logs.output[0])

    def test_leaves_authenticated_sessions_alone(self):
        """A long transfer is old but authenticated, and must not be cut off."""
        transferring = _FakeTransport(authenticated=True)
        self.server._sessions = {transferring: sftp_server.time.monotonic() - 86400}
        self.assertEqual(self.server._sweep_sessions(), [])
        self.assertFalse(transferring.closed)

    def test_forgets_transports_that_ended_on_their_own(self):
        done = _FakeTransport(active=False, authenticated=True)
        self.server._sessions = {done: 0.0}
        self.assertEqual(self.server._sweep_sessions(), [])
        self.assertEqual(self.server._sessions, {})

    def test_reaper_survives_a_failing_sweep(self):
        sweeps = []

        def sweep(self_):
            sweeps.append(1)
            if len(sweeps) == 1:
                raise RuntimeError('transient')
            raise _StopLoop()

        with mock.patch.object(sftp_server.time, 'sleep'), \
                mock.patch.object(BioshareSFTPServer, '_sweep_sessions', sweep):
            with self.assertLogs(level='ERROR') as logs:
                with self.assertRaises(_StopLoop):
                    self.server._reap_sessions_forever()
        self.assertEqual(len(sweeps), 2)  # it kept going after the failure
        self.assertIn('SFTP session reaper error', logs.output[0])


class _PresentedKey:
    """Stands in for the paramiko PKey the auth handler hands the server."""

    def __init__(self, line):
        self._blob = base64.b64decode(line.split()[1])

    def asbytes(self):
        return self._blob


class TestPublicKeyAuth(ShareTestBase):

    def setUp(self):
        super().setUp()
        with mock.patch.object(paramiko.PKey, 'from_path', return_value=mock.Mock()):
            self.server = BioshareSFTPServer('/nonexistent/host_key')
        self.key_line = make_public_key('ssh-ed25519', comment='laptop')
        self.stored = SSHKey.objects.create(user=self.owner, name='laptop',
                                            key=self.key_line)

    def test_uploaded_key_authenticates_its_owner(self):
        user = self.server.get_user_by_key(self.owner.username,
                                           _PresentedKey(self.key_line))
        self.assertEqual(user, self.owner)

    def test_key_does_not_authenticate_a_different_account(self):
        self.assertIsNone(self.server.get_user_by_key(
            self.other.username, _PresentedKey(self.key_line)))

    def test_deleted_key_stops_working_immediately(self):
        self.stored.delete()
        self.assertIsNone(self.server.get_user_by_key(
            self.owner.username, _PresentedKey(self.key_line)))

    def test_unknown_key_is_rejected(self):
        self.assertIsNone(self.server.get_user_by_key(
            self.owner.username, _PresentedKey(make_public_key(filler=b'\x99'))))

    def test_deactivated_account_cannot_use_its_key(self):
        """authenticate() would apply this check for us; the key path can't."""
        self.owner.is_active = False
        self.owner.save()
        self.assertIsNone(self.server.get_user_by_key(
            self.owner.username, _PresentedKey(self.key_line)))

    def test_anonymous_has_no_key_path(self):
        """Anonymous access is a password-path concept; it has no key to present."""
        self.assertIsNone(self.server.get_user_by_key(
            'anonymous', _PresentedKey(self.key_line)))

    def test_unparseable_stored_key_is_skipped_not_fatal(self):
        """A row predating validation must be stepped over, not raised through.

        Deleting the good key first is what makes this deterministic: the loop
        returns on the first match and the queryset has no explicit ordering, so
        with both rows present the garbage one may never be reached at all.
        """
        self.stored.delete()
        SSHKey.objects.create(user=self.owner, name='legacy', key='garbage')
        with self.assertLogs(level='WARNING') as logs:
            user = self.server.get_user_by_key(self.owner.username,
                                               _PresentedKey(self.key_line))
        self.assertIsNone(user)
        self.assertIn('unparseable stored SSH key', logs.output[0])

    def test_unparseable_row_does_not_block_a_valid_key(self):
        """Whichever order the two rows come back in, the good one still wins."""
        SSHKey.objects.create(user=self.owner, name='legacy', key='garbage')
        # The garbage row may or may not be reached before the match, so whether
        # a warning is emitted is not something this test can assert either way.
        # Mute instead, so the outcome doesn't depend on row order.
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)
        user = self.server.get_user_by_key(self.owner.username,
                                           _PresentedKey(self.key_line))
        self.assertEqual(user, self.owner)

    def test_matching_is_independent_of_comment_and_whitespace(self):
        body = self.key_line.split()[1]
        self.stored.key = '  ssh-ed25519  %s  someone@elsewhere  \n' % body
        self.stored.save()
        self.assertEqual(
            self.server.get_user_by_key(self.owner.username, _PresentedKey(self.key_line)),
            self.owner)


class TestSSHInterfaceAuth(TestCase):
    """The paramiko-facing auth surface: advertised methods and attempt budgets."""

    def _interface(self, user=None, key_user=None):
        return SSHInterface(get_user=lambda u, p: user,
                            get_user_by_key=lambda u, k: key_user)

    def test_publickey_is_advertised_first(self):
        self.assertEqual(self._interface().get_allowed_auths('bob'),
                         'publickey,password')

    def test_only_password_advertised_without_a_key_resolver(self):
        interface = SSHInterface(get_user=lambda u, p: None)
        self.assertEqual(interface.get_allowed_auths('bob'), 'password')
        self.assertEqual(interface.check_auth_publickey('bob', object()),
                         paramiko.AUTH_FAILED)

    def test_successful_key_auth_sets_the_session_user(self):
        sentinel = object()
        interface = self._interface(key_user=sentinel)
        self.assertEqual(interface.check_auth_publickey('bob', object()),
                         paramiko.AUTH_SUCCESSFUL)
        self.assertIs(interface.user, sentinel)

    def test_key_offers_do_not_consume_the_password_budget(self):
        """paramiko calls check_auth_publickey twice per key, and OpenSSH offers
        every key in ~/.ssh before falling back to a password. A shared counter
        would deny the fallback the client was legitimately heading for."""
        interface = self._interface(user='pw-user', key_user=None)
        for _ in range(SSHInterface.MAX_AUTH_ATTEMPTS * 2):
            interface.check_auth_publickey('bob', object())
        self.assertEqual(interface.check_auth_password('bob', 'secret'),
                         paramiko.AUTH_SUCCESSFUL)

    def test_password_budget_still_bounded(self):
        interface = self._interface(user=None)
        for _ in range(SSHInterface.MAX_AUTH_ATTEMPTS):
            self.assertEqual(interface.check_auth_password('bob', 'wrong'),
                             paramiko.AUTH_FAILED)
        interface.get_user = lambda u, p: 'right-this-time'
        with self.assertLogs(level='WARNING') as logs:
            self.assertEqual(interface.check_auth_password('bob', 'correct'),
                             paramiko.AUTH_FAILED)
        self.assertIn('Auth attempt limit exceeded', logs.output[0])

    def test_key_budget_bounded_too(self):
        interface = self._interface(key_user=None)
        for _ in range(SSHInterface.MAX_PUBLICKEY_ATTEMPTS):
            interface.check_auth_publickey('bob', object())
        interface.get_user_by_key = lambda u, k: 'right-this-time'
        with self.assertLogs(level='WARNING') as logs:
            self.assertEqual(interface.check_auth_publickey('bob', object()),
                             paramiko.AUTH_FAILED)
        self.assertIn('Public key attempt limit exceeded', logs.output[0])

    def test_resolver_error_fails_closed(self):
        def boom(username, key):
            raise RuntimeError('database is on fire')
        interface = SSHInterface(get_user=lambda u, p: None, get_user_by_key=boom)
        with self.assertLogs(level='ERROR') as logs:
            self.assertEqual(interface.check_auth_publickey('bob', object()),
                             paramiko.AUTH_FAILED)
        self.assertFalse(hasattr(interface, 'user'))
        self.assertIn('Error resolving public key', logs.output[0])


class _FakeSession:
    """Stands in for the SSHInterface the SFTP subsystem is handed."""

    def __init__(self, user):
        self.user = user


class _FlushFails:
    """
    Wraps an open file so that flush() fails the way a full filesystem makes it
    fail, while close() still records that the descriptor was released.
    """

    def __init__(self, wrapped, error):
        self._wrapped = wrapped
        self._error = error
        self.close_called = False

    def flush(self):
        raise self._error

    def close(self):
        self.close_called = True
        self._wrapped.close()

    def __getattr__(self, name):
        return getattr(self._wrapped, name)


class _SFTPInterfaceTestCase(ShareTestBase):

    def interface_for(self, user):
        return sftp_server.SFTPInterface(_FakeSession(user))

    def path(self, subpath='hello.txt', share=None):
        return '/%s/%s' % ((share or self.share).slug_or_id, subpath)

    @contextlib.contextmanager
    def no_cache(self):
        """Run with the memo disabled, as SFTP_PERMISSION_CACHE_SECONDS = 0 does."""
        with mock.patch.object(sftp_server, 'SFTP_PERMISSION_CACHE_SECONDS', 0):
            yield


class TestPermissionCaching(_SFTPInterfaceTestCase):
    """
    Permissions used to be read from guardian on every open() and every
    operation behind permissions_required, so a bulk transfer cost one query
    per file. See SFTP_PERMISSION_CACHE_SECONDS.
    """

    def test_repeated_lookups_do_not_re_query(self):
        interface = self.interface_for(self.writer)
        interface._get_bioshare_path_permissions(self.path())
        # The point of the change: opening 500 more files costs no queries.
        with self.assertNumQueries(0):
            for _ in range(500):
                interface._get_bioshare_path_permissions(self.path())

    def test_a_zero_window_disables_the_memo_entirely(self):
        with self.no_cache():
            interface = self.interface_for(self.writer)
            self.assertIn(Share.PERMISSION_WRITE,
                          interface._get_bioshare_path_permissions(self.path()))
            remove_perm(Share.PERMISSION_WRITE, self.writer, self.share)
            self.assertNotIn(Share.PERMISSION_WRITE,
                             interface._get_bioshare_path_permissions(self.path()))

    def test_a_revocation_inside_the_window_is_not_seen_until_it_expires(self):
        """
        The cost of caching, asserted rather than left to folklore: a
        permission revoked mid-session keeps working for up to
        SFTP_PERMISSION_CACHE_SECONDS. Locking the share is the immediate
        escape hatch -- see TestLockStateFreshness.
        """
        interface = self.interface_for(self.writer)
        self.assertIn(Share.PERMISSION_WRITE,
                      interface._get_bioshare_path_permissions(self.path()))

        remove_perm(Share.PERMISSION_WRITE, self.writer, self.share)

        # Still granted, because the window has not passed.
        self.assertIn(Share.PERMISSION_WRITE,
                      interface._get_bioshare_path_permissions(self.path()))
        # Gone as soon as it has.
        with self.no_cache():
            self.assertNotIn(Share.PERMISSION_WRITE,
                             interface._get_bioshare_path_permissions(self.path()))

    def test_narrowing_one_result_does_not_narrow_the_next(self):
        """
        _get_bioshare_path_permissions strips WRITE and DELETE in place for
        paths that aren't real. Were it handed the cached list itself, that
        removal would persist, and one request for a path under a symlink would
        silently strip write access for the rest of the session.
        """
        interface = self.interface_for(self.writer)
        interface._share_permissions(self.share).remove(Share.PERMISSION_WRITE)
        self.assertIn(Share.PERMISSION_WRITE,
                      interface._share_permissions(self.share))

    def test_each_share_is_memoised_separately(self):
        second = self.make_share(self.owner, name='Second')
        self.grant(self.writer, Share.PERMISSION_VIEW, share=second)
        self.write_share_file('other.txt', share=second)
        interface = self.interface_for(self.writer)

        self.assertIn(Share.PERMISSION_WRITE,
                      interface._get_bioshare_path_permissions(self.path()))
        self.assertNotIn(Share.PERMISSION_WRITE,
                         interface._get_bioshare_path_permissions(
                             self.path('other.txt', share=second)))


class TestLockStateFreshness(_SFTPInterfaceTestCase):
    """
    A session's Share objects are loaded once at connect time, so before
    _refresh_lock_state an administrator locking a share had no effect at all
    on a transfer already in progress.
    """

    def lock_in_database(self):
        """Lock without touching the session's in-memory Share, as the web UI does."""
        Share.objects.filter(id=self.share.id).update(locked=True)

    def test_a_share_locked_mid_session_stops_being_served(self):
        interface = self.interface_for(self.writer)
        self.assertTrue(interface._get_share(self.path()))
        self.lock_in_database()
        with self.no_cache():
            with self.assertRaises(PermissionDenied):
                interface._get_share(self.path())

    def test_locking_overrides_a_still_warm_permission_memo(self):
        interface = self.interface_for(self.writer)
        interface._get_bioshare_path_permissions(self.path())
        self.lock_in_database()
        with self.no_cache():
            with self.assertRaises(PermissionDenied):
                interface._get_bioshare_path_permissions(self.path())

    def test_the_lock_flag_is_not_re_read_on_every_operation(self):
        interface = self.interface_for(self.writer)
        interface._get_share(self.path())
        with self.assertNumQueries(0):
            for _ in range(100):
                interface._get_share(self.path())

    def test_a_share_deleted_mid_session_is_denied(self):
        interface = self.interface_for(self.writer)
        interface._get_share(self.path())
        Share.objects.filter(id=self.share.id).delete()

        with self.no_cache():
            with self.assertLogs(level='WARNING') as logs:
                with self.assertRaises(PermissionDenied):
                    interface._get_share(self.path())
        self.assertIn('Share disappeared', logs.output[0])


class TestUploadBuffering(_SFTPInterfaceTestCase):
    """
    Writes are no longer flushed per block (SFTP_WRITE_BUFFER_SIZE), which
    moves the reporting of a failed write from the write to the close.
    """

    def open_handle(self, subpath, flags, user=None):
        interface = self.interface_for(user or self.writer)
        handle = interface.open(self.path(subpath), flags, None)
        self.assertNotIsInstance(handle, int, 'open() failed: %r' % (handle,))
        return handle

    def open_for_write(self, subpath='upload.bin'):
        handle = self.open_handle(subpath, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
        return handle, os.path.join(self.share.get_path(), subpath)

    def test_blocks_are_buffered_rather_than_written_straight_through(self):
        handle, real_path = self.open_for_write()
        for i in range(4):
            self.assertEqual(handle.write(i * 32768, b'x' * 32768), SFTP_OK)
        self.assertEqual(os.path.getsize(real_path), 0)
        handle.close()
        self.assertEqual(os.path.getsize(real_path), 4 * 32768)

    def test_a_block_larger_than_the_buffer_still_lands(self):
        handle, real_path = self.open_for_write()
        payload = b'y' * (sftp_server.SFTP_WRITE_BUFFER_SIZE * 2)
        self.assertEqual(handle.write(0, payload), SFTP_OK)
        handle.close()
        with open(real_path, 'rb') as f:
            self.assertEqual(f.read(), payload)

    def test_fstat_on_the_handle_accounts_for_buffered_bytes(self):
        """A client checking its own upload's size must not see it lag."""
        handle, _ = self.open_for_write()
        handle.write(0, b'z' * 1024)
        self.assertEqual(handle.stat().st_size, 1024)
        handle.close()

    def test_a_failed_flush_on_close_is_reported_and_logged(self):
        """
        paramiko answers CMD_CLOSE with SFTP_OK unless close() raises, so
        swallowing this would report a truncated upload as a complete one.
        """
        handle, _ = self.open_for_write()
        handle.write(0, b'w' * 1024)
        handle.readfile = handle.writefile = _FlushFails(
            handle.writefile, OSError(errno.ENOSPC, 'No space left on device'))

        with self.assertLogs(level='ERROR') as logs:
            with self.assertRaises(OSError):
                handle.close()

        self.assertIn('upload.bin', logs.output[0])
        self.assertIn('No space left', logs.output[0])
        # The descriptor is released even though the flush failed.
        self.assertTrue(handle.writefile.close_called)

    def test_uploads_are_buffered_above_the_client_block_size(self):
        """
        Python writes anything larger than the buffer straight to the fd, so
        this only pays off while the buffer exceeds the client's block size --
        which is why dropping the per-block flush() on its own changed nothing.
        """
        self.assertGreater(sftp_server.SFTP_WRITE_BUFFER_SIZE, 32768)

    def test_downloads_keep_pythons_default_buffer(self):
        """
        A large read buffer means readahead, which would multiply the cost of
        the scattered small reads sshfs and rclone's VFS layer make.
        """
        buffering = []
        real_fdopen = os.fdopen

        def record(fd, mode, *args):
            if mode in ('rb', 'wb'):
                buffering.append((mode, args[0] if args else None))
            return real_fdopen(fd, mode, *args)

        with mock.patch.object(sftp_server.os, 'fdopen', record):
            self.open_handle('hello.txt', os.O_RDONLY, user=self.downloader).close()
            self.open_for_write()[0].close()

        self.assertEqual(buffering,
                         [('rb', -1), ('wb', sftp_server.SFTP_WRITE_BUFFER_SIZE)])


class TestSessionTeardown(_SFTPInterfaceTestCase):

    def test_one_failing_handle_does_not_strand_the_others(self):
        """
        A full filesystem fails every session's flush at once, and paramiko
        closes the handle table in a bare loop (sftp_server.py:172-175) that the
        first raising handle aborts -- leaving every later handle's descriptor
        open, which is the exhaustion SFTP_MAX_SESSIONS exists to prevent.
        """
        interface = self.interface_for(self.writer)
        handles = []
        for name in ('a.bin', 'b.bin', 'c.bin'):
            handle = interface.open(self.path(name), os.O_WRONLY | os.O_CREAT, None)
            self.assertNotIsInstance(handle, int, 'open() failed: %r' % (handle,))
            handle.write(0, b'data')
            handles.append(handle)

        broken = handles[1]
        broken.readfile = broken.writefile = _FlushFails(
            broken.writefile, OSError(errno.ENOSPC, 'No space left on device'))

        # Bypass SFTPServer.__init__; only these three attributes are touched,
        # plus the channel SubsystemHandler.finish_subsystem closes (name-mangled
        # because it is set in that class's own __init__).
        server = sftp_server.SFTPServer.__new__(sftp_server.SFTPServer)
        server.server = mock.Mock()
        server._SubsystemHandler__channel = mock.Mock()
        server.file_table = {str(i): h for i, h in enumerate(handles)}
        server.folder_table = {}

        with self.assertLogs(level='ERROR') as logs:
            sftp_server._SFTPServer_finish_subsystem(server)

        self.assertTrue(any('Error closing an SFTP handle' in line
                            for line in logs.output), logs.output)
        self.assertTrue(handles[0].writefile.closed)
        self.assertTrue(handles[2].writefile.closed)
        self.assertTrue(broken.writefile.close_called)
        self.assertEqual(server.file_table, {})


class _CloseMessage:
    """The CMD_CLOSE payload paramiko hands _process: just a handle."""

    def __init__(self, handle):
        self.handle = handle

    def get_binary(self):
        return self.handle


class TestCloseStatus(_SFTPInterfaceTestCase):
    """
    Since writes stopped being flushed per block, close() is where a failed
    upload surfaces -- so the close response is the client's only report, and
    it has to carry the reason. See _SFTPServer_process.
    """

    def sftp_server(self):
        server = sftp_server.SFTPServer.__new__(sftp_server.SFTPServer)
        server.file_table = {}
        server.folder_table = {}
        server.sent = []
        server._send_status = lambda number, code, desc=None: server.sent.append((code, desc))
        return server

    def open_upload(self, subpath='upload.bin'):
        interface = self.interface_for(self.writer)
        handle = interface.open(self.path(subpath), os.O_WRONLY | os.O_CREAT, None)
        self.assertNotIsInstance(handle, int, 'open() failed: %r' % (handle,))
        handle.write(0, b'payload')
        return handle

    def close_through_process(self, server, handle):
        server.file_table[b'H'] = handle
        sftp_server._SFTPServer_process(server, CMD_CLOSE, 1, _CloseMessage(b'H'))

    def test_a_clean_close_still_reports_success(self):
        server = self.sftp_server()
        self.close_through_process(server, self.open_upload())
        self.assertEqual(server.sent, [(SFTP_OK, None)])

    def test_a_full_filesystem_reports_why_not_just_failure(self):
        """
        SFTP v3 has no status code for ENOSPC, so the code is SFTP_FAILURE
        either way -- but the description is what rclone prints, and 'Failure'
        alone sends the operator to the server log.
        """
        handle = self.open_upload()
        handle.readfile = handle.writefile = _FlushFails(
            handle.writefile, OSError(errno.ENOSPC, 'No space left on device'))

        server = self.sftp_server()
        with self.assertLogs(level='ERROR'):
            self.close_through_process(server, handle)

        self.assertEqual(server.sent, [(SFTP_FAILURE, 'No space left on device')])

    def test_the_errno_still_selects_the_status_code(self):
        handle = self.open_upload()
        handle.readfile = handle.writefile = _FlushFails(
            handle.writefile, OSError(errno.EACCES, 'Permission denied'))

        server = self.sftp_server()
        with self.assertLogs(level='ERROR'):
            self.close_through_process(server, handle)

        self.assertEqual(server.sent, [(SFTP_PERMISSION_DENIED, 'Permission denied')])

    def test_a_failed_close_does_not_leave_the_handle_behind(self):
        """
        paramiko's version deletes the handle only after close() returns, so a
        close that raised left it in the table for finish_subsystem to close a
        second time.
        """
        handle = self.open_upload()
        handle.readfile = handle.writefile = _FlushFails(
            handle.writefile, OSError(errno.ENOSPC, 'No space left on device'))

        server = self.sftp_server()
        with self.assertLogs(level='ERROR'):
            self.close_through_process(server, handle)

        self.assertEqual(server.file_table, {})
        self.assertTrue(handle.writefile.close_called)

    def test_an_unknown_handle_is_rejected(self):
        server = self.sftp_server()
        sftp_server._SFTPServer_process(server, CMD_CLOSE, 1, _CloseMessage(b'nope'))
        self.assertEqual(server.sent, [(SFTP_BAD_MESSAGE, 'Invalid handle')])

    def test_every_other_request_is_left_to_paramiko(self):
        server = self.sftp_server()
        with mock.patch.object(sftp_server, '_SFTPServer_process_original') as original:
            for opcode in (CMD_CLOSE + 1, CMD_CLOSE + 2):
                sftp_server._SFTPServer_process(server, opcode, 1, _CloseMessage(b'x'))
        self.assertEqual(original.call_count, 2)
        self.assertEqual(server.sent, [])


def attrs(mtime=None, mode=None, size=None, atime=None):
    """Build the SFTPAttributes a client sends with SETSTAT / FSETSTAT."""
    attr = paramiko.SFTPAttributes()
    attr._flags = 0
    if mtime is not None:
        attr.st_atime = atime if atime is not None else mtime
        attr.st_mtime = mtime
        attr._flags |= attr.FLAG_AMTIME
    if mode is not None:
        attr.st_mode = mode
        attr._flags |= attr.FLAG_PERMISSIONS
    if size is not None:
        attr.st_size = size
        attr._flags |= attr.FLAG_SIZE
    return attr


A_TIME = 1400000000  # 2014-05-13, safely distinct from anything the tests create


class TestSetModificationTime(_SFTPInterfaceTestCase):
    """
    Refusing CMD_SETSTAT outright made the server unusable with rclone, which
    sets the modtime after every upload and discards the transfer if it fails.
    """

    def real(self, subpath='hello.txt'):
        return os.path.join(self.share.get_path(), subpath)

    def test_a_client_can_set_the_modification_time(self):
        interface = self.interface_for(self.writer)
        self.assertEqual(interface.chattr(self.path(), attrs(mtime=A_TIME)), SFTP_OK)
        self.assertEqual(int(os.stat(self.real()).st_mtime), A_TIME)

    def test_the_access_time_comes_along(self):
        interface = self.interface_for(self.writer)
        interface.chattr(self.path(), attrs(mtime=A_TIME, atime=A_TIME + 60))
        self.assertEqual(int(os.stat(self.real()).st_atime), A_TIME + 60)

    def test_it_requires_write_permission(self):
        """Setting an mtime is a modification, so view alone must not do it."""
        before = os.stat(self.real()).st_mtime
        interface = self.interface_for(self.downloader)
        self.assertEqual(interface.chattr(self.path(), attrs(mtime=A_TIME)),
                         SFTP_PERMISSION_DENIED)
        self.assertEqual(os.stat(self.real()).st_mtime, before)

    def test_a_bare_chmod_is_still_refused(self):
        """
        Shares have their own ownership and mode conventions that the web
        application depends on. Reporting OK for a chmod we did not perform
        would be worse than refusing it.
        """
        before = os.stat(self.real()).st_mode
        interface = self.interface_for(self.writer)
        self.assertEqual(interface.chattr(self.path(), attrs(mode=0o777)),
                         SFTP_OP_UNSUPPORTED)
        self.assertEqual(os.stat(self.real()).st_mode, before)

    def test_a_mode_alongside_an_mtime_does_not_fail_the_request(self):
        """
        `sftp -p` sends both. Failing the whole transfer over the half we
        decline would repeat the mistake that broke rclone.
        """
        before = os.stat(self.real()).st_mode
        interface = self.interface_for(self.writer)
        self.assertEqual(interface.chattr(self.path(), attrs(mtime=A_TIME, mode=0o777)),
                         SFTP_OK)
        self.assertEqual(int(os.stat(self.real()).st_mtime), A_TIME)
        self.assertEqual(os.stat(self.real()).st_mode, before)

    def test_a_size_is_refused_rather_than_ignored(self):
        """
        set_file_attr implements a size change as open(filename, 'w+'), which
        truncates. Silently returning OK for a truncate that did not happen
        would be a lie the client can act on.
        """
        interface = self.interface_for(self.writer)
        self.assertEqual(interface.chattr(self.path(), attrs(size=0)),
                         SFTP_OP_UNSUPPORTED)
        self.assertEqual(os.path.getsize(self.real()), len(b'Hello bioshare!\n'))

    def test_a_size_is_refused_even_alongside_an_mtime(self):
        interface = self.interface_for(self.writer)
        self.assertEqual(interface.chattr(self.path(), attrs(mtime=A_TIME, size=0)),
                         SFTP_OP_UNSUPPORTED)
        self.assertEqual(os.path.getsize(self.real()), len(b'Hello bioshare!\n'))

    def test_a_locked_share_still_refuses(self):
        interface = self.interface_for(self.writer)
        Share.objects.filter(id=self.share.id).update(locked=True)
        with self.no_cache():
            self.assertEqual(interface.chattr(self.path(), attrs(mtime=A_TIME)),
                             SFTP_PERMISSION_DENIED)


class TestSetModificationTimeOnAnOpenHandle(_SFTPInterfaceTestCase):
    """
    CMD_FSETSTAT is routed straight to the handle without going near the share
    (paramiko sftp_server.py:489-499), so the handle is the only place
    authorisation can be checked -- and it never was.
    """

    def real(self, subpath='hello.txt'):
        return os.path.join(self.share.get_path(), subpath)

    def open_as(self, user, flags=os.O_RDONLY, subpath='hello.txt'):
        handle = self.interface_for(user).open(self.path(subpath), flags, None)
        self.assertNotIsInstance(handle, int, 'open() failed: %r' % (handle,))
        return handle

    def test_a_writer_can_set_the_modification_time(self):
        handle = self.open_as(self.writer, os.O_WRONLY | os.O_CREAT)
        self.assertEqual(handle.chattr(attrs(mtime=A_TIME)), SFTP_OK)
        handle.close()
        self.assertEqual(int(os.stat(self.real()).st_mtime), A_TIME)

    def test_a_read_only_handle_cannot_truncate_the_file(self):
        """
        The hole this closes: opening for reading needs only view + download,
        and FSETSTAT with a size reached set_file_attr, which truncates. A user
        with no write permission could empty any file they could download.
        """
        handle = self.open_as(self.downloader)
        self.assertEqual(handle.chattr(attrs(size=0)), SFTP_PERMISSION_DENIED)
        handle.close()
        self.assertEqual(os.path.getsize(self.real()), len(b'Hello bioshare!\n'))

    def test_a_read_only_handle_cannot_chmod_the_file(self):
        before = os.stat(self.real()).st_mode
        handle = self.open_as(self.downloader)
        self.assertEqual(handle.chattr(attrs(mode=0o777)), SFTP_PERMISSION_DENIED)
        handle.close()
        self.assertEqual(os.stat(self.real()).st_mode, before)

    def test_a_read_only_handle_cannot_set_the_modification_time_either(self):
        before = os.stat(self.real()).st_mtime
        handle = self.open_as(self.downloader)
        self.assertEqual(handle.chattr(attrs(mtime=A_TIME)), SFTP_PERMISSION_DENIED)
        handle.close()
        self.assertEqual(os.stat(self.real()).st_mtime, before)

    def test_a_writer_still_cannot_truncate_through_fsetstat(self):
        handle = self.open_as(self.writer, os.O_WRONLY | os.O_CREAT)
        self.assertEqual(handle.chattr(attrs(size=0)), SFTP_OP_UNSUPPORTED)
        handle.close()
        self.assertEqual(os.path.getsize(self.real()), len(b'Hello bioshare!\n'))


class TestRename(_SFTPInterfaceTestCase):
    """
    rclone uploads to <name>.<hash>.partial and renames on completion, so every
    single file in a transfer goes through here.
    """

    def setUp(self):
        super().setUp()
        # rename requires write AND delete; the base writer holds only write.
        self.grant(self.writer, Share.PERMISSION_DELETE)

    def real(self, subpath):
        return os.path.join(self.share.get_path(), subpath)

    def test_a_rename_reports_success(self):
        """
        The regression: rename reassigned oldpath to the real filesystem path
        and then passed it to _path_modified, which re-resolves the share from
        an SFTP path and so went looking for a share called 'data'. os.rename
        had already run, so the file moved and the client was told it had not --
        rclone reported 'partial file rename failed' for every file in the
        transfer.
        """
        interface = self.interface_for(self.writer)
        self.write_share_file('upload.partial', b'contents')
        result = interface.rename(self.path('upload.partial'), self.path('upload.txt'))
        self.assertEqual(result, SFTP_OK)
        self.assertTrue(os.path.exists(self.real('upload.txt')))
        self.assertFalse(os.path.exists(self.real('upload.partial')))

    def test_a_rename_is_logged_against_the_share(self):
        interface = self.interface_for(self.writer)
        self.write_share_file('upload.partial', b'contents')
        interface.rename(self.path('upload.partial'), self.path('upload.txt'))

        log = ShareLog.objects.filter(share=self.share,
                                      action=ShareLog.ACTION_RENAMED).last()
        self.assertIsNotNone(log, 'no ShareLog written')
        self.assertIn('upload.partial', log.text)
        self.assertIn('upload.txt', log.text)
        # The subpath within the share, not /data/shares/<id>/... -- a real
        # filesystem path is what the bug would have recorded here.
        self.assertEqual(log.paths, ['upload.partial'])

    def test_a_rename_updates_the_share_modified_date(self):
        was = timezone.now() - datetime.timedelta(days=1)
        Share.objects.filter(id=self.share.id).update(updated=was)

        interface = self.interface_for(self.writer)
        self.write_share_file('upload.partial', b'contents')
        interface.rename(self.path('upload.partial'), self.path('upload.txt'))

        self.share.refresh_from_db()
        self.assertGreater(self.share.updated, was)

    def test_renaming_into_a_share_without_write_is_refused(self):
        elsewhere = self.make_share(self.other, name='Someone elses share')
        self.grant(self.writer, Share.PERMISSION_VIEW, share=elsewhere)
        interface = self.interface_for(self.writer)
        self.write_share_file('upload.partial', b'contents')

        result = interface.rename(self.path('upload.partial'),
                                  self.path('landing.txt', share=elsewhere))

        self.assertEqual(result, SFTP_PERMISSION_DENIED)
        self.assertTrue(os.path.exists(self.real('upload.partial')))
        self.assertFalse(os.path.exists(
            os.path.join(elsewhere.get_path(), 'landing.txt')))

    def test_renaming_something_that_is_not_there(self):
        interface = self.interface_for(self.writer)
        result = interface.rename(self.path('nope.partial'), self.path('nope.txt'))
        self.assertEqual(result, paramiko.SFTP_NO_SUCH_FILE)

    def test_a_read_only_session_cannot_rename(self):
        interface = self.interface_for(self.downloader)
        self.write_share_file('upload.partial', b'contents')
        self.assertEqual(
            interface.rename(self.path('upload.partial'), self.path('upload.txt')),
            SFTP_PERMISSION_DENIED)
        self.assertTrue(os.path.exists(self.real('upload.partial')))


class TestUnknownShareIsDenied(_SFTPInterfaceTestCase):

    def test_an_unknown_share_is_denied_not_reported_as_a_server_fault(self):
        """
        The message this raises never formatted: a stray '}' made str.format
        raise ValueError, which sftp_response did not catch, so paramiko's
        catch-all answered SFTP_FAILURE. A path naming a share the session
        cannot see came back as a server fault rather than a denial -- and it is
        what turned the rename bug into an opaque 'Failure'.
        """
        interface = self.interface_for(self.writer)
        with self.assertLogs(level='WARNING'):
            with self.assertRaises(PermissionDenied):
                interface._get_share('/data/shares/somewhere/else')

    def test_the_denial_names_the_share_it_could_not_find(self):
        interface = self.interface_for(self.writer)
        with self.assertLogs(level='WARNING'):
            with self.assertRaises(PermissionDenied) as caught:
                interface._get_share('/nosuchshare/file.txt')
        self.assertIn('nosuchshare', str(caught.exception))


class TestUnexpectedErrorsAreLogged(_SFTPInterfaceTestCase):

    def test_an_unexpected_exception_is_logged_and_reported(self):
        """
        paramiko answers SFTP_FAILURE for anything that escapes an operation,
        but logs the traceback at DEBUG while start_sftp runs the root logger at
        INFO. Thousands of failed renames left nothing on the server to diagnose
        them by.
        """
        interface = self.interface_for(self.owner)
        with mock.patch.object(sftp_server.SFTPInterface, '_realpath',
                               side_effect=ValueError('something unforeseen')):
            with self.assertLogs(level='ERROR') as logs:
                result = interface.remove(self.path())

        self.assertEqual(result, SFTP_FAILURE)
        self.assertIn('Unhandled error in SFTP remove', logs.output[0])
        self.assertIn('something unforeseen', logs.output[0])

    def test_ordinary_denials_are_not_logged_as_errors(self):
        """A denial is a normal outcome, not a server fault."""
        interface = self.interface_for(self.downloader)
        with self.assertLogs(level='ERROR') as logs:
            # assertLogs fails outright with no records, so emit one of our own
            # and assert nothing joined it.
            logging.getLogger().error('sentinel')
            self.assertEqual(interface.remove(self.path()), SFTP_PERMISSION_DENIED)
        self.assertEqual(len(logs.output), 1, logs.output)
