=======================
Sending email to askbot
=======================

Askbot supports posting replies by email as well as posting questions by email.

If this feature is enabled, email alerts will be answerable via sending email
to unique "reply-to" email addresses provided with the messages.

To ask - send email to `ask@<your domain name>`.

For this feature  to work ``Lamson`` and ``django-lamson`` need to be installed on the system. To install all the necessery dependencies execute the following command:
    
    pip install django-lamson

.. note::
    On Windows installation of the Lamson module may require
    additional work. Askbot does not support this feature
    on Windows automatically.

The lamson daemon needs a folder to store it's mail queue files and a folder to store log files, create the folders folder named ``run`` and ``logs`` within your project folder by executing the following commands:

    mkdir run

    mkdir logs

The minimum settings required to enable this feature are defining the port and binding address for the lamson SMTP daemon and the email handlers within askbot. Edit your settings.py file to include the following::

    LAMSON_RECEIVER_CONFIG = {'host': 'your.ip.address', 'port': 25}
    LAMSON_HANDLERS = ['askbot.mail.lamson_handlers']
    LAMSON_ROUTER_DEFAULTS = {'host': '.+'}

In the list of ``installed_apps`` add the app ``django_lamson``.

The ``LAMSON_RECEIVER_CONFIG`` parameter defines the binding address/port for the SMTP daemon. To recieve internet email you will need to bind to your external ip address and port 25. If you just want to test the feature by sending eamil from the same system you could bind to 127.0.0.1 and any higher port. 

To run the lamson SMTP daemon you will need to execute the following management command::
    
    python manage.py lamson_start

To stop the daemon issue the following command::

    python manage.py lamson_stop

Note that in order to be able to bind the daemon to port 25 you will need to execute the command as a superuser.

Within the askbot admin interface there are 4 significant configuration points for this feature.

* In the email section, the "Enable posting answers and comments by email" controls whether the feature is enabled or disabled.
* The "reply by email hostname" needs to be set to the email hostname where you want to receive the email replies. If for example this is set to "example.com" the users will post replies to addresses such as "4wffsw345wsf@example.com", you need to point the MX DNS record for that domain to the address where you will run the lamson SMTP daemon.
* The last setting in this section controls the threshold for minimum length of the reply that is posted as an answer to a question. If the user is replying to a notification for a question and the reply  body is shorter than this threshold the reply will be posted as a comment to the question.
* In the karma thresholds section the "Post answers and comments by email" defines the minimum karma for users to be able to post replies by email.

If the system where lamson is hosted also acts as an email server or you simply want some of the emails to be ignored and sent to another server you can define forward rules. Any emails matching these rules will be sent to another smtp server, bypassing the reply by email function. As an example by adding the following in your settings.py file::

    LAMSON_FORWARD = (
        {
           'pattern': '(.*?)@(.subdomain1|subdomain2)\.example.com',
           'host': 'localhost',
           'port': 8825
        },
        {
           'pattern': '(info|support)@example.com',
           'host': 'localhost',
           'port': 8825
        },

    )

any email that was sent to anyaddress@sobdomain1.example.com or anyaddress@sobdomain2.example.com or info@example.com will be forwarded to the smtp server listening on port 8825. The pattern parameter is treated as a regular expression that is matched against  the ``To`` header of the email message and the ``host`` and ``port`` are the host and port of the smtp server that the message should be forwarded to.

If you want to run the lamson daemon on a port other than 25 you can use a mail proxy server such as ``nginx`` that will listen on port 25 and forward any SMTP requests to lamson. Using nginx you can also setup more complex email handling rules, such as for example if the same server where askbot is installed acts as an email server for other domains you can configure nginx to forward any emails directed to your askbot installation to lamson and any other emails to the mail server you're using, such as ``postfix``. For more information on how to use nginx for this please consult the nginx mail module documentation `nginx mail module documentation <http://wiki.nginx.org/MailCoreModule>`_ .
