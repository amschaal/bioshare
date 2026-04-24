"""
Local replacement for django-sendfile2.

django-sendfile2 enforces a single SENDFILE_ROOT which is incompatible with
BioShareX's multi-root filesystem model (FILESYSTEM_DIRECTORIES can list
several unrelated paths like /data/shares, /share/biocore, /tmp, ...).

Settings:

    SENDFILE_METHOD   - 'simple' | 'xsendfile' | 'nginx'.
    SENDFILE_ROOTS    - list of absolute directories this module is allowed
                        to serve from. Defense-in-depth check layered on top
                        of @safe_path_decorator + FILESYSTEM_DIRECTORIES.
                        Applies to every transport. Empty list disables the
                        check. SENDFILE_ROOTS should generally mirror
                        FILESYSTEM_DIRECTORIES + LINK_TO_DIRECTORIES so that
                        legitimate symlinks still resolve to a whitelisted
                        root (we realpath() before checking).
    NGINX_INTERNAL_LOCATIONS - only for 'nginx': mapping of filesystem root
                        to the internal nginx URI. Keys must be a subset of
                        SENDFILE_ROOTS. Longest matching root wins.
    SENDFILE_CSP      - Content-Security-Policy header value applied to
                        every response. Default isolates user-uploaded HTML
                        in a null origin (no access to bioshare cookies,
                        localStorage, or APIs) while still permitting the
                        scripts + popups that interactive bioinformatics
                        reports rely on. Set to None to disable the header.

Security model:

  * All path input is passed through os.path.realpath() once, and that
    resolved path is what we (a) whitelist-check, (b) open / hand to
    Apache / translate for nginx. That closes the symlink-swap TOCTOU
    window between the check and the delivery.
  * Only regular files are served; directories, device nodes, sockets,
    FIFOs, etc. are refused.
  * Whitelist uses `real == root` OR `real.startswith(root + '/')` so
    prefix-confusion attacks (e.g. /data/sharesXX matching /data/shares)
    are rejected.
  * Filenames bound for HTTP headers are stripped of C0 control chars
    before use; Django's own BadHeaderError is a second line of defense.
  * 4xx messages sent to the client never include the absolute path.
  * X-Content-Type-Options: nosniff is set on every response to block
    MIME-sniffing attacks when the caller serves content inline.

Example nginx config matching NGINX_INTERNAL_LOCATIONS = {
    '/data/shares': '/protected-shares',
    '/share/biocore': '/protected-biocore',
}:

    location /protected-shares/ {
        internal;
        alias /data/shares/;
    }
    location /protected-biocore/ {
        internal;
        alias /share/biocore/;
    }

The API mirrors django-sendfile2's sendfile() so call sites do not change.
"""

import logging
import mimetypes
import os
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse

logger = logging.getLogger(__name__)

# C0 control characters (0x00-0x1F) and DEL (0x7F). Used to scrub filenames
# that end up in Content-Disposition / X-Sendfile / X-Accel-Redirect headers.
_CONTROL_CHARS = ''.join(chr(c) for c in range(0x20)) + '\x7f'
_CONTROL_TRANS = str.maketrans('', '', _CONTROL_CHARS)

# Default CSP: isolate served documents in a null origin so user-uploaded
# HTML cannot read app cookies or hit authenticated APIs, while still
# allowing the JS + popups that legitimate bioinformatics reports need.
_DEFAULT_CSP = 'sandbox allow-scripts allow-popups'


def sendfile(request, filename, attachment=False, attachment_filename=None, mimetype=None, encoding=None):
    if not isinstance(filename, str) or not os.path.isabs(filename):
        logger.warning('sendfile: non-absolute or non-string path rejected: %r', filename)
        raise Http404()

    # Single resolve point: everything downstream uses `real`, closing the
    # check-vs-open TOCTOU window on symlinks.
    real = os.path.realpath(filename)

    if not os.path.isfile(real):
        logger.warning('sendfile: not a regular file: %r (resolved %r)', filename, real)
        raise Http404()

    _check_under_roots(real)

    if attachment_filename is None:
        attachment_filename = os.path.basename(real)
    attachment_filename = _scrub(attachment_filename)

    if mimetype is None:
        mimetype, _ = mimetypes.guess_type(real)
    if mimetype is None:
        mimetype = 'application/octet-stream'

    method = getattr(settings, 'SENDFILE_METHOD', 'simple')

    if method == 'simple':
        response = FileResponse(
            open(real, 'rb'),
            as_attachment=attachment,
            filename=attachment_filename,
            content_type=mimetype,
        )
    elif method == 'xsendfile':
        response = HttpResponse(content_type=mimetype)
        response['X-Sendfile'] = real
        if attachment:
            response['Content-Disposition'] = _attachment_header(attachment_filename)
    elif method == 'nginx':
        response = HttpResponse(content_type=mimetype)
        response['X-Accel-Redirect'] = _map_to_internal_uri(real)
        if attachment:
            response['Content-Disposition'] = _attachment_header(attachment_filename)
    else:
        raise ValueError('Unknown SENDFILE_METHOD: %r' % method)

    # Prevent MIME sniffing: a user-uploaded HTML file served inline should
    # not be upgraded from text/plain to text/html by the browser.
    response['X-Content-Type-Options'] = 'nosniff'
    # CSP sandbox: render user-uploaded HTML in a null origin so any script
    # in it cannot reach bioshare cookies / APIs. Harmless on non-documents.
    csp = getattr(settings, 'SENDFILE_CSP', _DEFAULT_CSP)
    if csp:
        response['Content-Security-Policy'] = csp
    if encoding:
        response['Content-Encoding'] = encoding
    return response


def _check_under_roots(real):
    roots = getattr(settings, 'SENDFILE_ROOTS', []) or []
    normalized = [os.path.realpath(r).rstrip('/') for r in roots if r]
    if not normalized:
        return
    for root_real in normalized:
        if not root_real:  # root was '/' or '' after strip
            if real.startswith('/'):
                return
            continue
        if real == root_real or real.startswith(root_real + '/'):
            return
    logger.warning('sendfile: path %r not under any SENDFILE_ROOTS', real)
    raise Http404()


def _map_to_internal_uri(real):
    mapping = getattr(settings, 'NGINX_INTERNAL_LOCATIONS', {}) or {}
    if not mapping:
        raise ValueError(
            'SENDFILE_METHOD is "nginx" but NGINX_INTERNAL_LOCATIONS is empty. '
            'Map each SENDFILE_ROOTS entry to an internal nginx location.'
        )
    best_root = None
    best_real = None
    for root in mapping:
        root_real = os.path.realpath(root).rstrip('/')
        if not root_real:
            continue
        if real == root_real or real.startswith(root_real + '/'):
            if best_real is None or len(root_real) > len(best_real):
                best_root = root
                best_real = root_real
    if best_root is None:
        logger.warning('sendfile: path %r not under any NGINX_INTERNAL_LOCATIONS root', real)
        raise Http404()
    internal = mapping[best_root].rstrip('/')
    relpath = real[len(best_real):].lstrip('/')
    # `real` is a realpath -- no '..' components remain. quote() encodes any
    # remaining reserved chars so the URI can't smuggle /, ?, # into nginx.
    return '%s/%s' % (internal, quote(relpath))


def _attachment_header(filename):
    # RFC 5987: ascii fallback + UTF-8 encoded variant for non-ascii names.
    # The ascii fallback strips non-ascii, control chars, and the double
    # quote that delimits the header value.
    ascii_safe = filename.encode('ascii', errors='replace').decode('ascii')
    ascii_safe = _scrub(ascii_safe).replace('"', '')
    utf8 = quote(filename)
    return 'attachment; filename="%s"; filename*=UTF-8\'\'%s' % (ascii_safe, utf8)


def _scrub(s):
    return s.translate(_CONTROL_TRANS)
