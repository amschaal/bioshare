"""
Tests for the paramiko SFTP daemon in sftp/server.py.

Two concerns are covered here:

  * **Availability** -- the accept loop in ``BioshareSFTPServer.serve_forever``
    is the single acceptor for the whole daemon, and ``startup.sh`` backgrounds
    it with no supervisor, so anything that escapes it takes SFTP down for every
    user until the container restarts. These tests drive the loop with a fake
    listening socket and assert it survives, cleans up, and enforces its
    session ceiling.

  * **Public key authentication** -- that a stored SSHKey admits its owner, that
    nothing else does, and that the per-method attempt budgets don't lock out a
    legitimate client.

They live in bioshareX/ rather than sftp/ so ``manage.py test bioshareX`` picks
them up; the sftp package is not in INSTALLED_APPS.

Run with:  python manage.py test bioshareX.test_sftp
"""

import base64
import contextlib
import errno
from unittest import mock

import paramiko
from django.test import TestCase

from bioshareX.models import SSHKey
from bioshareX.test_base import ShareTestBase, make_public_key
from sftp import server as sftp_server
from sftp.server import BioshareSFTPServer, SSHInterface


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
        """A row predating validation must not break auth for the good key."""
        SSHKey.objects.create(user=self.owner, name='legacy', key='garbage')
        with self.assertLogs(level='WARNING') as logs:
            user = self.server.get_user_by_key(self.owner.username,
                                               _PresentedKey(self.key_line))
        self.assertEqual(user, self.owner)
        self.assertIn('unparseable stored SSH key', logs.output[0])

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
