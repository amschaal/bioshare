#!/usr/bin/env python
import logging
import os

from server import SFTPServer


SSH_PORT = 2222

# development_root = os.path.join(os.path.dirname(__file__), 'tmp')
# FILE_ROOT = os.path.realpath(os.environ.get(
#         'FILESERVER_ROOT', development_root))
FILE_ROOT='/tmp'
# Note, you can generate a new host key like this:
# ssh-keygen -t rsa -N '' -f host_key
HOST_KEY = '/tmp/host_key'#os.path.join(os.path.dirname(__file__), 'config/host_key')
# PERMISSIONS_FILE = os.path.join(os.path.dirname(__file__), 'config/permissions.ini')


def run_server():
    logging.basicConfig(level=logging.INFO)
#     permissions = read_permissions_file(PERMISSIONS_FILE)
#     ldap_auth = LDAPAuth(AUTH_LDAP_SERVER_URI,
#         bind_dn=AUTH_LDAP_BIND_DN,
#         bind_password=AUTH_LDAP_BIND_PASSWORD,
#         base_dn=LDAP_ROOT_DN,
#         group_dn=LDAP_GROUP_ROOT_DN)
#     manager = PermissionsManager(permissions,
#             required_group=REQUIRED_GROUP,
#             authenticate=ldap_auth)
    server = SFTPServer(HOST_KEY)#, get_user=manager.get_user
    server.serve_forever('0.0.0.0', SSH_PORT)

if __name__ == '__main__':
    run_server()