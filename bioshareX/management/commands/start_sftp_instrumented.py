#!/usr/bin/env python
"""
start_sftp, plus a count of how many permission lookups actually reach the
database. For benchmarking plan §3 -- do not run this in production.

Wall-clock from tools/sftp_benchmark.py is noisy: it moves with network, disk
and whatever else the box is doing. The query count is not, which makes it the
measurement that actually settles whether the memo works. Before
SFTP_PERMISSION_CACHE_SECONDS, transferring the 50k-file corpus made on the
order of 50,000 lookups; after, it should be roughly one per share per interval.

    manage.py start_sftp_instrumented --report-interval 10

Counts are logged through the same handlers start_sftp sets up, so they land in
SFTP_LOG_FILE alongside everything else:

    2026-08-24 11:03:12 INFO root [benchmark] permission lookups: 4 (+4 in 10s)

Two counters are reported. "lookups" is calls that reached
SharePermissions.get_user_permissions, i.e. real guardian queries. "requests" is
calls to SFTPInterface._share_permissions, i.e. what the daemon asked for. The
gap between them is what the memo saved.
"""

import logging
import threading
import time

from django.core.management.base import BaseCommand

from bioshareX.management.commands.start_sftp import Command as StartSFTPCommand


class Command(BaseCommand):
    help = 'Start the SFTP server with permission-lookup counters (benchmarking only).'

    def add_arguments(self, parser):
        parser.add_argument('--report-interval', type=int, default=30,
                            help='seconds between log lines (default: 30)')

    def handle(self, *args, **options):
        from bioshareX.permissions import SharePermissions
        from sftp.server import SFTPInterface

        state = {'lookups': 0, 'requests': 0}
        lock = threading.Lock()

        def counting(attr, key, owner):
            original = getattr(owner, attr)

            def wrapper(self, *a, **kw):
                with lock:
                    state[key] += 1
                return original(self, *a, **kw)

            wrapper.__name__ = getattr(original, '__name__', attr)
            wrapper.__doc__ = getattr(original, '__doc__', None)
            setattr(owner, attr, wrapper)

        # Patched before the server starts, so no session can slip past either.
        counting('get_user_permissions', 'lookups', SharePermissions)
        counting('_share_permissions', 'requests', SFTPInterface)

        def report():
            previous = dict(state)
            interval = options['report_interval']
            while True:
                time.sleep(interval)
                with lock:
                    current = dict(state)
                saved = current['requests'] - current['lookups']
                logging.info(
                    '[benchmark] permission lookups: %d (+%d in %ds) | '
                    'requests: %d (+%d) | saved by the memo: %d',
                    current['lookups'], current['lookups'] - previous['lookups'],
                    interval,
                    current['requests'], current['requests'] - previous['requests'],
                    saved)
                previous = current

        # Daemon thread: this must never be what keeps the process alive.
        # It sleeps first, so start_sftp's logging handlers are installed by the
        # time it emits anything.
        threading.Thread(target=report, daemon=True).start()

        logging.warning('SFTP server starting INSTRUMENTED -- benchmarking only, '
                        'not for production use')
        StartSFTPCommand().handle(*args, **options)
