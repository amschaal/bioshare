#!/usr/bin/env python
import os
import sys
import re
import logging
import urllib2
import json
from os.path import join

ORIGINAL_COMMAND = None
USER = None
TEST = False
PERMISSIONS = {}
SHARE_META = {}
WRITE_PERMISSIONS = ['write_to_share','delete_share_files']
READ_PERMISSIONS = ['download_share_files']



import ConfigParser
config = ConfigParser.ConfigParser()
config.read('sshwrapper.config')

# r = re.compile('^hg -R (S%2B) serve --stdio$')
# match = re.search(r, os.environ['SSH_ORIGINAL_COMMAND'])
# if match:
#     repo_path = match.groups()[0]
#     if os.path.exists(repo_path):
#         os.execvp('hg', ['hg', '-R', repo_path, 'serve', '--stdio'])

# class WrapperException(Exception):
#     """Basically just the base Exception class"""

class WrapperException(Exception):
    pass

def get_token_data(token_file):
    import ConfigParser
    config = ConfigParser.ConfigParser()
    config.read(token_file)
    directory = config.get('details','directory')
    user = config.get('details','user')
    return {'directory':directory,'user':user}

def get_permissions(username,share):
    if not PERMISSIONS.has_key(share):
        url  = config.get('config','perm_api_url') % (share,username)
        response = urllib2.urlopen(url)
        response = json.load(response)
        PERMISSIONS[share]= response['permissions']
    return PERMISSIONS[share]

def get_share_meta(share):
#     try:
    if not SHARE_META.has_key(share):
        url  = config.get('config','metadata_api_url') % (share)
        response = urllib2.urlopen(url)
        response = json.load(response)
        SHARE_META[share]= response
    return SHARE_META[share]
#     except WrapperException, e:
#         raise e
#     except Exception, e: 
#         raise WrapperException('Illegal subpath: %s' % matches['subpath'])

def can_write(username,share):
    perms = get_permissions(username,share)
    for perm in WRITE_PERMISSIONS:
        if perm not in perms:
            return False
    return True

def can_read(username,share):
    perms = get_permissions(username,share)
    for perm in READ_PERMISSIONS:
        if perm not in perms:
            return False
    return True

def analyze_path(path):
#     print path
    match = re.match('/(?P<share>[a-zA-Z0-9]{15})(?:/(?P<subpath>.*))', path)
    try:
        matches = match.groupdict()
        if not matches.has_key('share'):
            raise WrapperException('analyze_path: Bad key: %s' % path)
        share_path = get_share_meta(matches['share'])['path']
        if matches.has_key('subpath'):
#             print matches['subpath']
            if '..' in matches['subpath']:
                raise WrapperException('Illegal subpath: %s' % matches['subpath'])
        if matches.has_key('subpath'):
            path = join(share_path,  match.group('subpath'))
        else:
            path = share_path
        return {'share':matches['share'],'path':path}
    except WrapperException, e:
        raise e
    except Exception, e:
        raise Exception('analyze_path: Bad path: %s, %s' % (path,str(e)))

def handle_rsync(parts):
    try:
        paths_data = [analyze_path(path) for path in parts[parts.index('.')+1:]]
        paths = [path_data['path'] for path_data in paths_data]
        shares = [path_data['share'] for path_data in paths_data]
        if '--sender' in parts:#server->client
            for share in shares:
                if not can_read(USER, share):
                    raise WrapperException('User %s cannot read from share %s' % (USER,share))
            command = ['rsync', '--server', '--sender', '-vrzte.iLsf', '.'] + paths
        else:#client->server
            # --no-p --no-g --chmod=ugo=rwX  //destination default permissions
            for share in shares:
                if not can_write(USER, share):
                    raise WrapperException('User %s cannot write to share %s' % (USER,share))
            command = ['rsync', '--server', '-vrtze.iLsf', '.'] + paths
#             command = parts[:4]+paths
        if TEST:
            logger.info('running rsync command: %s' % ', '.join(command))
            print command
        else:
            logger.info('running rsync command: %s' % ', '.join(command))
            os.execvp('rsync', command)
    except Exception, e:
        print >> sys.stderr, 'handle_rsync exception: %s' % str(e)
        logger.info('handle_rsync exception: %s' % str(e))
        
def handle_ls(parts):
    path_data = analyze_path(parts[1])
    if path_data is not None:
        if can_read(USER, path_data['share']):
            command = ['ls', path_data['path']]
#             if TEST:
#                 print command
#             else:
            os.execvp('ls', command)
        else:
            logger.info( 'ls: Permission denied')
    else:
        logger.info( 'ls: Bad command')

def main():
    try:
        import shlex
        parts = shlex.split(ORIGINAL_COMMAND)
        logger.info('SSH_ORIGINAL_COMMAND: '+ORIGINAL_COMMAND)
        logger.info('SPLIT: '+', '.join(parts))
        if parts[0] == 'rsync':
            handle_rsync(parts)
        elif parts[0] == 'ls':
            handle_ls(parts)
        else:
            logger.info( 'Unsupported command: %s' % parts[0])
    #     os.execvp('ls', ['ls', '/var/www'])
    except Exception, e:
        logger.error('Bad or missing parameter "SSH_ORIGINAL_COMMAND"')



if __name__ == '__main__':
    #Should probably use argument parsing library, but trying to keep dependencies to a minimum
    
    if len(sys.argv)==2:
        USER = sys.argv[1]
    elif len(sys.argv)==3:
        USER = sys.argv[1]
        ORIGINAL_COMMAND = sys.argv[2] #for testing: ssh-wrapper.py username 'rsync /local/file remote:/TOKEN/subdir
        TEST = True
    if ORIGINAL_COMMAND is None:
        ORIGINAL_COMMAND = os.environ['SSH_ORIGINAL_COMMAND']
    logger = logging.getLogger('bioshare')
    hdlr = logging.FileHandler('/var/log/sshwrapper.log')
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr) 
    logger.setLevel(logging.INFO)
    logger.info('user: %s' % USER)
    logger.info('command: %s' % ORIGINAL_COMMAND)
    main()
