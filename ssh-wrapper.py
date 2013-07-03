#!/usr/bin/env python
import os
import sys
import re
import logging

TOKEN_DIR = '/tmp/tokens'
ORIGINAL_COMMAND = None
TEST = False

# r = re.compile('^hg -R (S%2B) serve --stdio$')
# match = re.search(r, os.environ['SSH_ORIGINAL_COMMAND'])
# if match:
#     repo_path = match.groups()[0]
#     if os.path.exists(repo_path):
#         os.execvp('hg', ['hg', '-R', repo_path, 'serve', '--stdio'])

def get_token_data(token_file):
    import ConfigParser
    config = ConfigParser.ConfigParser()
    config.read(token_file)
    directory = config.get('details','directory')
    user = config.get('details','user')
    return {'directory':directory,'user':user}

def transform_path(path):
    match = re.match('/(?P<token>[a-zA-Z0-9]{10})(?:/(?P<subpath>.*))', path)
    try:
        matches = match.groupdict()
        if not matches.has_key('token'):
            return None
        if matches.has_key('subpath'):
            if '..' in matches['subpath']:
                print 'Illegal subpath: %s' % matches['subpath']
                return None
        token_file = join(TOKEN_DIR,match.group('token'))
        if isfile(token_file):
            data = get_token_data(token_file)
            if match.groupdict().has_key('subpath'):
                return join(data['directory'],match.group('subpath'))
            return data['directory']
        else:
            return None    
    except:
        print 'Bad path: %s' % path
        return None
    

def handle_rsync(parts):
    paths = [transform_path(path) for path in parts[parts.index('.')+1:]]
    if None in paths:
        print 'Bad command'
        return
    if '--sender' in parts:#server->client
        command = ['rsync', '--server', '--sender', '-vogDtprze.iLsf', '.'] + paths
    else:#client->server
        # --no-p --no-g --chmod=ugo=rwX  //destination default permissions
        command = ['rsync', '--server', '-voDtrze.iLsf', '.'] + paths
    if TEST:
        print command
    else:
        os.execvp('rsync', command)
        
def handle_ls(parts):
    path = transform_path(parts[1])
    if path is not None:
        os.execvp('ls', ['ls', path])
    else:
        print 'Bad command'

def main():
    try:
        parts = re.split('\s+',ORIGINAL_COMMAND)
        logger.info('SSH_ORIGINAL_COMMAND: '+ORIGINAL_COMMAND)
        if parts[0] == 'rsync':
            handle_rsync(parts)
        elif parts[0] == 'ls':
            handle_ls(parts)
        else:
            print 'Unsupported command: %s' % parts[0]
    #     os.execvp('ls', ['ls', '/var/www'])
    except Exception, e:
        logger.error('Bad or missing parameter "SSH_ORIGINAL_COMMAND"')



if __name__ == '__main__':
    #Should probably use argument parsing library, but trying to keep dependencies to a minumum
    
    if len(sys.argv)==2:
        user = sys.argv[1]
    elif len(sys.argv)==3:
        user = sys.argv[1]
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
    from os.path import join, isfile
    logger.info('Test message')
    main()
