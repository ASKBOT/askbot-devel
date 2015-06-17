import sys
import optparse
from django.core.management.base import BaseCommand, CommandError
from askbot import models
from askbot import const

def get_tag_lines(tag_marks, width = 25):
    output = list()
    line = ''
    for name in tag_marks:
        if line == '':
            line = name
        elif len(line) + len(name) + 1 > width:
            output.append(line)
            line = name
        else:
            line += ' ' + name
    output.append(line)
    return output

def get_empty_lines(num_lines):
    output = list()
    for idx in xrange(num_lines):
        output.append('')
    return output

def pad_list(the_list, length):
    if len(the_list) < length:
        the_list.extend(get_empty_lines(length - len(the_list)))

def format_table_row(*cols, **kwargs):
    max_len = max(map(len, cols))
    for col in cols:
        pad_list(col, max_len)

    output = list()
    for idx in xrange(max_len):
        bits = list()
        for col in cols:
            bits.append(col[idx])
        line = kwargs['format_string'] % tuple(bits)
        output.append(line)

    return output


class Command(BaseCommand):
    help = 'Prints statistics of tag usage'

    option_list = BaseCommand.option_list + (
            optparse.make_option(
                '-t',
                '--sub-counts',
                action = 'store_true',
                default = False,
                dest = 'sub_counts',
                help = 'Print tag subscription statistics, for all tags, listed alphabetically'
            ),
            optparse.make_option(
                '-u',
                '--user-sub-counts',
                action = 'store_true',
                default = False,
                dest = 'user_sub_counts',
                help = 'Print tag subscription data per user, with users listed alphabetically'
            ),
            optparse.make_option(
                '-e',
                '--print-empty',
                action = 'store_true',
                default = False,
                dest = 'print_empty',
                help = 'Print empty records too (with zero counts)'
            ),
        )
    def handle(self, *args, **options):
        if not(options['sub_counts'] ^ options['user_sub_counts']):
            raise CommandError('Please use either -u or -t (but not both)')

        print ''
        if options['sub_counts']:
            self.print_sub_counts(options['print_empty'])

        if options['user_sub_counts']:
            self.print_user_sub_counts(options['print_empty'])
        print ''

    def print_user_sub_counts(self, print_empty):
        """prints list of users and what tags they follow/ignore
        """
        users = models.User.objects.all().order_by('username')
        item_count = 0
        for user in users:
            tag_marks = user.tag_selections

            #add names of explicitly followed tags
            followed_tags = list()
            followed_tags.extend(
                tag_marks.filter(
                            reason='good'
                        ).values_list(
                            'tag__name', flat = True
                        )
            )

            #add wildcards to the list of interesting tags
            followed_tags.extend(user.interesting_tags.split())

            for good_tag in user.interesting_tags.split():
                followed_tags.append(good_tag)

            ignored_tags = list()
            ignored_tags.extend(
                tag_marks.filter(
                    reason='bad'
                ).values_list(
                    'tag__name', flat = True
                )
            )

            for bad_tag in user.ignored_tags.split():
                ignored_tags.append(bad_tag)

            subscribed_tags = list()
            subscribed_tags.extend(
                tag_marks.filter(
                    reason='subscribed'
                ).values_list(
                    'tag__name', flat = True
                )
            )

            for subscribed_tag in user.subscribed_tags.split():
                subscribed_tags.append(subscribed_tag)

            followed_count = len(followed_tags)
            ignored_count = len(ignored_tags)
            subscribed_count = len(subscribed_tags)
            total_count = followed_count + ignored_count + subscribed_count
            if total_count == 0 and print_empty == False:
                continue
            if item_count == 0:
                print '%-28s %25s %25s %25s' % ('User (id)', 'Interesting tags', 'Ignored tags', 'Subscribed tags')
                print '%-28s %25s %25s %25s' % ('=========', '================', '============', '===============')
            followed_lines = get_tag_lines(followed_tags, width = 25)
            ignored_lines = get_tag_lines(ignored_tags, width = 25)
            subscribed_lines = get_tag_lines(subscribed_tags, width = 25)

            follow = '*'
            if user.email_tag_filter_strategy == const.INCLUDE_INTERESTING:
                follow = ''
            user_string = '%s (%d)%s' % (user.username, user.id, follow)
            output_lines = format_table_row(
                                [user_string,],
                                followed_lines,
                                ignored_lines,
                                subscribed_lines,
                                format_string = '%-28s %25s %25s %25s'
                            )
            item_count += 1
            for line in output_lines:
                print line
            print ''

        self.print_postamble(item_count)

    def get_wildcard_tag_stats(self):
        """This method collects statistics on all tags
        that are followed or ignored via a wildcard selection

        The return value is a dictionary, where keys are tag names
        and values are two element lists with whe first value - follow count
        and the second value - ignore count
        """
        wild = dict()#the dict that is returned in the end

        users = models.User.objects.all().order_by('username')
        for user in users:
            wk = user.interesting_tags.strip().split()
            interesting_tags = models.Tag.objects.get_by_wildcards(wk)
            for tag in interesting_tags:
                if tag.name not in wild:
                    wild[tag.name] = [0, 0, 0]
                wild[tag.name][0] += 1

            wk = user.ignored_tags.strip().split()
            ignored_tags = models.Tag.objects.get_by_wildcards(wk)
            for tag in ignored_tags:
                if tag.name not in wild:
                    wild[tag.name] = [0, 0, 0]
                wild[tag.name][1] += 1

            wk = user.subscribed_tags.strip().split()
            subscribed_tags = models.Tag.objects.get_by_wildcards(wk)
            for tag in subscribed_tags:
                if tag.name not in wild:
                    wild[tag.name] = [0, 0, 0]
                wild[tag.name][2] += 1

        return wild

    def print_sub_counts(self, print_empty):
        """prints subscription counts for
        each tag (ignored and favorite counts)
        """
        wild_tags = self.get_wildcard_tag_stats()
        tags = models.Tag.objects.all().order_by('name')
        item_count = 0
        for tag in tags:
            wild_follow = 0
            wild_ignore = 0
            wild_sub = 0
            if tag.name in wild_tags:
                (wild_follow, wild_ignore) = wild_tags[tag.name]

            tag_marks = tag.user_selections
            follow_count = tag_marks.filter(reason='good').count() \
                                                        + wild_follow
            ignore_count = tag_marks.filter(reason='bad').count() \
                                                        + wild_ignore
            subscribe_count = tag_marks.filter(reason='subscribe').count() \
                                                        + wild_sub
            follow_str = '%d (%d)' % (follow_count, wild_follow)
            ignore_str = '%d (%d)' % (ignore_count, wild_ignore)
            subscribe_str = '%d (%d)' % (subscribe_count, wild_sub)
            counts = (11-len(subscribe_str)) * ' ' + subscribe_str + '  '
            counts = (11-len(follow_str)) * ' ' + follow_str + '  '
            counts += (11-len(ignore_str)) * ' ' + ignore_str

            total_count = follow_count + ignore_count + subscribe_count
            if total_count == 0 and print_empty == False:
                continue
            if item_count == 0:
                print '%-32s %12s %12s %12s' % ('', 'Subscribed', 'Ignored  ', 'Interesting')
                print '%-32s %12s %12s %12s' % ('Tag name', 'Total(wild)', 'Total(wild)', 'Total(wild)')
                print '%-32s %12s %12s %12s' % ('========', '===========', '===========', '===========')
            print '%-32s %s' % (tag.name, counts)
            item_count += 1

        self.print_postamble(item_count)

    def print_postamble(self, item_count):
        print ''
        if item_count == 0:
            print 'Did not find anything'
        else:
            print '%d records shown' % item_count
        print 'Since -e option was not selected, empty records were hidden'
