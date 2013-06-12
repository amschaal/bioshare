from models import Share
def user_contexts(request):
        recent_shares = Share.objects.filter(owner=request.user)
        return {
            'my_recent_shares':recent_shares,
        }