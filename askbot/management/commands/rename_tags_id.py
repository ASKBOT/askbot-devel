"""management command that transfer tag usage data from
one tag to another and deletes the "from" tag

both "from" and "to" tags are identified by id

also, corresponding questions are retagged
"""
import re
import sys
from optparse import make_option
from django.conf import settings as django_settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import translation
from askbot import const, models
from askbot.utils import console
from askbot.management.commands.rename_tags import get_admin

def get_tags_by_ids(tag_ids):
    tags = list()
    for tag_id in tag_ids:
        try:
            tags.append(models.Tag.objects.get(id = tag_id))
        except models.Tag.DoesNotExist:
            raise CommandError('tag with id=%s not found' % tag_id)
    return tags

def get_similar_tags_from_strings(tag_strings, tag_name):
    """returns a list of tags, similar to tag_name from a set of questions"""

    grab_pattern = r'\b([%(ch)s]*%(nm)s[%(ch)s]*)\b' % \
                {'ch': const.TAG_CHARS, 'nm': tag_name}
    grab_re = re.compile(grab_pattern, re.IGNORECASE)

    similar_tags = set()
    for tag_string in tag_strings:
        similar_tags.update(
            grab_re.findall(tag_string)
        )
    return similar_tags

def parse_tag_ids(input):
    input = input.strip().split(' ')
    return set([int(i) for i in input])

def get_tag_names(tag_list):
    return set([tag.name for tag in tag_list])

def format_tag_name_list(tag_list):
    name_list = get_tag_names(tag_list)
    return u', '.join(name_list)

class Command(BaseCommand):
    "The command object itself"

    help = """Retags questions from one set of tags to another, like
rename_tags, but using tag id's


"""
    option_list = BaseCommand.option_list + (
        make_option('--from',
            action = 'store',
            type = 'str',
            dest = 'from',
            default = None,
            help = 'list of tag IDs which needs to be replaced'
        ),
        make_option('--to',
            action = 'store',
            type = 'str',
            dest = 'to',
            default = None,
            help = 'list of tag IDs that are to be used instead'
        ),
        make_option('--user-id',
            action = 'store',
            type = 'int',
            dest = 'user_id',
            default = None,
            help = 'id of the user who will be marked as a performer of this operation'
        ),
    )

    #@transaction.commit_manually
    def handle(self, *args, **options):
        """command handle function. retrieves tags by id
        """
        translation.activate(django_settings.LANGUAGE_CODE)
        try:
            from_tag_ids = parse_tag_ids(options['from'])
            to_tag_ids = parse_tag_ids(options['to'])
        except:
            raise CommandError('Tag IDs must be integer')

        in_both = from_tag_ids & to_tag_ids
        if in_both:
            tag_str = ', '.join([str(i) for i in in_both])
            if len(in_both) > 1:
                error_message = 'Tags with IDs %s appear ' % tag_str
            else:
                error_message = 'Tag with ID %s appears ' % tag_str
            raise CommandError(error_message + 'in both --from and --to sets')

        from_tags = get_tags_by_ids(from_tag_ids)
        to_tags = get_tags_by_ids(to_tag_ids)

        #all tags must belong to the same language
        lang_codes = set(tag.language_code for tag in (from_tags + to_tags))
        if len(lang_codes) != 1:
            langs = ', '.join(lang_codes)
            raise CommandError('all tags must belong to the same language, have: %s' % langs)
        lang = list(lang_codes).pop()

        admin = get_admin(options['user_id'])

        questions = models.Thread.objects.all()
        for from_tag in from_tags:
            questions = questions.filter(tags=from_tag)

        #print some feedback here and give a chance to bail out
        question_count = questions.count()
        if question_count == 0:
            print """Did not find any matching questions,
you might want to run prune_unused_tags
or repost a bug, if that does not help"""
        elif question_count == 1:
            print "One question matches:"
        elif question_count <= 10:
            print "%d questions match:" % question_count
        if question_count > 10:
            print "%d questions match." % question_count
            print "First 10 are:"
        for question in questions[:10]:
            print '* %s' % question.title.strip()

        formatted_from_tag_names = format_tag_name_list(from_tags)
        formatted_to_tag_names = format_tag_name_list(to_tags)

        if not options.get('is_force', False):
            prompt = 'Rename tags %s --> %s?' % (formatted_from_tag_names, formatted_to_tag_names)
            choice = console.choice_dialog(prompt, choices=('yes', 'no'))
            if choice == 'no':
                print 'Canceled'
                sys.exit()
        else:
            print 'Renaming tags %s --> %s' % (formatted_from_tag_names, formatted_to_tag_names)
        sys.stdout.write('Processing:')

        from_tag_names = get_tag_names(from_tags)
        to_tag_names = get_tag_names(to_tags)

        #if user provided tag1 as to_tag, and tagsynonym tag1->tag2 exists.
        for to_tag_name in to_tag_names:
            try:
               tag_synonym =  models.TagSynonym.objects.get(
                                                source_tag_name=to_tag_name,
                                                language_code=lang
                                            )
               raise CommandError(u'You gave %s as --to argument, but TagSynonym: %s -> %s exists, probably you want to provide %s as --to argument' % (to_tag_name, tag_synonym.source_tag_name, tag_synonym.target_tag_name, tag_synonym.target_tag_name))
            except models.TagSynonym.DoesNotExist:
                pass


        #actual processing stage, only after this point we start to
        #modify stuff in the database, one question per transaction
        i = 0
        for question in questions:
            tag_names = set(question.get_tag_names())
            tag_names.update(to_tag_names)
            tag_names.difference_update(from_tag_names)

            admin.retag_question(
                question = question._question_post(),
                tags = u' '.join(tag_names),
                #silent = True #do we want to timestamp activity on question
            )
            question.invalidate_cached_summary_html()
            i += 1
            sys.stdout.write('%6.2f%%' % (100*float(i)/float(question_count)))
            sys.stdout.write('\b'*7)
            sys.stdout.flush()

        sys.stdout.write('\n')
        #transaction.commit()

        #may need to run assertions on that there are
        #print 'Searching for similar tags...',
        #leftover_questions = models.Thread.objects.filter(
        #                        icontains=from_tag.name
        #                    )
        #if leftover_questions.count() > 0:
        #    tag_strings = leftover_questions.values_list('tagnames', flat=True)
        #    similar_tags = get_similar_tags_from_strings(
        #                                        tag_strings,
        #                                        from_tag.name
        #                                    )
        #    print '%d found:' % len(similar_tags),
        #    print '\n*'.join(sorted(list(similar_tags)))
        #else:
        #    print "None found."
        #print "Done."
        #transaction.commit()

        # A user wants to rename tag2->tag3 and tagsynonym tag1->tag2 exists.
        # we want to update tagsynonym (tag1->tag2) to (tag1->tag3)
        for from_tag_name in from_tag_names:
            # we need db_index for target_tag_name as well for this
            models.TagSynonym.objects.filter(
                                target_tag_name=from_tag_name,
                                language_code=lang
                            ).update(target_tag_name = to_tag_name)
