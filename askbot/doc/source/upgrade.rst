How to upgrade Askbot
=====================

NOTE: always back up the database and customized files before upgrading!

These instructions assume that you are working with a Unix-like OS,
such as `Linux` or `MacOS` and a Python environment.

1) Introduction.
----------------

Askbot `0.13.x` supports Django `4.2` and `5.2` and requires `Python 3.10+`.
Earlier versions support older Django and Python releases - see the
compatibility table at the end of this document.

Askbot versions start with `0`, for example `0.11.2`.
Versions with different second numbers should be considered as different major versions.

When upgrading across multiple major versions, upgrade one major version at a time,
by upgrading to the latest release of each major version (explained in the section 2 below).

For example, when upgrading from `0.7.x` to `0.11.x`, it is best to upgrade to `0.8.x` first, then to `0.9.x`, and so on.

The best practice is to first make a test migration by creating a new
database with your current content,
then put your site in maintenance mode
and run the production migration.

2) Database migrations.
-----------------------

Configure a fresh uncustomized installation of Askbot of desired version.

First, decide which version of Python is required. For Askbot versions `0.12.x` and later, use `Python 3.10+`.
For `0.11.x` use `Python 3.6-3.10`, and for earlier versions use `Python 2.7`. Then install Askbot.

For example, for the latest `0.11.x` run:

    pip install 'askbot<0.12'

Configure this version by running `askbot-setup` and follow the instructions.
During the configuration, point your instance to the database.

Then, run the following command to upgrade the database:

    python manage.py migrate

When working with versions `0.8.x` and earlier, instead run the following command:

    python manage.py syncdb --migrate

Repeat the above steps until you have upgraded to the desired major version.

3) Finalize your upgrade.
-------------------------

One your database is migrated, you can integrate your customized settings into the project's `settings.py` file.

Finally, collect the static files:

  python manage.py collectstatic

Test your migration by running the dev server:

  python manage.py runserver

If everything works, your site can be deployed to the production.

4) Compatible versions of Askbot, Django and Python.
----------------------------------------------------

The following table shows the compatibility of Askbot versions with Django and Python versions.

+-----------------------+---------------------------------+-------------------+
| Version of Askbot (*) | Version of the Django framework | Version of Python |
+=======================+=================================+===================+
| `0.13.x`              | `4.2`, `5.2`                    | `3.10+`           |
+-----------------------+---------------------------------+-------------------+
| `0.12.x`              | `4.2`                           | `3.10+`           |
+-----------------------+---------------------------------+-------------------+
| `0.11.x`              | `2.x - 3.x`                     | `3.6-3.10`        |
+-----------------------+---------------------------------+-------------------+
| `0.10.x`              | `1.8.x`                         | `2.7`             |
+-----------------------+---------------------------------+-------------------+
| `0.9.x`               | `1.7.x`                         | `2.7`             |
+-----------------------+---------------------------------+-------------------+
| `0.8.x` (*)           | `1.6.x`                         | `2.7`             |
+-----------------------+---------------------------------+-------------------+
| `0.7.x`               | `1.5.x`                         | `2.7`             |
+-----------------------+---------------------------------+-------------------+

(*) Versions `0.8.x` are exclusively for migrating the database from `0.7.x` to `0.9.x`,
versions `0.8.x` should not be used in production.
