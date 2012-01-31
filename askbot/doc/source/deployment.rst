.. _deployment:

================
Deploying Askbot
================

Deploying askbot (assuming that it is already installed) entails:

* collecting static media files
* setting correct file access permissions
* configuring the webserver to work with your application

This document currently explains the configuration under Apache and mod_wsgi_.

Collecting static media files
-----------------------------
Static media must be collected into a single location with a command::

    python manage.py collectstatic

There are several options on where to put the static files - the simplest is 
a local directory, but it is also possible to use a dedicated static files
storage or a CDN, for more information see django documentation about
serving static files.

Setting up file access permissions
----------------------------------

Webserver process must be able to write to the following locations within your project::

    log/
    askbot/upfiles

If you know user name or the group name under which the webserver runs,
you can make those directories writable by setting the permissons
accordingly:

For example, if you are using Linux installation of apache webserver running under
group name 'apache' you could do the following::

    cd /path/to/django-project
    cd .. #go one level up
    chown -R yourlogin:apache django-project 
    chmod -R g+w django-project/askbot/upfiles
    chmod -R g+w django-project/log

If your account somehow limits you from running such commands - please consult your
system administrator.

Installation under Apache/mod\_wsgi
------------------------------------

Apache/mod\_wsgi combination is the only type of deployment described in this
document at the moment. mod_wsgi_ is currently the most resource efficient
apache handler for the Python web applications.

The main wsgi script is in the file django.wsgi_
it does not need to be modified

Configure webserver
~~~~~~~~~~~~~~~~~~~~

Settings below are not perfect but may be a good starting point::

    #NOTE: the directory paths used here may be adjusted

    #the following two directories must be both readable and writable by apache
    WSGISocketPrefix /path/to/socket/sock
    WSGIPythonEggs /var/python/eggs

    #the following directory must be readable by apache
    WSGIPythonHome /usr/local

    #NOTE: all urs below will need to be adjusted if
    #settings.FORUM_SCRIPT_ALIAS is anything other than empty string (e.g. = 'forum/')
    #this allows "rooting" forum at http://example.com/forum, if you like

    #replace with 127.0.0.1 with real IP address
    <VirtualHost 127.0.0.1:80>
         ServerAdmin you@example.com
         DocumentRoot /path/to/django-project
         ServerName example.come

         #aliases to serve static media directly
         #will probably need adjustment
         Alias /static/ /path/to/django-project/static/
         Alias /upfiles/ /path/to/django-project/askbot/upfiles/
         <DirectoryMatch "/path/to/django-project/askbot/skins/([^/]+)/media">
            Order deny,allow
            Allow from all
         </DirectoryMatch>
         <Directory "/path/to/django-project/askbot/upfiles">
            Order deny,allow
            Allow from all
         </Directory>
         #must be a distinct name within your apache configuration
         WSGIDaemonProcess askbot2
         WSGIProcessGroup askbot2
         WSGIScriptAlias / /path/to/django-project/django.wsgi
         #make all admin stuff except media go through secure connection
         <LocationMatch "/admin(?!/media)">
         RewriteEngine on
             RewriteRule /admin(.*)$ https://example.com/admin$1 [L,R=301]
             </LocationMatch>
         CustomLog /var/log/httpd/askbot/access_log common
         ErrorLog /var/log/httpd/askbot/error_log
         LogLevel debug
    </VirtualHost>
    #again, replace the IP address
    <VirtualHost 127.0.0.1:443>
         ServerAdmin you@example.com
         DocumentRoot /path/to/django-project
         ServerName example.com
         <LocationMatch "^(?!/admin)">
             RewriteEngine on
             RewriteRule django.wsgi(.*)$ http://example.com$1 [L,R=301]
         </LocationMatch>
         SSLEngine on
         #your SSL keys
         SSLCertificateFile /etc/httpd/ssl.crt/server.crt
         SSLCertificateKeyFile /etc/httpd/ssl.key/server.key
         Alias /admin/media/ /usr/local/lib/python2.6/site-packages/django/contrib/admin/media/
         WSGIScriptAlias / /path/to/django-project/django.wsgi
         CustomLog /var/log/httpd/askbot/access_log common
         ErrorLog /var/log/httpd/askbot/error_log
    </VirtualHost>

.. _mod_wsgi: http://code.google.com/p/modwsgi/
.. _django.wsgi: http://github.com/ASKBOT/askbot-devel/blob/master/askbot/setup_templates/django.wsgi
