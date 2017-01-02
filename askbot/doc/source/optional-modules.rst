================
Optional modules
================

Askbot supports a number of optional modules, enabling certain features, not available 
in askbot by default.

.. _haystack:

Haystack search
=============
Askbot supports `Haystack <http://haystacksearch.org/>`_, a modular search framework that supports popular search engine backends as 
Solr, Elasticsearch, Whoosh and Xapian. 

.. note::
    Haystack support in Askbot is a new feature,
    please give us your feedback at ``support@askbot.com``
    regarding the possible improvements.

To enable:

* add 'haystack' to INSTALLED_APPS
* add ENABLE_HAYSTACK_SEARCH = True in settings.py 
* Configure your search backend according to your setup following `this guide <http://django-haystack.readthedocs.org/en/latest/tutorial.html#modify-your-settings-py>`_

Solr and  Multilingual Support
-------------------------

There is more documentation about solr and multilingual support  please visit :ref:`this link <solr>`

.. _ldap:

LDAP authentication
===================

To enable authentication via LDAP
(Lightweight Directory Access Protocol, see more info elsewhere)
, first :ref:`install <installation-of-python-packages>`
``python-ldap`` package:

    pip install python-ldap

After that, add configuration parameters in :ref:`live settings <live-settings>`,
section "LDAP settings" 
(url ``/settings/LDAP_SETTINGS``, relative to the forum base url)

.. note::
    While it is possible to configure LDAP via web interface,
    it is actually more safe to add them in your ``settings.py`` file in the
    :ref:`LIVESETTINGS_OPTIONS <live-settings-options>` dictionary.
    Consider that a breach in security of your forum might open
    malicious access into your LDAP directory.

The parameters are (note that some have pre-set defaults that might work for you)::

* in Login Provider Settings select "enable local login"
  - this makes login/password form available
* enable/disable LDAP for password login -
  must check that, to connect the login/password form to LDAP flow
* create accounts automatically or not (``LDAP_AUTOCREATE_USERS``)
* protocol version (``LDAP_PROTOCOL_VERSION``) (version 2 is insecure and deprecated)
* ldap url (``LDAP_URL``)
* base distinguished name, 'dn' in LDAP parlance (``LDAP_BASEDN``)
* user id field name (``LDAP_USERID_FIELD``)
* email field name (``LDAP_EMAIL_FIELD``)
* user name filter template (``LDAP_USERNAME_FILTER_TEMPLATE``)
  must have two string placeholders.
* given (first) name field (``LDAP_GIVEN_NAME_FIELD``)
* surname (last name) field (``LDAP_SURNAME_FIELD``)
* common name field (``LDAP_COMMON_NAME_FIELD``)
  either given and surname should be used or common name.
  All three are not necessary - either first two or common.
  These fields are used to extract users first and last names.
* Format of common name (``LDAP_COMMON_NAME_FIELD_FORMAT``)
  values can be only 'first,last' or 'last,first' - used to 
  extract last and first names from common name

There are three more optional parameters that must go to the ``settings.py`` file::

* ``LDAP_LOGIN_DN``
* ``LDAP_PASSWORD``
* ``LDAP_EXTRA_OPTIONS``, a list of two-item tuples - of names and values of
  the options. Option names must be upper case strings all starting with ``OPT_``
  as described in the `python ldap library documentation <http://www.python-ldap.org/doc/html/ldap.html#options>`_. An often used option is (`OPT_REFERRALS`, 0).
* ``LDAP_AUTHENTICATE_FUNCTION`` - dotted python path to optional function that
  can override the default `ldap_authenticate` function. This function allows to
  completely customize the LDAP login procedure.
  To see what is expected of this function (input parameters and the return value) -
  look at the end of the doc string at
  `askbot.deps.django_authopenid.ldap_auth.ldap_authenticate_default`.
  One use case for the custom function is determining to which group
  a user might belong or check any additional access rules that might be
  stored in your LDAP directory. Another use case - is the case when 
  the default procedure just does not work for you.
* ``LDAP_AUTHENICATE_FAILURE_FUNCTION`` - python dotted path to an additional function
  that may be called after a unsuccessful authentication.
  This function can be used to set custom error messages to the login form.
  The function should take two parameters (in the following order): user_info, login_form.
  user_info - is the same dictionary
  that is returned by the `ldap_authenticate` function.
* ``LDAP_CREATE_USER_FUNCTION`` - python dotted path to function that will create
  the ldap user, should actually return a user association object, like
  ``askbot.deps.django_authopenid.ldap_auth.ldap_create_user_default``.
  Function takes return value of the ldap authenticate function as a sole parameter.


Use these when you have the "directory master passsword" - 
for a specific user who can access the rest of the directory,
these were not added to the live settings due to security concerns.

``LDAP_USER`` and ``LDAP_PASSWORD`` will be used only if both are provided!

Since LDAP authentication requires so many parameters,
you might need to :ref:`debug <debugging>` the settings.
The function to look at is `askbot.deps.django_authopenid.backends.ldap_authenticate`.
If you have problems with LDAP please contact us at support@askbot.com.

The easiest way to debug - insert ``import pdb; pdb.set_trace()`` line into function
`askbot.deps.django_authopenid.backends.ldap_authenticate`,
start the ``runserver`` and step through.

.. _custom_profile:

Custom section in the user profile
==================================
Sometimes you might want to add a completely custom section
to the user profile, available via an additional tab.

This is possible by editing the ``settings.py`` file,
which means that to use this feature you must have sufficient 
access to the webserver file system.

Add a following setting to your ``settings.py``::

    ASKBOT_CUSTOM_USER_PROFILE_TAB = {
        'NAME': 'some name',
        'SLUG': 'some-name',
        'CONTENT_GENERATOR': 'myapp.views.somefunc'
    }

The value of ``ASKBOT_CUSTOM_USER_PROFILE_TAB['CONTENT_GENERATOR']``
should be a path to the function that returns the widget content
as string.

Here is a simple example of the content generator 
implemented as part of the fictional application called ``myapp``::

    from myapp.models import Thing#definition not shown here
    from django.template.loader import get_template
    from django.template import Context

    def somefunc(request, profile_owner):
        """loads things for the ``profile_owner``
        and returns output rendered as html string
        """
        template = get_template('mytemplate.html')
        things = Thing.objects.filter(user = profile_owner)
        return template.render(Context({'things': things}))

The function is very similar to the regular
Django view, but returns a string instead of the ``HttpResponse``
instance.

Also, the method must accept one additional argument -
an instance of the ``django.contrib.auth.models.User`` object.

.. _wordpress_auth:

Wordpress authentication
========================

To enable authentication for self hosted wordpress sites(wordpress.com blogs will work with openid login). To enable it follow the following steps:

* Check if you have the package `"python_wordpress_xmlrpc <http://pypi.python.org/pypi/python-wordpress-xmlrpc/1.4>`_ from pypi.
* Go to your wordpress blog admin panel and serch for: Settings->Writing->Remote Publishing then check the box for XML-RPC.
* Go back to your askbot site settings and click on *Login Provider Settings* and then activate the option *Activate to allow login with self-hosted wordpress site*, 
* Input your blog url to the xmlrpc.php file it will look something like this http://yoursite.com/xmlrpc.php
* Upload an icon for display in the login area.

After doing this steps you should be able to login with your self hosted wordpress site user/password combination.

.. _celery:

Celery for background jobs
==========================

Askbot supports `celery <http://celeryproject.org/>`_ distributed task queue for some task, to enable it follow the following steps:

* Install the following packages: `celery <http://pypi.python.org/pypi/django-celery>`_, `django-celery <http://pypi.python.org/pypi/django-celery>`_,  `django-kombu <http://pypi.python.org/pypi/django-kombu>`_
* Set **CELERY_ALWAYS_EAGER** setting value to **False**
* Run the celery daemon: for this you can use generic init scripts or supervisor, `celery documentation have more information <http://docs.celeryproject.org/en/latest/cookbook/daemonizing.html>`_

For `supervisor <http://supervisord.org/>`_: add this sample config file named askbot.conf into /etc/supervisor/conf.d/ directory::

    [program:askbot_celery]
    command=celeryd --loglevel=INFO

    environment=PYTHONPATH=/path/to/project
    directory=/path/to/project

    user=nobody
    numprocs=1
    stdout_logfile=/var/log/askbot_celery.log
    stderr_logfile=/var/log/askbot_celery.err
    autostart=true
    autorestart=true
    startsecs=10

Then run **supervisorctl update** and it will be started. For more information about job handling with supervisor please visit `this link <http://supervisord.org/>`_.


S3 Integration
=============

.. note::
    Please note that this is a "recipe" solution and there might be a better way
    to achieve the same. Please have a look at available django packages
    for integration with the S3 service.


The media files are stored locally by default. If you're hosting askbot on AWS you might want to take advantage of S3 buckets instead. The usage of S3 buckets becomes particularly important when you deploy Askbot on an AutoScaling group; in this configuration, you might notice some avatars go missing. This problem occurs since ASG might be firing off a new instance and it does not have access to the older avatar files that were stored in the old instance. Saving the media files on S3 would resolve this problem. The goood news is enabling S3 integration is fairly simple in Askbot.

Please first install the following packages::
    
        pip install boto
        pip install django-storages
    
Create a new Python calss, ``s3utils.py`` in the same directory as your ``settings.py`` file. And define the class as the following::

    from storages.backends.s3boto import S3BotoStorage
    MediaRootS3BotoStorage  = lambda: S3BotoStorage(location='media') 
    
Then replace the following line in your ``settings.py``::
    
    MEDIA_ROOT = os.path.join(os.path.dirname(__file__), 'askbot', 'upfiles')

with::
    
    #set encoding to unicode for reading environment variables
    reload(sys)
    sys.setdefaultencoding('utf8')
    
    #AWS params used for S3 bucket integration.
    #They have to be set as an enviroment variable. Otherwise local storage will be used.
    #These options apply to a local deployment only
    AWS_STORAGE_BUCKET_NAME = os.environ.get('STORAGE_BUCKET_NAME')
    AWS_ACCESS_KEY_ID = os.environ.get('ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('SECRET_ACCESS_KEY')
 
    # S3 path to the directory that holds uploaded media
    AWS_S3_CUSTOM_DOMAIN = '%s.s3.amazonaws.com' % AWS_STORAGE_BUCKET_NAME
    MEDIA_ROOT = "https://%s/%s/" % (AWS_S3_CUSTOM_DOMAIN, 'media')
    
In addition, replace the following::
    
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
    
with::
    
    DEFAULT_FILE_STORAGE = 's3utils.MediaRootS3BotoStorage'
    
Last but not least, we would need to update the ``INSTALLED_APPS`` field to let Django know that the storage modules have been installed::
    
        INSTALLED_APPS = (
          ...,
          'storages',
     )
    
Now the only thing left to do is to specify the AWS parameters from command line::
    
    $ export STORAGE_BUCKET_NAME=BUCKET_NAEM #set to the bucket name you've created in AWS
    $ export ACCESS_KEY_ID=XXXXXXXXXXXXXXXX
    $ export SECRET_ACCESS_KEY=XXXXXXXXXXXXXXXXXXXXXX
    
Then deploy Askbot. You should now be using the S3 storage instead of local storage.
