from django.conf import settings

def url_path_key(group, request):
    if request.user.is_authenticated:
        return "{}:{}".format(request.user.username, request.path)
    else:
        return "{}:{}".format(request.META['REMOTE_ADDR'], request.path)

def ratelimit_rate(group, request):
    rates = getattr(settings,'RATELIMIT_RATES',{})
    group_rates = rates.get('groups', {}).get(group)
    if group_rates:
        if isinstance(group_rates, str):
            return group_rates
        elif 'user' in group_rates and request.user.is_authenticated:
            return group_rates.get('user')
        elif 'anon' in group_rates:
            return group_rates.get('anon')
    else:
        if request.user.is_authenticated and 'user' in rates:
            return rates['user']
        else:
            return rates.get('anon', '5/m')