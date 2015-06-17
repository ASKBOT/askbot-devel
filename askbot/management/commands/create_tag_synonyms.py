"""management command that creates a tag synonym
all corresponding questions are retagged
"""

import sys
from optparse import make_option
from django.conf import settings as django_settings
from django.core import management
from django.core.management.base import BaseCommand, CommandError
from askbot import models
from askbot.management.commands.rename_tags import get_admin
from askbot.utils import console
import datetime



def decode_input(input):
    decoded_input = input.decode(sys.stdin.encoding)
    decoded_input = decoded_input.strip()
    return decoded_input


class Command(BaseCommand):

    help = """create TagSynonym,
retags questions from source_tag_name to target_tag_name,
remove source_tag"""

    option_list = BaseCommand.option_list + (
        make_option('--from',
            action = 'store',
            type = 'str',
            dest = 'from',
            default = None,
            help = 'a source tag name which needs to be replaced'
        ),
        make_option('--to',
            action = 'store',
            type = 'str',
            dest = 'to',
            default = None,
            help = 'a target tag name that are to be used instead'
        ),
        make_option('--user-id',
            action = 'store',
            type = 'int',
            dest = 'user_id',
            default = None,
            help = 'id of the user who will be marked as a performer of this operation'
        ),
        make_option('--lang',
            action='store',
            type='str',
            dest='lang',
            default=django_settings.LANGUAGE_CODE,
            help='language code of the tag, e.g. "en"'
        )
    )

    def handle(self, *args, **options):
        """command handle function. reads tag names, decodes
        them using the standard input encoding and attempts to find
        the matching tags

        If "from" tag is not resolved, command fails
        if "to" tag is not resolved, a new tag is created
        """

        if options['from'] is None:
            raise CommandError('the --from argument is required')
        if options['to'] is None:
            raise CommandError('the --to argument is required')

        source_tag_name = decode_input(options['from'])
        target_tag_name = decode_input(options['to'])

        if source_tag_name == target_tag_name:
            raise CommandError("source and target tags appear to be the same")

        admin = get_admin(seed_user_id = options['user_id'])

        source_tag = None
        is_source_tag_created = False

        try:
            source_tag = models.Tag.objects.get(name=source_tag_name, language_code=options['lang'])
        except models.Tag.DoesNotExist:
            if not options.get('is_force', False):
                prompt = """source tag %s doesn't exist, are you sure you want to create a TagSynonym
    %s ==> %s?""" % (source_tag_name, source_tag_name, target_tag_name)
                choice = console.choice_dialog(prompt, choices=('yes', 'no'))
                if choice == 'no':
                    print 'Cancled'
                    sys.exit()
            source_tag = models.Tag.objects.create(
                                            name=source_tag_name,
                                            created_by=admin,
                                            language_code=options['lang']
                                        )
            is_source_tag_created = True


        # test if target_tag is actually synonym for yet another tag
        # when user asked tag2->tag3, we already had tag3->tag4.
        try:
            tag_synonym_tmp = models.TagSynonym.objects.get(
                                                source_tag_name=target_tag_name,
                                                language_code=options['lang']
                                            )
            if not options.get('is_force', False):
                prompt = """There exists a TagSynonym %s ==> %s,
    hence we will create a tag synonym %s ==> %s instead. Proceed?""" % (tag_synonym_tmp.source_tag_name, tag_synonym_tmp.target_tag_name,
                                                                         source_tag_name, tag_synonym_tmp.target_tag_name)
                choice = console.choice_dialog(prompt, choices=('yes', 'no'))
                if choice == 'no':
                    print 'Cancled'
                    sys.exit()
            target_tag_name = tag_synonym_tmp.target_tag_name
            options['to'] = target_tag_name
        except models.TagSynonym.DoesNotExist:
            pass

        try:
            models.Tag.objects.get(name=target_tag_name, language_code=options['lang'])
        except models.Tag.DoesNotExist:
            # we are creating a target tag, let's copy source tag's info
            # used_count are updated later
            models.Tag.objects.create(
                              name=target_tag_name,
                              created_by = admin,
                              status = source_tag.status,
                              tag_wiki = source_tag.tag_wiki,
                              language_code=options['lang']
                            )

        tag_synonym_tmp, created = models.TagSynonym.objects.get_or_create(
                                                                   source_tag_name=source_tag_name,
                                                                   target_tag_name=target_tag_name,
                                                                   owned_by=admin,
                                                                   language_code=options['lang']
                                                                )

        management.call_command('rename_tags', *args, **options)

        # When source_tag_name is a target_tag_name of already existing TagSynonym.
        # ie. if tag1->tag2 exists when user asked tag2->tag3
        # we are going to convert all tag1->tag2 to tag1->tag3 as well
        existing_tag_synonyms = models.TagSynonym.objects.filter(
                                                target_tag_name=source_tag_name,
                                                language_code=options['lang']
                                            )
        for existing_tag_synonym in existing_tag_synonyms:
            new_options = options.copy()
            new_options['from'] = existing_tag_synonym.source_tag_name
            new_options['user_id'] = admin.id
            new_options['is_force'] = True # this is mandatory conversion
            new_options['timestamp'] = datetime.datetime.now()
            existing_tag_synonym.delete() # no longer needed
            self.handle(*args, **new_options)

        # delete source Tag
        if is_source_tag_created:
            source_tag.delete()
        else:
            source_tag.deleted = True
            source_tag.deleted_at = options.get('timestamp', datetime.datetime.now())
            source_tag.deleted_by = admin
