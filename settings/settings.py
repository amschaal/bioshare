#
# Django settings for bioshareX project.
#
import sys
import os
CURRENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__),os.pardir))

# Used for rsync wrapper to choose correct python (especially when using virtualenv).  Override this in config.py if different from what is used by web server.
if 'VIRTUAL_ENV' in os.environ:
    PYTHON_BIN = os.path.join(os.environ['VIRTUAL_ENV'],'bin/python')
else:
    PYTHON_BIN = sys.executable

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/var/www/example.com/media/"
# MEDIA_ROOT = os.path.join(CURRENT_DIR, 'media')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://example.com/media/", "http://media.example.com/"
# MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/var/www/example.com/static/"
STATIC_ROOT = os.path.join(CURRENT_DIR, 'static')

# URL prefix for static files.
# Example: "http://example.com/static/", "http://static.example.com/"
STATIC_URL = '/static/'

# Additional locations of static files
STATICFILES_DIRS = (
    os.path.join(CURRENT_DIR, 'static_files'),
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

APPEND_SLASH = True
# # List of callables that know how to import templates from various sources.
# TEMPLATE_LOADERS = (
#     'django.template.loaders.filesystem.Loader',
#     'django.template.loaders.app_directories.Loader',
# #     'django.template.loaders.eggs.Loader',
# )

# TEMPLATE_CONTEXT_PROCESSORS = (
#     "django.contrib.auth.context_processors.auth",
#     "django.core.context_processors.debug",
#     "django.core.context_processors.i18n",
#     "django.core.context_processors.media",
#     "django.core.context_processors.static",
#     "django.core.context_processors.tz",
#     "django.contrib.messages.context_processors.messages",
#     "django.core.context_processors.request",
#     "bioshareX.contexts.user_contexts",
# )

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(CURRENT_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                # Insert your TEMPLATE_CONTEXT_PROCESSORS here or use this
                # list if you haven't customized them:
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.request',
                'bioshareX.contexts.user_contexts',
            ],
        },
    }
]

MIDDLEWARE = (
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django_ratelimit.middleware.RatelimitMiddleware'
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'wsgi.application'

# TEMPLATE_DIRS = (
#     os.path.join(CURRENT_DIR, 'templates'),
#     # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
#     # Always use forward slashes, even on Windows.
#     # Don't forget to use absolute paths, not relative paths.
# )

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
#     'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Uncomment the next line to enable the admin:
    'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',
    'bioshareX',
    'crispy_forms',
    'crispy_bootstrap5',
    'guardian',
    'django_filters',
    'rest_framework',
    'rest_framework.authtoken',
    'compressor',
    'corsheaders',
)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'null': {
            'level': 'DEBUG',
            'class': 'logging.NullHandler',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    'django.security.DisallowedHost': {
            'handlers': ['null'],
            'propagate': False,
        },
    }
}

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend', # this is default
    'guardian.backends.ObjectPermissionBackend',
)

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        #'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ),
    # Authenticated-by-default. Every current view sets explicit permissions (and
    # public share access uses non-DRF function views), so this only backstops any
    # future endpoint that forgets to declare permission_classes.
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    # 'DEFAULT_FILTER_BACKENDS': ('rest_framework_filters.backends.DjangoFilterBackend','rest_framework.filters.OrderingFilter'),
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend', 'rest_framework.filters.OrderingFilter',),
    'DEFAULT_PAGINATION_CLASS': 'bioshareX.pagination.StandardPagePagination',
    'PAGE_SIZE': 10,
    'PAGINATE_BY_PARAM': 'page_size',  # Allow client to override, using `?page_size=xxx`.
    'MAX_PAGINATE_BY': 1000,
    'DEFAULT_THROTTLE_CLASSES': [
        'bioshareX.api.throttles.BurstRateThrottle',
        'bioshareX.api.throttles.SustainedRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'burst': '20/minute',
        'sustained': '1000/day'
    }
}

ANONYMOUS_USER_ID = -1 #Guardian

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

DEFAULT_FILESYSTEM_ID = None #Replace with integer filesystem id

FILE_UPLOAD_HANDLERS = (
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
)
SSH_WRAPPER_SCRIPT = os.path.join(CURRENT_DIR, 'sshwrapper.py')

UMASK = 0o002

INCLUDE_REGISTER_URL = False

STRIP_REGEX = r'[^\w\.\- \*^]+'
UNDERSCORE_REGEX = r'[ ]+'
MD5SUM_COMMAND = 'md5sum'

ENABLE_SYMLINKS = False
SYMLINK_DEPTH_DEFAULT = 1 # default depth that symlinks are allowed, can be overridden
SYMLINK_DEPTH_MAX = 3 # absolute maximum depth

ZFS_CREATE_COMMAND =  ['zfs','create']
ZFS_DESTROY_COMMAND =  ['zfs','destroy']

USE_DU = False # Whether to use "du" linux command instead of python os utils for calculating share sizes

# RATELIMIT_EXCEPTION_CLASS = 'bioshareX.exceptions.ThrottledException'
RATELIMIT_VIEW = 'bioshareX.views.ratelimit_exceeded'

# Custom settings so it is easy to override per view rates in config, rather than changing source code
RATELIMIT_RATES = {
    'default': '10/m',
    'user': '10/m',
    'anon': '5/m',
    'groups': {
        'list_directory': {
            'user': '5/m',
            'anon': '2/m'
        },
        'wget_listing': '5/h',
        'create_symlink': '10/h',
        'download_stream_archive': '5/h',
        'download_file': {
            'user': '5/h',
            'anon': '2/h' 
        },
        'get_md5sum': {
            'user': '3/h',
            'anon': '2/d'
        },
        'search_share': {
            'user': '20/h',
            'anon': '5/h'
        },
        'email_participants': '3/d'
    }
}

RATELIMIT_EXEMPT_IPS = [] # List of exempt IP addresses or ranges
RATELIMIT_EXEMPT_USERNAMES = [] # List of exempt usernames

# Shortest accepted file-search query. Searches are a full `find` walk of the
# share with no index, so a one-character query matches most of a large share
# and costs a stat per hit. Deploys may override in config.py.
MIN_SEARCH_QUERY_LENGTH = 2

# Most file-search hits returned in one response. Each hit past this point
# costs an isdir() stat plus payload for a result list nobody scrolls through;
# the client is told when it hit the cap. Deploys may override in config.py.
MAX_SEARCH_RESULTS = 50

# Wall-clock ceiling (seconds) for any subprocess (du, find, zfs, md5sum,
# ssh-keygen, ...) invoked while handling a request. A blocked child past this
# is killed and raises subprocess.TimeoutExpired so the wsgi worker is freed
# instead of pinned until a manual restart. Deploys may override in config.py.
SUBPROCESS_TIMEOUT = 30

# Locale handed to subprocesses whose behaviour is locale-sensitive -- notably
# `find -iname`, whose case folding is ASCII-only under the C locale that wsgi
# workers usually inherit. Deploys may override in config.py.
SUBPROCESS_LOCALE = 'C.UTF-8'

# Socket timeout (seconds) Django passes to the SMTP backend. Email is sent
# synchronously inside request handlers (share/permission notifications,
# password reset); without this a slow or stalled mail server (e.g. a hung
# TLS handshake) blocks the EmailMessage.send() call and pins the worker
# indefinitely. Deploys may override in config.py.
EMAIL_TIMEOUT = 10

from settings.config import *

# Bound how long a single statement may run (and how long a connection attempt
# may block) so a degraded query plan or an unreachable DB host can't pin a
# wsgi worker until a manual restart. Injected here, after the per-deploy
# DATABASES block is imported, so it applies everywhere; a deploy can still
# override by pre-setting these OPTIONS in config.py. PostgreSQL-only
# (statement_timeout is passed via libpq `options`).
_default_db = DATABASES.get('default', {}) if 'DATABASES' in dir() else {}
if _default_db.get('ENGINE', '').endswith('postgresql'):
    _db_options = _default_db.setdefault('OPTIONS', {})
    _db_options.setdefault('connect_timeout', 10)
    _db_options.setdefault('options', '-c statement_timeout=30000')
