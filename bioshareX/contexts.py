from models import Share
from guardian.shortcuts import get_objects_for_user
def user_contexts(request):
        if request.user.is_authenticated():
            recent_shares = Share.objects.filter(owner=request.user)[:5]
            shared_with_me = get_objects_for_user(request.user, 'bioshareX.view_share_files')[:5]
        else:
            recent_shares = []
            shared_with_me = [] 
        return {
            'my_recent_shares':recent_shares,
            'shared_with_me':shared_with_me,
        }



# def user_dashboard(request, template_name='projects/dashboard.html'):
#     projects = get_objects_for_user(request.user, 'projects.view_project')
#     return render_to_response(template_name, {'projects': projects},
#         RequestContext(request))