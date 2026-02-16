=================================
Settings for ``settings.py`` file
=================================

* ``ALLOW_UNICODE_SLUGS`` - if ``True``, slugs will use unicode, default - ``False``
* ``ASKBOT_DELAYED_EMAIL_ALERTS_CUTOFF_TIMESTAMP`` - a datetime isnstance, useful
  when enabling email alerts on a site with a lot of existing content.
  This prevents spamming users with update alerts on content created
  long before the perioding email alerts were enabled.

There are more settings that are not documented yet,
but most are described in the ``settings.py`` template:

    askbot/setup_templates/settings.py.jinja2

* MIDDLEWARE

A lot of different middlewares are commonly used with Askbot. For reference
and inspiration, see this example definition for MIDDLEWARE:

    MIDDLEWARE = (
        'django.middleware.csrf.CsrfViewMiddleware',
        #'django.middleware.gzip.GZipMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
        ## Enable the following middleware if you want to enable
        ## language selection in the site settings.
        #'askbot.middleware.locale.LocaleMiddleware',
        #'django.middleware.cache.UpdateCacheMiddleware',
        'django.middleware.common.CommonMiddleware',
        #'django.middleware.cache.FetchFromCacheMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        #'django.middleware.sqlprint.SqlPrintingMiddleware',

        #below is askbot stuff for this tuple
        'askbot.middleware.anon_user.ConnectToSessionMessagesMiddleware',
        'askbot.middleware.forum_mode.ForumModeMiddleware',
        'askbot.middleware.cancel.CancelActionMiddleware',
        #'debug_toolbar.middleware.DebugToolbarMiddleware',
        'askbot.middleware.view_log.ViewLogMiddleware',
        'askbot.middleware.spaceless.SpacelessMiddleware',
    )

* INSTALLED_APPS

Askbot imports existing work as Django apps. Askbot is extended and integrated
using the common Django facilities. For reference and inspiration, see this
example INSTALLED_APPS:
    INSTALLED_APPS = (
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.sites',
        'django.contrib.staticfiles',

        #all of these are needed for the askbot
        'django.contrib.admin',
        'django.contrib.humanize',
        'django.contrib.sitemaps',
        'django.contrib.messages',
        'django_jinja',
        #'debug_toolbar',
        'compressor',
        'askbot',
        'askbot.deps.django_authopenid',
        #'askbot.importers.stackexchange', #se loader
        'livesettings',
        'keyedcache',
        'django_countries',
        'kombu.transport.memory',
        'followit',
        'askbot.deps.group_messaging',
        #'avatar',#experimental use git clone git://github.com/ericflo/django-avatar.git$
        'captcha',
        'avatar',
    )
TODO: describe all of them here.
