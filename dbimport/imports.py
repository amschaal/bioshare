from db import dictfetchall
from django.contrib.auth.models import Group, User
from bioshareX.models import Share, Tag
from django.db import transaction
from guardian.shortcuts import assign_perm
@transaction.commit_on_success
def import_users():
    group = Group.objects.get_or_create(name='old_accounts')[0]
    print group
    users = dictfetchall('select * from user')
    for user in users:
        try:
            User.objects.get(email=user['login'])
            print 'User with email %s exists' % user['login']
        except:
            try:
                print 'Creating user %s' % user['login']
                u = User(username=user['login'],email=user['login'],first_name=user['firstname'],last_name=user['lastname'])
    #             u.set_password(password)
                u.save()
                u.groups.add(group)
                u.save()
            except:
                print 'Failed creating user %s' % user['login']
            
#     raise Exception('do not commit this')
@transaction.commit_on_success
def import_shares():
    admin = User.objects.get(username='admin')
    select = """SELECT 
                    sp.description,
                    sp.random_dir,
                    sp.submitted,
                    p.description as pdescription,
                    p.project_title as ptitle,
                    g.db_group, 
                    t.type as type, 
                    t.description as type_description 
                FROM bioshare_old.sub_project sp join project p on sp.project_id = p.project_id join type t on sp.type_id = t.type_id join db_group g on g.group_id = p.group_id"""
    subprojects = dictfetchall(select)
    for sp in subprojects:
        share_id = '00000%s'%sp['random_dir']
        try:
            share = Share.objects.get(id=share_id)
            share.delete()
        except:
            pass
        share = Share(id=share_id)
        share.name = ('%s: %s- %s, %s'%(sp['db_group'],sp['ptitle'],sp['type'],sp['submitted']))[:99]
        print 'Creating %s'%share.name[:99]
        share.notes = "Project Description:%s\nSubproject Description:%s"%(sp['pdescription'],sp['description'])
        share.owner=admin
        share.save()
        tag = Tag.objects.get_or_create(name=sp['db_group'])[0]
        share.tags.add(tag)
        share.save()
        
@transaction.commit_on_success
def import_permissions():
    admin = User.objects.get(username='admin')
    select = """SELECT  random_dir, login, permission FROM
    (
    SELECT sub_project_id, login, user.user_id, lastname, firstname, permission FROM all_user_group_permission, project, sub_project, user WHERE sub_project.project_id = project.project_id AND all_user_group_permission.group_id = project.group_id AND all_user_group_permission.user_id = user.user_id
    UNION
    SELECT sub_project_id, login, user.user_id, lastname, firstname, permission FROM all_user_sub_project_permission, user WHERE source LIKE 'project' AND all_user_sub_project_permission.user_id = user.user_id
    UNION
    SELECT sub_project_id, login, user.user_id, lastname, firstname, permission FROM all_user_sub_project_permission, user WHERE  source LIKE 'sub_project' AND all_user_sub_project_permission.user_id = user.user_id
    ) as X join sub_project sp on X.sub_project_id = sp.sub_project_id
    GROUP BY random_dir,login,permission
    ORDER BY random_dir,lastname, user_id, permission"""
    
    perms = dictfetchall(select)
    perm_map = {'administer':'admin','view-project':'view_share_files','view-files':'download_share_files','upload-files':'write_to_share','delete-files':'delete_share_files'}
    for p in perms:
        share_id = '00000%s'%p['random_dir']
        print 'treating share %s' % share_id
        share = Share.objects.get(id=share_id)
        user = User.objects.get(email=p['login'])
        assign_perm(perm_map[p['permission']],user,share)
#             MetaData
#     raise Exception('Do not commit this')
# SELECT sp.description,sp.random_dir,sp.submitted,p.description as pdescription, p.project_title as ptitle, t.type as type, t.description as type_description FROM bioshare_old.sub_project sp join project p on sp.project_id = p.project_id join type t on sp.type_id = t.type_id;

def create_symlinks():
    import os
    file = '/home/adam/bioshare_symlinks'
    base = '/data/bioshare/'
    link_directory = '/var/www/virtualenv/bioshareX/include/bioshareX/media/files'
    os.chdir(link_directory)
    for line in open(file):
        try:
            parts = line.split()
            link = '00000%s'%parts[8]
            target= base+parts[10].split('/var/www/html/bioshare/files/')[1]
            print '%s -> %s'%(link,target)
            os.symlink(target,link)
        except:
            pass