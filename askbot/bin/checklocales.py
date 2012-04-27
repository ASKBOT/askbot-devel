import os
import subprocess

locales = os.listdir('locale')
for locale in locales:
    command = 'msgfmt -c locale/%s/LC_MESSAGES/django.po' % locale
    subprocess.call(command.split())
    print command
    command = 'msgfmt -c locale/%s/LC_MESSAGES/djangojs.po' % locale
    print command
    subprocess.call(command.split())
