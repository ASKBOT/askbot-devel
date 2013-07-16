import datetime
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.utils import timezone

from optparse import make_option
from askbot.utils.console import ProgressBar
from askbot.models import Thread
from askbot.models import User

class Command(BaseCommand):
    help = """Adds tags to questions. Tags should be given via a file
    with one tag per line. The tags will be matched with the words
    found in the question title. Then, most frequently used matching tags
    will be applied. This command respects the maximum number of tags
    allowed per question.
    """
    option_list = BaseCommand.option_list + (
        make_option('--tags-file', '-t',
            action = 'store',
            type = 'str',
            dest = 'tags_file',
            default = None,
            help = 'file containing tag names, one per line'
        ),
    )
    def handle(self, *args, **kwargs):
        """reads the tags file, parses it,
        then applies tags to questions by matching them
        with the question titles and content
        """
        if kwargs['tags_file'] is None:
            raise CommandError('parameter --tags-file is required')
        try:
            tags_input = open(kwargs['tags_file']).read()
        except IOError:
            raise CommandError('file "%s" not found' % kwargs['tags_file'])

        tags_list = map(lambda v: v.strip(), tags_input.split('\n'))

        multiword_tags = list()
        for tag in tags_list:
            if ' ' in tag:
                multiword_tags.append(tag)

        if len(multiword_tags):
            message = 'multiword tags tags not allowed, have: %s' % ', '.join(multiword_tags)
            raise CommandError(message)

        threads = Thread.objects.all()
        count = threads.count()
        message = 'Applying tags to questions'

        user = User.objects.all().order_by('-id')[0]
        now = timezone.now()

        for thread in ProgressBar(threads.iterator(), count, message):
            thread.apply_hinted_tags(
                tags_list, user=user, timestamp=now, silent=True
            )
