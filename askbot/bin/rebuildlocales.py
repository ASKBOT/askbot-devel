import os
import subprocess

locales = os.listdir('locale')

def call_command(command):
    print command
    subprocess.call(command.split())

for locale in locales:
    call_command(
        'python ../manage.py jinja2_makemessages -l %s -e html,py,txt' % locale
    )
    call_command(
        'python ../manage.py makemessages -l %s -d djangojs' % locale
    )
