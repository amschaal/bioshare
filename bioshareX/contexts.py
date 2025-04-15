from django.conf import settings
from guardian.shortcuts import get_objects_for_user

from bioshareX.models import Share

from functools import cached_property

# This class ensures that the queries from get_objects_for_user are not run unless accessed in the template
class UserShares():

    def __init__(self, request):
      self.request = request

    @cached_property
    def my_recent_shares(self):
        return Share.objects.filter(owner=self.request.user).order_by('-created')[:5]
    @cached_property
    def shared_with_me(self):
        return get_objects_for_user(self.request.user, 'bioshareX.view_share_files',klass=Share).exclude(owner=self.request.user).order_by('-created')[:5]
    @cached_property
    def bad_share_path(self):
        return get_objects_for_user(self.request.user, 'bioshareX.view_share_files',klass=Share).filter(path_exists=False).order_by('-created')
    @cached_property
    def locked_shares(self):
        return get_objects_for_user(self.request.user, 'bioshareX.view_share_files',klass=Share).filter(locked=True).order_by('-created')
    
def user_contexts(request):
        if request.user.is_authenticated and not request.is_ajax():
            shares = UserShares(request)
            # recent_shares = Share.objects.filter(owner=request.user).order_by('-created')[:5]
            # # The calls below are causing a lot of extra queries to be run, here or from the template. Make more efficient, or cache somehow
            # shared_with_me = get_objects_for_user(request.user, 'bioshareX.view_share_files',klass=Share).exclude(owner=request.user).order_by('-created')[:5]
            # bad_share_path = get_objects_for_user(request.user, 'bioshareX.view_share_files',klass=Share).filter(path_exists=False).order_by('-created')
            # locked_shares = get_objects_for_user(request.user, 'bioshareX.view_share_files',klass=Share).filter(locked=True).order_by('-created')
        else:
            shares = {
                'recent_shares': [],
                'shared_with_me': [],
                'bad_share_path': [],
                'locked_shares': []
            }
        return {
            'user_shares': shares,
            # 'my_recent_shares':recent_shares,
            # 'shared_with_me':shared_with_me,
            # 'bad_share_path':bad_share_path,
            # 'locked_shares':locked_shares,
            'SITE_URL':settings.SITE_URL
        }



# def user_dashboard(request, template_name='projects/dashboard.html'):
#     projects = get_objects_for_user(request.user, 'projects.view_project')
#     return render_to_response(template_name, {'projects': projects},
#         RequestContext(request))