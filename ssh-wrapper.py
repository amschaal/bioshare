#!/usr/bin/env python
import os
import re
import logging
logger = logging.getLogger('bioshare')
hdlr = logging.FileHandler('/var/log/sshwrapper.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr) 
logger.setLevel(logging.INFO)

logger.info('Test message')
try:
    logger.info('SSH_ORIGINAL_COMMAND: '+os.environ['SSH_ORIGINAL_COMMAND'])
    os.execvp('ls', ['ls', '/var/www'])
except Exception, e:
    logger.error('Bad or missing parameter "SSH_ORIGINAL_COMMAND"')
# r = re.compile('^hg -R (S%2B) serve --stdio$')
# match = re.search(r, os.environ['SSH_ORIGINAL_COMMAND'])
# if match:
#     repo_path = match.groups()[0]
#     if os.path.exists(repo_path):
#         os.execvp('hg', ['hg', '-R', repo_path, 'serve', '--stdio'])