import sys
from django.core.management.base import NoArgsCommand
from django.db import transaction
from askbot import models
from askbot import forms
from askbot.utils import console
from askbot.models import signals
from askbot.conf import settings as askbot_settings

FORMAT_STRING = '%6.2f%%'

class Command(NoArgsCommand):
    def handle_noargs(self, **options):
        signal_data = signals.pop_all_db_signal_receivers()
        self.run_command()
        signals.set_all_db_signal_receivers(signal_data)

    @transaction.commit_manually
    def run_command(self):
        """method that runs the actual command"""
        #go through tags and find character case duplicates and eliminate them
        tagnames = models.Tag.objects.values_list('name', flat = True)
        for name in tagnames:
            dupes = models.Tag.objects.filter(name__iexact = name)
            first_tag = dupes[0]
            if dupes.count() > 1:
                line = 'Found duplicate tags for %s: ' % first_tag.name
                print line,
                for idx in xrange(1, dupes.count()):
                    print dupes[idx].name + ' ',
                    dupes[idx].delete()
                print ''
            if askbot_settings.FORCE_LOWERCASE_TAGS:
                lowercased_name = first_tag.name.lower()
                if first_tag.name != lowercased_name:
                    print 'Converting tag %s to lower case' % first_tag.name
                    first_tag.name = lowercased_name
                    first_tag.save()
        transaction.commit()

        #go through questions and fix tag records on each
        questions = models.Question.objects.all()
        checked_count = 0
        found_count = 0
        total_count = questions.count()
        print "Searching for questions with inconsistent tag records:",
        for question in questions:
            tags = question.thread.tags.all()
            denorm_tag_set = set(question.get_tag_names())
            norm_tag_set = set(question.thread.tags.values_list('name', flat=True))
            if norm_tag_set != denorm_tag_set:

                if question.last_edited_by:
                    user = question.last_edited_by
                    timestamp = question.last_edited_at
                else:
                    user = question.author
                    timestamp = question.added_at

                tagnames = forms.TagNamesField().clean(question.tagnames)

                question.thread.update_tags(
                    tagnames = tagnames,
                    user = user,
                    timestamp = timestamp
                )
                question.thread.tagnames = tagnames
                question.thread.save()
                found_count += 1

            transaction.commit()
            checked_count += 1
            progress = 100*float(checked_count)/float(total_count)
            console.print_progress(FORMAT_STRING, progress)
        print FORMAT_STRING % 100
        if found_count:
            print '%d problem questions found, tag records restored' % found_count
        else:
            print 'Did not find any problems'
