from django.core.management.base import BaseCommand
from bioshareX.models import Share, ShareLog
import os, re, logging
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
    requires_system_checks = []
    def get_flags(self,args):
        # Collect all the short flags into one group
        args_re = re.compile(r"\-(\w+)")
        flags = ''
        for arg in args:
            m = args_re.match(arg)
            if m:
                flags += m.group(1)
        
        allowed = 'vtzqcirt'
        filtered = ''.join([c for c in flags if c in allowed])
        return '-L'+filtered
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
            if 'share' not in matches:
                raise WrapperException('analyze_path: Bad key: %s' % path)
            share = Share.objects.get(id=matches['share'])
#             share_path = get_share_meta(matches['share'])['path']
            if 'subpath' in matches:
                try:
                    test_path(matches['subpath'])
                except:
                    raise WrapperException('Illegal subpath: %s' % matches['subpath'])
                path = join(share.get_path(),  match.group('subpath'))
            else:
                path = share.get_path()
            return {'share':share,'path':path,'subpath':'/'+matches.get('subpath','')}
        except WrapperException as e:
            raise e
        except Exception as e:
            raise Exception('analyze_path: Bad path: %s, %s' % (path,str(e)))
    def handle_rsync(self, parts):
        flags = self.get_flags(parts)
        if 'z' in flags:
            print('\n*** Use of -z is deprecated, and can actually hurt performance! ***\n',file=sys.stderr)
        try:
            paths_data = [self.analyze_path(path) for path in parts[parts.index('.')+1:]]
            paths = [path_data['path'] for path_data in paths_data]
            shares = [path_data['share'] for path_data in paths_data]
            if '--sender' in parts:#server->client
                for share in shares:
                    user_permissions = share.get_user_permissions(self.user)
                    if Share.PERMISSION_DOWNLOAD not in user_permissions:
                        raise WrapperException('User %s cannot read from share %s' % (self.user.username,share.id))
                    share.check_paths(True)
                    if share.illegal_path_found:
                        raise WrapperException('Illegal path found for share %s, rsync terminated.' % (share.id))  
                    share.last_data_access = timezone.now()
                    share.save(update_fields=['last_data_access'])
                command = ['rsync', '--server', '--sender', flags, '.'] + paths
            else:#client->server
                # --no-p --no-g --chmod=ugo=rwX  //destination default permissions
                for share in shares:
                    user_permissions = share.get_user_permissions(self.user)
                    for perm in [Share.PERMISSION_WRITE,Share.PERMISSION_DELETE]:
                        if perm not in user_permissions:
                            raise WrapperException('User %s cannot write to share %s' % (self.user.username,share.id))
                    share.check_paths(True)
                    if share.contains_symlinks:
                        raise WrapperException('Share %s contains symlinks and is not writable' % (share.id))
                    if share.illegal_path_found:
                        raise WrapperException('Illegal path found for share %s, rsync terminated.' % (share.id))
                    share.updated = timezone.now()
                    share.save()
                command = ['rsync', '--server', flags, '.'] + paths
                ShareLog.create(share=share,user=self.user,action=ShareLog.ACTION_RSYNC,paths=[path_data['subpath'] for path_data in paths_data], text=self.ORIGINAL_COMMAND)
            self.log('running rsync command: %s' % ', '.join(command))
            os.execvp('rsync', command)
        except Exception as e:
            print('handle_rsync exception: %s' % str(e),file=sys.stderr)
            self.log('handle_rsync exception: %s' % str(e))
    def handle(self, *args, **options):
        os.umask(0o002)
        self.user = User.objects.get(username=options['user'])
        self.ORIGINAL_COMMAND = os.environ['SSH_ORIGINAL_COMMAND']
        print('command '+  os.environ['SSH_ORIGINAL_COMMAND'],file=sys.stderr)
        RSYNC_LOGFILE = get_setting('RSYNC_LOGFILE',None)
        if RSYNC_LOGFILE:
            self.logger = logging.getLogger('bioshare')
            hdlr = logging.FileHandler(RSYNC_LOGFILE)
            formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
            hdlr.setFormatter(formatter)
            self.logger.addHandler(hdlr) 
            self.logger.setLevel(logging.INFO)
        self.log('user: %s' % options['user'])
        self.log('SSH_ORIGINAL_COMMAND: %s' % self.ORIGINAL_COMMAND)
        try:
            import shlex
            parts = shlex.split(self.ORIGINAL_COMMAND)
            if parts[0] == 'rsync':
                self.handle_rsync(parts)
            else:
                self.log( 'Unsupported command: %s' % parts[0])
        except Exception as e:
            self.log('Bad or missing parameter "SSH_ORIGINAL_COMMAND"')
            