"""Response headers that the static-asset cache-busting scheme depends on."""


class HTMLCacheControlMiddleware:
    """Make HTML revalidate.

    Django sends no Cache-Control on most responses here -- only LoginView does,
    via its own @never_cache -- so browsers apply heuristic freshness to pages.
    That was survivable when /static/ was also unhashed, but now the HTML is what
    carries the content-hashed asset URLs and the importmap: a stale page pins the
    entire old asset set, which is exactly the failure the hashing exists to
    prevent.

    'no-cache' still allows storage, so a reload is one conditional GET rather than
    a re-download. 'private' keeps authenticated pages out of shared caches.

    Only applied to text/html, so the xsendfile download path and the DRF JSON API
    are untouched, and only when the response has no Cache-Control already, so
    views using never_cache or cache_page keep their own policy.

    Note this is the HTML half of the problem only. /static/ never reaches
    middleware under runserver -- see bioshareX/management/commands/runserver.py.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if 'Cache-Control' not in response.headers:
            if response.headers.get('Content-Type', '').startswith('text/html'):
                response.headers['Cache-Control'] = 'no-cache, private'
        return response
