def url_path_key(group, request):
    if request.user.is_authenticated:
        return "{}:{}".format(request.user.username, request.path)
    else:
        return "{}:{}".format(request.META['REMOTE_ADDR'], request.path)