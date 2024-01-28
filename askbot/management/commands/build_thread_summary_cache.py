from django.core.management.base import BaseCommand
from django.conf import settings as django_settings
from django.utils import translation

from askbot.models import Thread
from askbot.utils.console import ProgressBar


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '-l',
            '--language',
            action='append',
            help='Specify the languages for which the cache has to be rebuilt.'
        )

    def handle(self, **options):
        languages = options['language'] or (django_settings.LANGUAGE_CODE,)
        for l in languages:
            translation.activate(l)
            message = f'Rebuilding {l.upper()} thread summary cache'
            count = Thread.objects.count()
            for thread in ProgressBar(Thread.objects.iterator(),
                                      count, message):
                thread.update_summary_html()
