from django import template
from django.utils.safestring import mark_safe
# from django.template.Library import register
register = template.Library()
from django.core.urlresolvers import reverse
import os
@register.simple_tag()
def link_full_path(*args, **kwargs):
    share = kwargs['share']
    subpath = kwargs['subpath']
    paths = subpath.split(os.sep)
    links = []
    for ind, val in enumerate(paths):
        spath = os.sep.join(paths[:ind+1])
        url = reverse('go_to_file_or_folder',kwargs={'share':share.id,'subpath':spath})
        link = '<a href="%s">%s</a>'%(url,val)
        links.append(link)
#     url = reverse('go_to_file_or_folder',kwargs={'share':share.id,'subpath':subpath})
    return mark_safe(' / '.join(links)) 