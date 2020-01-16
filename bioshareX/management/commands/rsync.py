from django.core.management.base import BaseCommand
from bioshareX.models import Share
import os, re, logging, argparse
from bioshareX.utils import get_setting, test_path
from django.contrib.auth.models import User
import sys
from os.path import join
from django.utils import timezone

class WrapperException(Exception):
    pass

class Command(BaseCommand):
    help = 'Wrap rsync commands'
    logger = None
    requires_system_checks = False
    def get_flags(self,args):
        parser = argparse.ArgumentParser(description='Parse rsync command')
        parser.add_argument('-z', action="store_true", default=False)
        parser.add_argument('-t', action="store_true", default=False)
        parser.add_argument('-v', action="store_true", default=False)
        parser.add_argument('-r', action="store_true", default=False)
        parser.add_argument('-c', action="store_true", default=False) #allow user to use checksums
        parser.add_argument('-e')
        parsed = parser.parse_known_args(args)
        flags =  ''.join([flag for flag in 'vrztc' if getattr(parsed[0],flag)])
        return '-%se.iLsf'%flags
    def add_arguments(self, parser):
        parser.add_argument('user')
    def log(self,message,level='info'):
        if self.logger:
            if level == 'info':
                self.logger.info(message)
            elif level == 'error':
                self.logger.error(message)
    def analyze_path(self, path):
        match = re.match('/(?P<share>[a-zA-Z0-9]{15})(?:/(?P<subpath>.*))', path)
        try:
            matches = match.groupdict()
            if not matches.has_key('share'):
                raise WrapperException('analyze_path: Bad key: %s' % path)
            share = Share.objects.get(id=matches['share'])
#             share_path = get_share_meta(matches['share'])['path']
            if matches.has_key('subpath'):
                try:
                    test_path(matches['subpath'])
                except:
                    raise WrapperException('Illegal subpath: %s' % matches['subpath'])
                path = join(share.get_path(),  match.group('subpath'))
            else:
                path = share.get_path()
            return {'share':share,'path':path}
        except WrapperException, e:
            raise e
        except Exception, e:
            raise Exception('analyze_path: Bad path: %s, %s' % (path,str(e)))
    def handle_rsync(self, parts):
        self.log('handle rsync')
        flags = self.get_flags(parts)
        if 'z' in flags:
            print >> sys.stderr, '\n*** Use of -z is deprecated, and can actually hurt performance! ***\n'
        try:
            paths_data = [self.analyze_path(path) for path in parts[parts.index('.')+1:]]
            paths = [path_data['path'] for path_data in paths_data]
            shares = [path_data['share'] for path_data in paths_data]
            if '--sender' in parts:#server->client
                for share in shares:
                    user_permissions = share.get_user_permissions(self.user)
                    if Share.PERMISSION_DOWNLOAD not in user_permissions:
                        raise WrapperException('User %s cannot read from share %s' % (self.user.username,share.id))
                command = ['rsync', '--server', '--sender', flags, '.'] + paths
            else:#client->server
                # --no-p --no-g --chmod=ugo=rwX  //destination default permissions
                for share in shares:
                    user_permissions = share.get_user_permissions(self.user)
                    for perm in [Share.PERMISSION_WRITE,Share.PERMISSION_DELETE]:
                        if perm not in user_permissions:
                            raise WrapperException('User %s cannot write to share %s' % (self.user.username,share.id))
                    share.updated = timezone.now()
                    share.save()
                command = ['rsync', '--server', flags, '.'] + paths
    #             command = parts[:4]+paths
#             if TEST:
#                 logger.info('running rsync command: %s' % ', '.join(command))
#                 print command
#             else:
            self.log('running rsync command: %s' % ', '.join(command))
            os.execvp('rsync', command)
        except Exception, e:
            print >> sys.stderr, 'handle_rsync exception: %s' % str(e)
            self.log('handle_rsync exception: %s' % str(e))
    def handle(self, *args, **options):
        os.umask(0002)
        self.user = User.objects.get(username=options['user'])
        self.ORIGINAL_COMMAND = os.environ['SSH_ORIGINAL_COMMAND']
        
        RSYNC_LOGFILE = get_setting('RSYNC_LOGFILE',None)
        if RSYNC_LOGFILE:
            self.logger = logging.getLogger('bioshare')
            hdlr = logging.FileHandler(RSYNC_LOGFILE)
            formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
            hdlr.setFormatter(formatter)
            self.logger.addHandler(hdlr) 
            self.logger.setLevel(logging.INFO)
        self.log('user: %s' % options['user'])
        self.log('command: %s' % self.ORIGINAL_COMMAND)
        try:
            import shlex
            parts = shlex.split(self.ORIGINAL_COMMAND)
            self.log('SSH_ORIGINAL_COMMAND: '+self.ORIGINAL_COMMAND)
            self.log('SPLIT: '+', '.join(parts))
            if parts[0] == 'rsync':
                self.handle_rsync(parts)
            else:
                self.log( 'Unsupported command: %s' % parts[0])
        except Exception, e:
            self.log('Bad or missing parameter "SSH_ORIGINAL_COMMAND"')
            