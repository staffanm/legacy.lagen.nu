# Django settings for ferenda project.

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
     ('Staffan Malmgren', 'staffan@tomtebo.org'),
)

MANAGERS = ADMINS

DATABASE_ENGINE = 'mysql'      # 'postgresql', 'mysql', 'sqlite3' or 'ado_mssql'.
DATABASE_NAME = 'ferenda'      # Or path to database file if using sqlite3.
DATABASE_USER = 'ferenda'      # Not used with sqlite3.
DATABASE_PASSWORD = 'f'        # Not used with sqlite3.
DATABASE_HOST = '192.168.0.7'  # Set to empty string for localhost. Not used with sqlite3.
DATABASE_PORT = ''             # Set to empty string for default. Not used with sqlite3.

# Local time zone for this installation. All choices can be found here:
# http://www.postgresql.org/docs/current/static/datetime-keywords.html#DATETIME-TIMEZONE-SET-TABLE
TIME_ZONE = 'Europe/Stockholm'


# Language code for this installation. All choices can be found here:
# http://www.w3.org/TR/REC-html40/struct/dirlang.html#langcodes
# http://blogs.law.harvard.edu/tech/stories/storyReader$15
LANGUAGE_CODE = 'sv-se'
DEFAULT_CHARSET = 'utf-8'
APPEND_SLASH = False;

SITE_ID = 1

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT.
# Example: "http://media.lawrence.com"
MEDIA_URL = ''

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'sx^h!fp!f(btkem3sk&tman_46f5-j6zunawpb$a9m%^8hcj-^'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
#     'django.template.loaders.eggs.load_template_source',
)

# CACHE_BACKEND = 'file:///var/tmp/django_cache'
# CACHE_BACKEND = 'file:///locmem'
CACHE_MIDDLEWARE_SECONDS = 300
CACHE_MIDDLEWARE_KEY_PREFIX = ''

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.doc.XViewMiddleware',
    'django.middleware.gzip.GZipMiddleware',
#    'django.middleware.cache.CacheMiddleware',
)

ROOT_URLCONF = 'ferenda.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates".
    "templates",
    "ferenda/templates",
    "/Library/WebServer/Documents/ferenda.lagen.nu/ferenda/templates",
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'ferenda.wiki',
    'ferenda.docview',    
)
EMAIL_HOST = "smtp.tomtebo.org"
SERVER_EMAIL = "nobody@lagen.nu"
EMAIL_SUBJECT_PREFIX = "Auto Generated Message: "
