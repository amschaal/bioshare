#!/usr/bin/env python
import logging
import os

from sftp.server import BioshareSFTPServer
from django.core.management.base import BaseCommand
from django.conf import settings

SSH_PORT = settings.SFTP_SSH_PORT
# Note, you can generate a new host key like this:
# ssh-keygen -t rsa -N '' -f host_key
HOST_KEY = settings.SFTP_HOST_KEY

class _SuppressBannerNoise(logging.Filter):
    """Drop benign 'Error reading SSH protocol banner' records.

    Non-SSH connections (port scanners, TLS/HTTP probes, half-open TCP health
    checks) hitting the public SFTP port make paramiko 3.x fail to decode the
    client banner and log a UnicodeDecodeError traceback at ERROR. These are
    expected internet background noise, not a server fault. Every other
    paramiko.transport record (real handshake/auth/transfer errors) is kept.
    """
    def filter(self, record):
        return 'Error reading SSH protocol banner' not in record.getMessage()

class Command(BaseCommand):
    help = 'Start the custom SFTP server.'
    def handle(self, *args, **options):
        logging.basicConfig(level=logging.INFO)
        logging.getLogger('paramiko.transport').addFilter(_SuppressBannerNoise())
        server = BioshareSFTPServer(HOST_KEY)
        server.serve_forever('0.0.0.0', SSH_PORT)