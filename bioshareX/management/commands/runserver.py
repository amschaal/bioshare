"""runserver, but with static responses that browsers actually revalidate.

``django.views.static.serve`` sends ``Last-Modified`` and nothing else -- no
``Cache-Control``, no ``ETag`` -- so browsers fall back to RFC 9111 heuristic
freshness (typically 10% of the age since ``Last-Modified``) and reuse edited
JS/CSS out of cache without asking. That is why editing a component and reloading
appears to do nothing until you force-refresh.

It bites harder here than in a typical Django project because the frontend is
unbundled ES modules: the browser resolves the ``/static/js/app/...`` specifiers
itself, so a cached entry point silently pins every module it transitively
imports. There is no bundle whose URL could change to invalidate them.

This has to be done in the handler rather than in ``MIDDLEWARE``:
``StaticFilesHandlerMixin.load_middleware()`` is a no-op and its
``get_response()`` calls ``self.serve()`` directly, so nothing in
``settings.MIDDLEWARE`` ever sees a ``/static/`` request under runserver.
``StaticFilesHandler.__call__`` also intercepts before URL resolution, so a
``urls.py`` route would not see it either.

Production does not use this path at all -- Apache serves ``STATIC_ROOT``, and the
content-hashed filenames from ``bioshareX/storage.py`` make caching safe there.

For this module to shadow django.contrib.staticfiles' runserver, ``'bioshareX'``
must appear before ``'django.contrib.staticfiles'`` in ``INSTALLED_APPS``:
``get_commands()`` iterates ``reversed(app_configs)`` and ``dict.update()``s, so
the earliest app wins.
"""

from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.contrib.staticfiles.management.commands.runserver import (
    Command as StaticfilesRunserverCommand,
)

# "no-cache" does not mean "do not store"; it means "revalidate before reuse".
# Every reload becomes a conditional GET, and django.views.static.serve already
# honours If-Modified-Since, so unchanged files cost one 304 with an empty body.
DEV_STATIC_CACHE_CONTROL = 'no-cache, max-age=0, must-revalidate'


class RevalidatingStaticFilesHandler(StaticFilesHandler):
    def serve(self, request):
        response = super().serve(request)
        # Also set on the 304 path, deliberately: HttpResponseNotModified only
        # forbids a body, and a 304 updates the stored response's headers, so the
        # policy sticks after the first revalidation.
        response.headers['Cache-Control'] = DEV_STATIC_CACHE_CONTROL
        return response


class Command(StaticfilesRunserverCommand):
    def get_handler(self, *args, **options):
        handler = super().get_handler(*args, **options)
        # A plain WSGI handler comes back when --nostatic was passed, or when
        # DEBUG is off without --insecure.
        if isinstance(handler, StaticFilesHandler):
            return RevalidatingStaticFilesHandler(handler.application)
        return handler
