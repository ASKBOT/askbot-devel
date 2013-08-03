===================
Askbot - Q&A forum
===================

This is Askbot project - open source Q&A system, like StackOverflow, Yahoo Answers and some others

Demos and hosting are available at http://askbot.com.

**Translators:** please translate at https://www.transifex.com/projects/p/askbot/.

All documentation is in the directory askbot/doc

Askbot is based on code of CNPROG, originally created by Mike Chen 
and Sailing Cai and some code written for OSQA. Askbot had officially launched
in April 2010.


Installation
============

**first create a virtual environment**

    virtualenv askbotenv --no-site-packages
    source askbotenv/bin/activate

install askbot
--------------

    pip install askbot
    
Or clone the code from the development repository:
--------------------------------------------------

    git clone git://github.com/suhailvs/askbot-devel.git <project_name>
    cd <project_name>
    
    python setup.py develop #the develop option will not install askbot into the python site packages directory

    
**connect to mysql and install database**

    mysql -u USERNAME -pPASSWORD
    
    mysql> create database askbot;
    
**install askbot as a new django project**

    mkdir mydjangosite
    cd mydjangosite
    askbot-setup
    
if prompt for database select mysql
then:

    python manage.py syncdb
    python manage.py migrate
    python manage.py runserver

now you can browse askbot at localhost:8000
