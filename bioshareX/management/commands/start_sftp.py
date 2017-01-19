#!/usr/bin/env python
import logging
import os

from sftp.server import SFTPServer
from django.core.management.base import BaseCommand
from django.conf import settings


SSH_PORT = settings.SFTP_SSH_PORT
# Note, you can generate a new host key like this:
# ssh-keygen -t rsa -N '' -f host_key
HOST_KEY = settings.SFTP_HOST_KEY


class Command(BaseCommand):
    help = 'Start the custom SFTP server.'
    def handle(self, *args, **options):
        logging.basicConfig(level=logging.INFO)
        server = SFTPServer(HOST_KEY)
        server.serve_forever('0.0.0.0', SSH_PORT)