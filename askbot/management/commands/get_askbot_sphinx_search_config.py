"""the management command that outputs configuration
for sphinx search"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.template import Template, Context
import askbot

class Command(BaseCommand):

    def handle(self, *args, **noargs):
        tpl_file = open(askbot.get_path_to('search/sphinx/sphinx.conf'))
        tpl = Template(tpl_file.read())
        context = Context({
            'db_name': settings.DATABASE_NAME,
            'db_user': settings.DATABASE_USER,
            'db_password': settings.DATABASE_PASSWORD
        })
        print tpl.render(context)
