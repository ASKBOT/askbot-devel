#!/usr/bin/env python
"""
Rebuild locale files for askbot.

Run from the project root:
    ./env-md/bin/python askbot/bin/rebuildlocales.py

This script:
1. Runs jinja2_makemessages for HTML/Python/text templates
2. Runs Django's makemessages (bypassing django_jinja) for JS/Svelte files
"""
import os
import subprocess
import sys

# Ensure we're in the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(PROJECT_ROOT)

locales = os.listdir('askbot/locale')

IGNORE_PATTERNS = ['env', 'env-*', 'env[0-9]*', '.git', '.history', 'node_modules', 'testproject']


def call_jinja2_makemessages(locale):
    """Run jinja2_makemessages from project root directory."""
    ignore_args = ' '.join(f'--ignore={p}' for p in IGNORE_PATTERNS)
    command = f'{sys.executable} askbot_site/manage.py jinja2_makemessages -l {locale} -e html,py,txt {ignore_args}'
    print(command)
    subprocess.call(
        command.split(),
        cwd=PROJECT_ROOT
    )


def run_djangojs_makemessages(locale):
    """Run Django's makemessages from askbot_site directory."""
    # Set up Django
    sys.path.insert(0, os.path.join(PROJECT_ROOT, 'askbot_site'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'askbot_site.settings')

    import django
    django.setup()
    from django.core.management.commands.makemessages import Command

    ignore_args = []
    for pattern in IGNORE_PATTERNS:
        ignore_args.extend(['--ignore', pattern])

    cmd = Command()
    argv = [
        'manage.py', 'makemessages',
        '-d', 'djangojs',
        '-l', locale,
        '-e', 'js,svelte',
    ] + ignore_args
    print(' '.join(argv))
    cmd.run_from_argv(argv)


for locale in locales:
    call_jinja2_makemessages(locale)
    run_djangojs_makemessages(locale)
