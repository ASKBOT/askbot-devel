#!/usr/bin/env python

import os
import sys

project_dir = os.environ.get('ASKBOT_SITE')
app_dir = os.environ.get('ASKBOT_APP', 'askbot_app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'{app_dir}.settings')

os.chdir(project_dir)
if project_dir not in sys.path:
    sys.path = [ '', project_dir ] + sys.path[1:]

import askbot as _test_import_of_askbot

dsn = os.environ.get('DATABASE_URL', None)
admin_to_be_id = 1

do_migrate    = True
do_admin      = True
do_make_admin = True
do_uwsgi_ini  = True

from time import sleep

if dsn is not None and dsn.startswith('postgres'):
    import psycopg2
    print(f'Waiting for database {dsn}')
    for retry in range(1,10):
        try:
            d = psycopg2.connect(dsn) # i hope this takes its time ...
        except psycopg2.OperationalError as e: # DB not ready
            print(e)
    print('Database connected. Peeking...')
    c = d.cursor()
    c.execute("SELECT * FROM information_schema.tables WHERE table_name='askbot_post';")
    r = c.fetchone()
    if r is not None:
        print('Will not migrate')
        do_migrate = False
    d.rollback()
    try:
        c.execute("SELECT * FROM auth_user WHERE username='admin'")
        r = c.fetchone()
        if r is not None:
            print('Will not create admin user')
            do_admin = False
    except psycopg2.errors.UndefinedTable:
        pass
    d.rollback()
    try:
        c.execute(f"SELECT 1 FROM auth_user WHERE id='{admin_to_be_id}' AND is_superuser='yes';")
        r = c.fetchone()
        if r is not None:
            print('Will not make user admin superuser')
            do_make_admin = False
    except psycopg2.errors.UndefinedTable:
        pass
    c.close()
    d.close()

from django.core.management import execute_from_command_line

if do_migrate is True :
    print('Running migrate')
    argv = [ 'manage.py', 'migrate', '--no-input' ]
    execute_from_command_line(argv)

if do_admin is True and os.environ.get('ADMIN_PASSWORD') is not None:
    print('Adding admin user')
    argv = [ 'manage.py', 'askbot_add_user',
        '--user-name', 'admin',
        '--email', 'admin@localhost',
        '--password', os.environ.get('ADMIN_PASSWORD'),
        '--status', 'd' ]
    execute_from_command_line(argv)

if do_make_admin is True:
    print('Grant superuser to admin')
    argv = [ 'manage.py', 'add_admin', str(admin_to_be_id), '--noinput' ]
    execute_from_command_line(argv)

if do_uwsgi_ini is True:
    print('Preparing uwsgi.ini')
    with open(os.path.join(project_dir, app_dir, 'uwsgi.ini'), 'a') as ini:
        ini.write("\n")
        for rule in [ f'pythonpath = {p}' for p in sys.path]:
            ini.write(rule + "\n")

if os.environ.get('NO_CRON') is None:
    print('Preparing cron_environ')
    with open('/cron_environ', 'w+') as cron_env:
        for var in [ f'{name}="{os.environ.get(name)}"'
            for name in [ 'PATH', 'DATABASE_URL', 'SECRET_KEY',
                       'PYTHONUNBUFFERED', 'ASKBOT_SITE' ]]:
            cron_env.write(var + "\n")
        cron_env.write("PYTHONPATH='{}'\n".format(str.join(":", sys.argv)))
