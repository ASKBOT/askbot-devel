import re
import sys
from django.core.management.base import NoArgsCommand
from django.conf import settings as django_settings
from django.db import transaction
from django.utils import translation
from askbot import const
from askbot import models
from askbot import forms
from askbot.utils import console
from askbot.utils.slug import slugify_camelcase
from askbot import signals
from askbot.conf import settings as askbot_settings
from askbot.management.commands.rename_tags import get_admin

def get_valid_tag_name(tag):
    """Returns valid version of the tag name.
    If necessary, lowercases the tag.
    Strips the forbidden first characters in the tag.
    """
    name = tag.name
    if askbot_settings.FORCE_LOWERCASE_TAGS:
        #name = slugify_camelcase(name)
        name = name.lower()
    #if tag name starts with forbidden character, chop off that character
    #until no more forbidden chars are at the beginning
    first_char_regex = re.compile('^%s+' % const.TAG_FORBIDDEN_FIRST_CHARS)
    return first_char_regex.sub('', name)

class Command(NoArgsCommand):
    def handle_noargs(self, *args, **options):
        signal_data = signals.pop_all_db_signal_receivers()
        languages = models.Tag.objects.values_list('language_code').distinct()
        for lang in languages:
            self.run_command(lang)
        signals.set_all_db_signal_receivers(signal_data)

    def retag_threads(self, from_tags, to_tag):
        """finds threads matching the `from_tags`
        removes the `from_tags` from them and applies the
        to_tags"""
        threads = models.Thread.objects.filter(tags__in=from_tags)
        from_tag_names = [tag.name for tag in from_tags]
        for thread in threads:
            tagnames = set(thread.get_tag_names())
            tagnames.difference_update(from_tag_names)
            tagnames.add(to_tag.name)
            self.admin.retag_question(
                question=thread._question_post(),
                tags=' '.join(tagnames)
            )


    @transaction.commit_manually
    def run_command(self, lang):
        """method that runs the actual command"""
        #go through tags and find character case duplicates and eliminate them
        translation.activate(lang)
        tagnames = models.Tag.objects.filter(
                                language_code=lang
                            ).values_list('name', flat=True)
        self.admin = get_admin()

        #1) first we go through all tags and
        #either fix or delete illegal tags
        found_count = 0

        for name in tagnames:
            try:
                tag = models.Tag.objects.get(
                                        name=name,
                                        language_code=lang
                                    )
            except models.Tag.DoesNotExist:
                #tag with this name was already deleted,
                #because it was an invalid duplicate version
                #of other valid tag
                continue


            fixed_name = get_valid_tag_name(tag)

            #if fixed name is empty after cleaning, delete the tag
            if fixed_name == '':
                print 'Deleting invalid tag: %s' % name
                tag.delete()
                found_count += 1
                continue

            if fixed_name != name:
                print 'Renaming tag: %s -> %s' % (name, fixed_name)

            #if tag name changed, see if there is a duplicate
            #with the same name, in which case we re-assign questions
            #with the current tag to that other duplicate
            #then delete the current tag as no longer used
            if fixed_name != name:
                try:
                    duplicate_tag = models.Tag.objects.get(
                                                name=fixed_name,
                                                language_code=lang
                                            )
                except models.Tag.DoesNotExist:
                    pass
                self.retag_threads([tag], duplicate_tag)
                tag.delete()
                found_count += 1
                continue


            #if there are case variant dupes, we assign questions
            #from the case variants to the current tag and
            #delete the case variant tags
            dupes = models.Tag.objects.filter(
                                name__iexact=fixed_name,
                                language_code=lang
                            ).exclude(pk=tag.id)

            dupes_count = dupes.count()
            if dupes_count:
                self.retag_threads(dupes, tag)
                dupes.delete()
                found_count += dupes_count

            if tag.name != fixed_name:
                tag.name = fixed_name
                tag.save()

        transaction.commit()

        #2) go through questions and fix tag records on each
        # and recalculate all the denormalised tag names on threads
        threads = models.Thread.objects.all()
        checked_count = 0
        total_count = threads.count()
        print "Searching for questions with inconsistent copies of tag records:",
        for thread in threads:
            #make sure that denormalized tag set is the same as normalized
            #we just add both the tags together and try to apply them
            #to the question
            tags = thread.tags.all()
            denorm_tag_set = set(thread.get_tag_names())
            norm_tag_set = set(thread.tags.values_list('name', flat=True))

            if norm_tag_set != denorm_tag_set:
                denorm_tag_set.update(norm_tag_set)
                cleaned_tag_set = set(
                            models.Tag.objects.filter(
                                name__in=denorm_tag_set,
                                language_code=lang
                            ).values_list('name', flat=True)
                        )
                self.admin.retag_question(
                    question=thread._question_post(),
                    tags=' '.join(cleaned_tag_set)
                )

            transaction.commit()
            checked_count += 1
            console.print_progress(checked_count, total_count)
        console.print_progress(checked_count, total_count)

        if found_count:
            print '%d problem questions found, tag records restored' % found_count
        else:
            print 'Did not find any problems'
