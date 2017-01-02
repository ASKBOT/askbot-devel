import ez_setup
ez_setup.use_setuptools()
from setuptools import setup, find_packages
import sys

#NOTE: if you want to develop askbot
#you might want to install django-debug-toolbar as well

import askbot

setup(
    name = "askbot",
    version = askbot.get_version(),#remember to manually set this correctly
    description = 'Question and Answer forum, like StackOverflow, written in python and Django',
    packages = find_packages(exclude=['testproject']),
    author = 'Evgeny.Fadeev',
    author_email = 'evgeny.fadeev@gmail.com',
    license = 'GPLv3',
    keywords = 'forum, community, wiki, Q&A',
    entry_points = {
        'console_scripts' : [
            'askbot-setup = askbot.deployment:askbot_setup',
        ]
    },
    url = 'http://askbot.org',
    include_package_data = True,
    install_requires = askbot.REQUIREMENTS.values(),
    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Natural Language :: English',
        'Natural Language :: Finnish',
        'Natural Language :: German',
        'Natural Language :: Russian',
        'Natural Language :: Serbian',
        'Natural Language :: Turkish',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.5',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: JavaScript',
        'Topic :: Communications :: Usenet News',
        'Topic :: Communications :: Email :: Mailing List Servers',
        'Topic :: Communications',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
    ],
    long_description = """Askbot will work alone or with other django apps (with some limitations, please see below), Django 1.8, PostgresQL(recommended) and MySQL(**) (MyISAM backend only - see footnote **)

    This version of Askbot supports only Django 1.8.

    To upgrade, or select version of Askbot working with earlier versions of Django,
    please follow instructions at
    https://github.com/ASKBOT/askbot-devel/blob/master/askbot/doc/source/upgrade.rst

Questions? Suggestions? Found a bug? -> please post at http://askbot.org/en/questions/

Features
========

* standard Q&A functionalities including votes, reputation system, etc.
* user levels: admin, moderator, regular, suspended, blocked
* per-user inbox for responses & flagged items (for moderators)
* email alerts - instant and delayed, optionally tag filtered
* search by full text and a set of tags simultaneously
* imports data from StackExchange, Jive, ZenDesk

Installation
============

The general steps are:

* install the code
* if there is no database yet - create one
* create a new or configure existing django site for askbot
* create/update the database tables

Methods to install code
-----------------------

* **pip install askbot**
* **download .tar.gz** file from the bottom of this page, then run **python setup.py install**
* clone code from the github **git clone git://github.com/ASKBOT/askbot-devel.git**, and then **python setup.py develop**

Create/configure django site
----------------------------

Either run command **askbot-setup** or merge contents of directory **askbot/setup_templates** in the source code into your project directory.


Create/update database tables
-----------------------------

Back up your database if it is not blank, then two commands:

* python manage.py syncdb
* python manage.py migrate

There are two apps to migrate - askbot and django_authopenid (a forked version of the original, included within askbot), so you can as well migrate them separately

Limitations
===========

There are some limitations that will be removed in the future. If any of these cause issues - please do not hesitate to contact support@askbot.com.

Askbot patches `auth_user` table. The migration script will automatically add missing columns, however it will not overwrite any existing columns. Please do back up your database before adding askbot to an existing site.

Included into askbot there are two forked apps: `django_authopenid` and `livesettings`. If you have these apps on your site, you may have trouble installing askbot.

User registration and login system is bundled with Askbot, but can be replaced with any other. It is quite good though, it allows logging in with password and many authentication service providers, including popular social services and recover account by email.

If there are any other collisions, askbot will simply fail to install, it will not damage your data.

Background Information
======================
Askbot is based on CNPROG project by Mike Chen and Sailing Cai, project which was originally inspired by StackOverflow and Yahoo Answers.

Footnotes
=========
(**) - With MySQL you have to use MyISAM data backend, because it's the only one that supports Full Text Search."""
)

print """**************************************************************
*                                                            *
*  Thanks for installing Askbot.                             *
*                                                            *
*  To start deploying type: askbot-setup                     *
*                                                            *
*  Please take a look at the manual http://askbot.org/doc/   *
*  And please do not hesitate to ask your questions at       *
*  at http://askbot.org/en/questions/                        *
*                                                            *
**************************************************************"""
