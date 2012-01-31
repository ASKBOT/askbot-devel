.. _create-database:

==========================
Create database for Askbot
==========================

Askbot has been successfully tested with `MySQL` and `PostgreSQL` databases.

PostgreSQL
----------
PostgreSQL is the preferred database for Askbot - because it offers great
full text search functionality and supports transactions at the same time.

To use postgresql - install it (please see documentation elsewhere).

After you have the database inself, add python bindingngs to postgresql::

    pip install psycopg2==2.4.1

.. note::
    Note the specific version of the library required! There may be issues with the later version.

To create a database, log in to postgresql as user postgres, create a user (if necessary), create a database, and enable the user account to log in to the database::

    create role someuser with createdb login encrypted password `somepassword`;
    create database somedb with owner=someuser;

Then edit file ``pg_hba.conf`` within your database installation and add a line as the first non-comment line or near, to make sure that this rule takes precedence::

    local somedb someuser md5

Then restart the database server (probably as root user), the command may be::

    /etc/init.d/postgresql restart

MySQL
-----
This section assumes that MySQL is installed and is up and running.

Once you have the database installed (please see manual elsewhere), add python bindings for mysql::

    pip install mysql-python

Database can be prepared via your hosting control panel, if available, or
can be created manually as shown below (using a high privilege MySQL account):

Log in to mysql::

    mysql -u username -p

Then type these two commands (note that fake `dbname`, `dbuser`, and `dbpassword` are used in this example)::

    create database askbot DEFAULT CHARACTER SET UTF8 COLLATE utf8_general_ci;
    grant all privileges on dbname.* to dbuser@localhost identified by 'dbpassword';

Again, please remember to create real usernname, database name and password and write them down. These
credentials will go into the file `settings.py`_ - the main configuration file of the Django application.

.. note::

    Notation `dbuser@hostname` is important for security - normally you want to restrict access to
    the database to certain hosts only. `localhost` entry ensures that database cannot be accessed
    from remote hosts at all.

.. _Python: http://www.python.org/download/
.. _MySQL: http://www.mysql.com/downloads/mysql/#downloads 
.. _settings.py: http://github.com/ASKBOT/askbot-devel/blob/master/askbot/setup_templates/settings.py
