
#todo: http://stackoverflow.com/questions/837828/how-to-use-a-slug-in-django
DEBUGME = False
import os
import re
import sys
from unidecode import unidecode
import zipfile
from django.conf import settings as django_settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import askbot.importers.stackexchange.parse_models as se_parser
from xml.etree import ElementTree as et
from django.db.models import fields
from django.db.utils import IntegrityError
from django.db import models
import askbot.models as askbot
import askbot.deps.django_authopenid.models as askbot_openid
import askbot.importers.stackexchange.models as se
from askbot.forms import EditUserEmailFeedsForm
from askbot.conf import settings as askbot_settings

try:
    from django.contrib.auth.models import Message as DjangoMessage
except ImportError:
    from askbot.models.message import Message as DjangoMessage

from django.utils.translation import gettext_lazy as _
from askbot.utils.console import ProgressBar
from askbot.utils.slug import slugify
from askbot.models.badges import award_badges_signal, award_badges
from askbot.importers.stackexchange.management import is_ready as importer_is_ready
from optparse import make_option
#from markdown2 import Markdown
#markdowner = Markdown(html4tags=True)

if DEBUGME == True:
    from guppy import hpy
    from askbot.utils import dummy_transaction as transaction
    HEAP = hpy()
else:
    #from django.db import transaction
    from askbot.utils import dummy_transaction as transaction

xml_read_order = (
        'VoteTypes','UserTypes','Users','Users2Votes',
        'Badges','Users2Badges','CloseReasons',#'FlatPages',
        'MessageTypes','PostHistoryTypes','PostTypes','SchemaVersion',
        'Settings','SystemMessages','ThemeResources','ThemeTextResources',
        #'ThrottleBucket',
        'UserHistoryTypes','UserHistory',
        'Users2Badges','VoteTypes','Users2Votes','MessageTypes',
        'Posts','Posts2Votes','PostHistory','PostComments',
        'ModeratorMessages','Messages','Comments2Votes', 'Passwords',
)

#association tables SE item id --> ASKBOT item id
#table associations are implied
#todo: there is an issue that these may be inconsistent with the database
USER = {}#SE User.id --> django(ASKBOT) User.id
QUESTION = {}
ANSWER = {}
COMMENT = {}
NUMBERED_NAME_RE = re.compile(r'^(.*)\*(\d+)\*$')

class X:#
    """class with methods for handling some details
    of SE --> ASKBOT mapping
    """
    badge_type_map = {'1':'gold','2':'silver','3':'bronze'}

    askbot_supported_id_providers = (
            'google','yahoo','aol','myopenid',
            'flickr','technorati',
            'wordpress','blogger','livejournal',
            'claimid','vidoop','verisign',
            'openidurl','facebook','local',
            'twitter' #oauth is not on this list, b/c it has no own url
            )

    #map SE VoteType -> askbot.User vote method
    #created methods with the same call structure in askbot.User
    #User.<vote_method>(post, timestamp=None, cancel=False)
    vote_actions = {
        'UpMod':'upvote',
        'DownMod':'downvote',
        'AcceptedByOriginator':'accept_best_answer',
        'Offensive':'flag_post',
        'Favorite':'toggle_favorite_question',
    }

    #these modes cannot be mixed
    #only wiki is assumed to be mixable
    exclusive_revision_modes = (
        'initial','edit','rollback','lock',
        'migrate','close','merge','delete',
    )

    #badges whose names don't match exactly, but
    #present in both SE and ASKBOT
    badge_exceptions = {# SE --> ASKBOT
        'Citizen Patrol':'Citizen patrol',#single #todo: why sentence case?
        'Strunk &amp; White':'Strunk & White',#single
        'Civic Duty':'Civic duty',
    }

    revision_type_map = {
        'Initial Title':'initial',
        'Initial Body':'initial',
        'Initial Tags':'initial',
        'Edit Title':'edit',
        'Edit Body':'edit',
        'Edit Tags':'edit',
        'Rollback Title':'rollback',
        'Rollback Body':'rollback',
        'Rollback Tags':'rollback',
        'Post Closed':'close',
        'Post Reopened':'close',
        'Post Deleted':'delete',
        'Post Undeleted':'delete',
        'Post Locked':'lock',
        'Post Unlocked':'lock',
        'Community Owned':'wiki',
        'Post Migrated':'migrate',
        'Question Merged':'merge',
    }

    close_reason_map = {
        1: _('duplicate question'),
        2: _('question is off-topic or not relevant'),
        3: _('too subjective and argumentative'),
        4: _('not a real question'),
        5: _('question contains offensive or malicious remarks'),
        6: _('question is not relevant or outdated'),
        7: _('too localized'),
        10: _('spam or advertising'),
    }

    @classmethod
    def get_message_text(cls, se_m):
        """try to intelligently translate
        SE message to ASKBOT so that it makese sense in
        our context
        """
        #todo: properly translate messages
        #todo: maybe work through more instances of messages
        if se_m.message_type.name == 'Badge Notification':
            return se_m.text
        else:
            if 'you are now an administrator' in se_m.text:
                return _('Congratulations, you are now an Administrator')
            elif re.search(r'^You have \d+ new',se_m.text):
                bits = se_m.text.split('.')
                text = bits[0]
                if se_m.user.id == -1:
                    return None
                url = cls.get_user(se_m.user).get_profile_url()
                return f'<a href="{url}?sort=responses">{text}</a>'
        return None

    @classmethod
    def get_post(cls, se_post):
        #todo: fix this hack - either in-memory id association table
        #or use database to store these associations
        try:
            if isinstance(se_post, se.PostComment):
                return askbot.Post.objects.get(id=COMMENT[se_post.id].id)
            post_type = se_post.post_type.name
            if post_type == 'Question':
                return askbot.Post.objects.get(id=QUESTION[se_post.id].id)
            elif post_type == 'Answer':
                return askbot.Post.objects.get(id=ANSWER[se_post.id].id)
            else:
                raise Exception('unknown post type %s' % post_type)
        except KeyError:
            return None

    @classmethod
    def get_close_reason(cls, se_reason):
        #todo: this is a guess - have not seen real data
        se_reason = int(se_reason)
        return str(cls.close_reason_map[se_reason])

    @classmethod
    def get_user(cls, se_user):
        #todo: same as get_post
        return askbot.User.objects.get(id=USER[se_user.id].id)

    @classmethod
    def get_post_revision_group_types(cls, rev_group):
        rev_types = {}
        for rev in rev_group:
            rev_type = cls.get_post_revision_type(rev)
            rev_types[rev_type] = 1
        rev_types = list(rev_types.keys())

        #make sure that exclusive rev modes are not mixed
        exclusive = cls.exclusive_revision_modes
        if len(rev_types) > 1 and all([t in exclusive for t in rev_types]):
            tstr = ','.join(rev_types)
            gstr = ','.join([str(rev.id) for rev in rev_group])
            msg = f'incompatible revision types {tstr} in PostHistory {gstr}'
            raise Exception(msg)
        return rev_types

    @classmethod
    def clean_tags(cls, tags):
        tags = re.subn(r'\s+',' ',tags.strip())[0]
        bits = tags.split(' ')
        tags = ' '.join([bit[1:-1] for bit in bits])
        tags = re.subn(r'\xf6','-',tags)[0]
        return tags

    @classmethod
    def get_screen_name(cls, se_user):
        """always returns unique screen name
        even if there are multiple users in SE
        with the same exact screen name
        """

        name = se_user.display_name

        if name is None:
            name = 'anonymous'
        name = name.strip()
        name = re.subn(r'\s+',' ',name)[0]#remove repeating spaces

        name_key = name.lower()#mysql seems to be case insensitive for uniqueness

        while True:
            try:
                u = askbot.User.objects.get(username = name)
                matches = NUMBERED_NAME_RE.search(name)
                if matches:
                    base_name = matches.group(1)
                    number = int(matches.group(2))
                    name = '%s*%d*' % (base_name, number + 1)
                else:
                    name = name + ' *1*'
            except askbot.User.DoesNotExist:
                return name

    @classmethod
    def get_email(cls, email):#todo: fix fringe case - user did not give email!
        if email is None:
            return askbot_settings.ANONYMOUS_USER_EMAIL
        else:
            assert(email != '')
            return email

    @classmethod
    def get_post_revision_type(cls, rev):
        rev_name = rev.post_history_type.name
        rev_type = cls.revision_type_map.get(rev_name, None)
        if rev_type is None:
            raise Exception('dont understand revision type %s' % rev)
        return rev_type

    #crude method of getting id provider name from the url
    @classmethod
    def get_openid_provider_name(cls, openid_url):
        openid_str = str(openid_url)
        bits = openid_str.split('/')
        base_url = bits[2] #assume this is base url
        url_bits = base_url.split('.')
        provider_name = url_bits[-2].lower()
        if provider_name not in cls.askbot_supported_id_providers:
            raise Exception('could not determine login provider for %s' % openid_url)
        return provider_name

    @staticmethod
    def blankable(input):
        if input is None:
            return ''
        else:
            return input

    @classmethod
    def parse_badge_summary(cls, badge_summary):
        badge_counts = [0,0,0]#gold, silver and bronze, respectively
        if badge_summary:
            badge_info_list = badge_summary.split(' ')
            for badge_info in badge_info_list:
                level, count = badge_info.split('=')
                badge_counts[int(level) - 1] = int(count)
        return badge_counts

    @classmethod
    def get_badge_name(cls, name):
        return slugify(cls.badge_exceptions.get(name, name).lower())

class Command(BaseCommand):
    help = """Loads StackExchange data from SE dump .zip file
it may be helpful to split this procedure in two:\n
* read the dump (with option --read-se-dump)
* transfer data to askbot (with option --process-data)
"""
    args = 'se_dump_dir'

    def add_arguments(self, parser):
        parser.add_argument(
            '-r', '--read-dump',
            action='store_true',
            dest='read_dump',
            default=False,
            help='Only read the the dump')
        parser.add_argument('-p', '--process-data',
            action='store_true',
            dest='process_data',
            default=False,
            help='Only process the data, assuming that the dump is loaded')

    def handle(self, *arg, **kwarg):

        if django_settings.DEBUG:
            raise CommandError(
                'Please set DEBUG to False in the settings.py to reduce '
                'RAM usage during the import process'
            )

        #process the command line arguments, if given
        if kwarg['read_dump'] is False and kwarg['process_data'] is False:
            #make them both true as a hack to simulate a condition where
            #no flags selected means the same as both are indeed selected
            kwarg['read_dump'] = True
            kwarg['process_data'] = True

        askbot_settings.update('LIMIT_ONE_ANSWER_PER_USER', False)

        if not importer_is_ready():
            raise CommandError(
                "Looks like stackexchange tables are not yet initialized in the database.\n"
                "Please, run command: \npython manage.py migrate\n"
                "then import the data."
            )


        award_badges_signal.disconnect(award_badges)

        if len(arg) < 1 or not os.path.isfile(arg[0]):
            raise CommandError('Error: first argument must be a zip file with the SE forum data')

        if kwarg['read_dump']:
            self.zipfile = self.open_dump(arg[0])
            #read the data into SE tables
            for item in xml_read_order:
                time_before = timezone.now()
                self.load_xml_file(item)
                transaction.commit()
                time_after = timezone.now()
                if DEBUGME == True:
                    print(time_after - time_before)
                    print(HEAP.heap())

        if kwarg['process_data'] is False:
            #that means we just wanted to load the xml dump to
            #do the second step in another go in order to have
            #more ram for the transfer of data from SE to Askbot databases
            return

        #this is important so that when we clean up messages
        #automatically generated by the procedures below
        #we do not delete old messages
        #todo: unfortunately this may need to be redone
        #when we upgrade to django 1.2 and definitely by 1.4 when
        #the current message system will be replaced with the
        #django messages framework
        self.save_askbot_message_id_list()

        #transfer data into ASKBOT tables
        print('Transferring users...')
        self.transfer_users()
        transaction.commit()
        print('done.')
        print('Transferring content edits...')
        sys.stdout.flush()
        self.transfer_question_and_answer_activity()
        transaction.commit()
        print('done.')
        print('Transferring view counts...')
        sys.stdout.flush()
        self.transfer_question_view_counts()
        transaction.commit()
        print('done.')
        print('Transferring comments...')
        sys.stdout.flush()
        self.transfer_comments()
        transaction.commit()
        print('done.')
        print('Transferring badges and badge awards...')
        sys.stdout.flush()
        self.transfer_badges()
        transaction.commit()
        print('done.')
        print('Transferring Q&A votes...')
        sys.stdout.flush()
        self.transfer_QA_votes()#includes favorites, accepts and flags
        transaction.commit()
        print('done.')
        print('Transferring comment votes...')
        sys.stdout.flush()
        self.transfer_comment_votes()
        transaction.commit()

        self.cleanup_messages()#delete autogenerated messages
        transaction.commit()
        self.transfer_messages()
        transaction.commit()

        #todo: these are not clear how to go about
        self.transfer_update_subscriptions()
        transaction.commit()
        self.transfer_tag_preferences()
        transaction.commit()
        self.transfer_meta_pages()
        transaction.commit()
        print('done.')

    def open_dump(self, path):
        """open the zipfile, raise error if it
        does not exist or does not contain files with expected names"""
        if not zipfile.is_zipfile(path):
            raise CommandError('%s is not a zip file' % path)
        dump = zipfile.ZipFile(path)
        filenames = [item.filename for item in dump.infolist()]
        for component in xml_read_order:
            expected_file = component + '.xml'
            if expected_file not in filenames:
                raise CommandError('file %s not found in the archive' % expected_file)
        return dump

    def save_askbot_message_id_list(self):
        id_list = list(DjangoMessage.objects.all().values('id'))
        self._askbot_message_id_list = id_list

    def cleanup_messages(self):
        """deletes messages generated by the load process
        """
        id_list = self._askbot_message_id_list
        mset = DjangoMessage.objects.all().exclude(id__in=id_list)
        mset.delete()

    def transfer_messages(self):
        """transfers some messages from
        SE to ASKBOT
        """
        messages = se.Message.objects.all()
        for m in ProgressBar(messages.iterator(), messages.count()):
            if m.is_read:
                continue
            if m.user is None:
                continue
            if m.user.id == -1:
                continue
            u = X.get_user(m.user)
            text = X.get_message_text(m)
            if text:
                u.message_set.create(
                    message=text,
                )

    def _process_post_initial_revision_group(self, rev_group):

        title = None
        text = None
        tags = None
        wiki = False
        author = USER[rev_group[0].user.id]
        added_at = rev_group[0].creation_date

        for rev in rev_group:
            rev_type = rev.post_history_type.name
            if rev_type == 'Initial Title':
                title = rev.text
            elif rev_type == 'Initial Body':
                text = rev.text
            elif rev_type == 'Initial Tags':
                tags = X.clean_tags(rev.text)
            elif rev_type == 'Community Owned':
                wiki = True
            else:
                raise Exception('unexpected revision type %s' % rev_type)

        post_type = rev_group[0].post.post_type.name
        if post_type == 'Question':
            q = author.post_question(
                        title = title,
                        body_text = text,
                        tags = tags,
                        wiki = wiki,
                        timestamp = added_at
                    )
            QUESTION[rev_group[0].post.id] = q
        elif post_type == 'Answer':
            q = X.get_post(rev_group[0].post.parent)
            if q is None:
                return
            a = author.post_answer(
                        question = q,
                        body_text = text,
                        wiki = wiki,
                        timestamp = added_at
                    )
            ANSWER[rev_group[0].post.id] = a
        else:
            post_id = rev_group[0].post.id
            raise Exception('unknown post type %s for id=%d' % (post_type, post_id))

    def _process_post_edit_revision_group(self, rev_group):
        #question apply edit
        (title, text, tags) = (None, None, None)
        for rev in rev_group:
            rev_type = rev.post_history_type.name
            if rev_type == 'Edit Title':
                title = rev.text
            elif rev_type == 'Edit Body':
                text = rev.text
            elif rev_type == 'Edit Tags':
                tags = X.clean_tags(rev.text)
            elif rev_type == 'Community Owned':
                pass
            else:
                raise Exception('unexpected revision type %s' % rev_type)

        rev0 = rev_group[0]
        edited_by = USER[rev0.user.id]
        edited_at = rev0.creation_date
        comment = ';'.join([rev.comment for rev in rev_group if rev.comment])
        if len(comment) > 300:#truncate to make the db happy
            comment = comment[:300]
        post_type = rev0.post.post_type.name

        post = X.get_post(rev0.post)
        if post is None:
            return
        if post_type == 'Question':
            edited_by.edit_question(question=post,
                                    title=title,
                                    body_text=text,
                                    tags=tags,
                                    revision_comment=comment,
                                    timestamp=edited_at,
                                    force=True) #avoid insufficient rep issue on imports
        elif post_type == 'Answer':
            edited_by.edit_answer(timestamp=edited_at,
                                  body_text=text,
                                  revision_comment=comment)

    def _make_post_wiki(self, rev_group):
        #todo: untested
        for rev in rev_group:
            if rev.post_history_type.name == 'Community Owned':
                p = X.get_post(rev.post)
                if p is None:
                    return
                u = X.get_user(rev.user)
                t = rev.creation_date
                p.wiki = True
                p.wikified_at = t
                p.wikified_by = u
                self.mark_activity(p,u,t)
                p.save()
                return

    def mark_activity(self,p,u,t):
        """p,u,t - post, user, timestamp
        """
        p.thread.set_last_activity_info(last_activity_by=u, last_activity_at=t)

    def _process_post_rollback_revision_group(self, rev_group):
        #todo: don't know what to do here as there were no
        #such data available
        pass

    def _process_post_lock_revision_group(self, rev_group):
        #todo: untested
        for rev in rev_group:
            rev_type = rev.post_history_type.name
            if rev_type.endswith('ocked'):
                t = rev.creation_date
                u = X.get_user(rev.user)
                p = X.get_post(rev.post)
                if p is None:
                    return
                if rev_type == 'Post Locked':
                    p.locked = True
                    p.locked_by = u
                    p.locked_at = t
                elif rev_type == 'Post Unlocked':
                    p.locked = False
                    p.locked_by = None
                    p.locked_at = None
                else:
                    return
                self.mark_activity(p,u,t)
                p.save()
                return

    def _process_post_close_revision_group(self, rev_group):
        #todo: untested
        for rev in rev_group:
            if rev.post.post_type.name != 'Question':
                return
            rev_type = rev.post_history_type.name
            if rev_type in ('Post Closed', 'Post Reopened'):
                t = rev.creation_date
                u = X.get_user(rev.user)
                p = X.get_post(rev.post)
                if p is None:
                    return
                if rev_type == 'Post Closed':
                    p.thread.set_closed_status(closed=True, closed_at=t, closed_by=u, close_reason_text=X.get_close_reason(rev.comment))
                elif rev_type == 'Post Reopened':
                    p.thread.set_closed_status(closed=False, closed_at=None, closed_by=None, close_reason_text='')
                self.mark_activity(p,u,t)
                p.save()
                return

    def _process_post_delete_revision_group(self, rev_group):
        #todo: untested
        for rev in rev_group:
            rev_type = rev.post_history_type.name
            if rev_type.endswith('eleted'):
                t = rev.creation_date
                u = X.get_user(rev.user)
                p = X.get_post(rev.post)
                if p is None:
                    return
                if rev_type == 'Post Deleted':
                    p.deleted = True
                    p.deleted_at = t
                    p.deleted_by = u
                elif rev_type == 'Post Undeleted':
                    p.deleted = False
                    p.deleted_at = None
                    p.deleted_by = None
                self.mark_activity(p,u,t)
                p.save()
                return

    def _process_post_revision_group(self, rev_group):
        #determine revision type
        #'initial','edit','rollback','lock',
        #'migrate','close','merge','delete',
        if rev_group[0].user is None:
            #drop userless revisions - those are probably garbage posts
            #by the deleted users
            return
        rev_types = X.get_post_revision_group_types(rev_group)
        if 'initial' in rev_types:
            self._process_post_initial_revision_group(rev_group)
        elif 'edit' in rev_types:
            self._process_post_edit_revision_group(rev_group)
        elif 'rollback' in rev_types:
            self._process_post_rollback_revision_group(rev_group)
        elif 'lock' in rev_types:
            self._process_post_lock_revision_group(rev_group)
        elif 'close' in rev_types:
            self._process_post_close_revision_group(rev_group)
        elif 'delete' in rev_types:
            self._process_post_delete_revision_group(rev_group)
        else:
            pass
            #todo: rollback, lock, close and delete are
            #not tested
            #merge and migrate actions are ignored
        #wiki is mixable with other groups, so process it in addition
        if 'wiki' in rev_types:
            self._make_post_wiki(rev_group)

    def transfer_tag_preferences(self):
        #todo: figure out where these are stored in SE
        #maybe in se.User.preferences_raw?
        pass

    def transfer_question_and_answer_activity(self):
        """transfers all question and answer
        edits and related status changes
        """
        #assuming that there are only two post types
        se_revs = se.PostHistory.objects.all()
        #assuming that chronologial order is correct and there
        #will be no problems of data integrity upon insertion of records
        se_revs = se_revs.order_by('creation_date','revision_guid')
        #todo: ignored fringe case - no revisions
        c_guid = se_revs[0].revision_guid
        c_group = []
        #this loop groups revisions by revision id, then calls process function
        #for the revision grup (elementary revisions posted at once)
        message = 'Processing revisions'
        count = se_revs.count()
        for se_rev in ProgressBar(se_revs.iterator(), count, message):
            if se_rev.revision_guid == c_guid:
                c_group.append(se_rev)
            else:
                self._process_post_revision_group(c_group)
                c_group = []
                c_group.append(se_rev)
                c_guid = se_rev.revision_guid
            transaction.commit()
        if len(c_group) != 0:
            self._process_post_revision_group(c_group)

    def transfer_comments(self):
        comments = se.PostComment.objects.all()
        for se_c in ProgressBar(comments.iterator(), comments.count()):
            if se_c.deletion_date:
                print('Warning deleted comment %d dropped' % se_c.id)
                sys.stdout.flush()
                continue
            se_post = se_c.post
            askbot_post = X.get_post(se_post)
            if askbot_post is None:
                continue

            se_author = se_c.user
            if se_author is None:
                continue

            comment = askbot_post.add_comment(
                comment = se_c.text,
                added_at = se_c.creation_date,
                user = USER[se_author.id]
            )
            COMMENT[se_c.id] = comment

    def _collect_missing_badges(self):
        self._missing_badges = {}
        badges = se.Badge.objects.all()
        message = 'Collecting missing badges'
        for se_b in ProgressBar(badges.iterator(), badges.count(), message):
            name = X.get_badge_name(se_b.name)
            try:
                #todo: query badge from askbot.models.badges
                #using case-insensitive name matching
                askbot.badges.get_badge(name=name)
            except KeyError:
                #todo: if absent - print error message
                #and drop it
                self._missing_badges[name] = 0
                if len(se_b.description) > 300:
                    print('Warning truncated description for badge %d' % se_b.id)
                    sys.stdout.flush()

    def _award_badges(self):
        #note: SE does not keep information on
        #content-related badges like askbot does
        badges = se.User2Badge.objects.all()
        message = 'Awarding badges'
        for se_a in ProgressBar(badges.iterator(), badges.count(), message):
            if se_a.user.id == -1:
                continue #skip community user
            u = USER[se_a.user.id]
            badge_name = X.get_badge_name(se_a.badge.name)
            try:
                b = askbot.badges.get_badge(name=badge_name)
                if b.multiple == False:
                    if b.award_badge.filter(user = u).count() > 0:
                        #do not allow transfer of "multi" in SE -> single badge in AB
                        continue
                #todo: fake content object here b/c SE does not support this
                #todo: but askbot requires related content object
                askbot.Award.objects.create(
                    user=u,
                    badge=b.get_stored_data(),
                    awarded_at=se_a.date,
                    content_object=u,
                )
            except KeyError:
                #do not transfer badges that Askbot does not have
                self._missing_badges[badge_name] += 1
                continue

    def _report_missing_badges(self):
        d = self._missing_badges
        unused = [name for name in list(d.keys()) if d[name] == 0]
        dropped = [unidecode(name) for name in list(d.keys()) if d[name] > 0]
        print('Warning - following unsupported badges were dropped:')
        print(', '.join(dropped))
        sys.stdout.flush()

    def transfer_badges(self):
        #note: badge level is neglected
        #1) install missing badges
        self._collect_missing_badges()
        #2) award badges
        self._award_badges()
        #3) report missing badges
        self._report_missing_badges()
        pass

    def transfer_question_view_counts(self):
        questions = se.Post.objects.filter(post_type__name='Question')
        for se_q in ProgressBar(questions.iterator(), questions.count()):
            q = X.get_post(se_q)
            if q is None:
                continue
            q.thread.view_count = se_q.view_count
            q.thread.save()


    def transfer_QA_votes(self):
        votes = se.Post2Vote.objects.all()
        for v in ProgressBar(votes.iterator(), votes.count()):
            vote_type = v.vote_type.name
            if not vote_type in X.vote_actions:
                continue

            if v.user is None:
                continue

            u = X.get_user(v.user)
            p = X.get_post(v.post)
            if p is None:
                continue
            m = X.vote_actions[vote_type]
            vote_method = getattr(askbot.User, m)
            vote_method(
                u, p, timestamp = v.creation_date,
                force = True
            )
            if v.deletion_date:
                vote_method(
                    u, p, timestamp = v.deletion_date,
                    cancel=True,
                    force = True#force to avoid permission errors
                )
            transaction.commit()

    def transfer_comment_votes(self):
        votes = se.Comment2Vote.objects.all()
        for v in ProgressBar(votes.iterator(), votes.count()):
            vote_type = v.vote_type.name
            if vote_type not in ('UpMod', 'Offensive'):
                continue

            if v.user is None:
                continue

            p = X.get_post(v.post_comment)
            #could also check deletion date on the Comment2Vote object
            #instead of making get_post return None on KeyError inside
            if p is None:#may be a deleted post
                continue

            u = X.get_user(v.user)
            m = X.vote_actions[vote_type]
            vote_method = getattr(askbot.User, m)
            vote_method(
                u, p, timestamp = v.creation_date,
                force = True
            )
            transaction.commit()


    def transfer_update_subscriptions(self):
        #todo: not clear where this is stored in SE
        #maybe in se.User.preferences_raw?
        pass

    def transfer_meta_pages(self):
        #here we actually don't have anything in the database yet
        #so we can't do this
        pass

    def load_xml_file(self, item):
        """read data from the zip file for the item
        """
        xml_path = self.get_xml_path(item)
        table_name = self.get_table_name(item)

        xml_data = self.zipfile.read(xml_path)

        tree = et.fromstring(xml_data)
        print(f'loading from {xml_path} to {table_name}')
        model = models.get_model('stackexchange', table_name)
        i = 0
        rows = tree.findall('.//row')
        for row in ProgressBar(iter(rows), len(rows)):
            model_entry = model()
            i += 1
            for col in row.getchildren():
                field_name = se_parser.parse_field_name(col.tag)
                try:
                    field_type = model._meta.get_field(field_name)
                except fields.FieldDoesNotExist as e:
                    print("Warning: %s" % str(e))
                    continue
                field_value = se_parser.parse_value(col.text, field_type)
                setattr(model_entry, field_name, field_value)
            model_entry.save()
            #transaction.commit()
        print('... %d objects saved' % i)
        sys.stdout.flush()

    def get_table_name(self, xml_file_basename):
        return se_parser.get_table_name(xml_file_basename)

    def get_xml_path(self, xml_file_basename):
        return xml_file_basename + '.xml'

    def transfer_users(self):
        se_users = se.User.objects.all()
        for se_u in ProgressBar(se_users.iterator(), se_users.count()):
            #if se_u.id == -1:#skip the Community user
            #    continue
            u = askbot.User()
            u_type = se_u.user_type.name
            if u_type == 'Administrator':
                u.set_status('d')
            elif u_type == 'Moderator':
                u.set_status('m')
            elif u_type not in ('Unregistered', 'Registered'):
                raise Exception('unknown user type %s' % u_type)

            if se_u.password_id is not None:
                pw = se.Password.objects.get(id = se_u.password_id)
                u.password = f'sha1${pw.salt}${pw.password}'
            else:
                u.set_unusable_password()

            #if user is not registered, no association record created
            #we do not allow posting by users who are not authenticated
            #probably they'll just have to "recover" their account by email
            if u_type != 'Unregistered':
                try:
                    assert(se_u.open_id)#everybody must have open_id
                    u_openid = askbot_openid.UserAssociation()
                    u_openid.openid_url = se_u.open_id
                    u.save()
                    u_openid.user = u
                    u_openid.last_used_timestamp = se_u.last_login_date
                    u_openid.save()
                except AssertionError:
                    print('User %s (id=%d) does not have openid' % \
                            (unidecode(se_u.display_name), se_u.id))
                    sys.stdout.flush()
                except IntegrityError:
                    print("Warning: have duplicate openid: %s" % se_u.open_id)
                    sys.stdout.flush()

            if se_u.open_id is None and se_u.email is None:
                print('Warning: SE user %d is not recoverable (no email or openid)')
                sys.stdout.flush()

            u.reputation = 1#se_u.reputation, it's actually re-computed
            u.last_seen = se_u.last_access_date
            u.email = X.get_email(se_u.email)
            u.location = X.blankable(se_u.location)
            u.date_of_birth = se_u.birthday #dattime -> date
            u.website = X.blankable(se_u.website_url)
            if se_u.last_login_date is None:
                u.last_login = se_u.creation_date
            else:
                u.last_login = se_u.last_login_date
            u.date_joined = se_u.creation_date
            u.is_active = True #todo: this may not be the case

            u.username = X.get_screen_name(se_u)
            u.real_name = X.blankable(se_u.real_name)

            (gold,silver,bronze) = X.parse_badge_summary(se_u.badge_summary)
            u.gold = gold
            u.silver = silver
            u.bronze = bronze

            #todo: we don't have these fields
            #views - number of profile views?
            #has_replies
            #has_message
            #opt_in_recruit
            #last_login_ip
            #open_id_alt - ??
            #preferences_raw - not clear how to use
            #display_name_cleaned - lowercased, srtipped name
            #timed_penalty_date
            #phone

            #don't know how to handle these - there was no usage example
            #password_id
            #guid

            #ignored
            #last_email_date - this translates directly to EmailFeedSetting.reported_at

            #save the data
            try:
                other = askbot.User.objects.get(username = u.username)
                print('alert - have a second user with name %s' % u.username)
                sys.sdtout.flush()
            except askbot.User.DoesNotExist:
                pass

            u.save()
            u.update_localized_profile(about=X.blankable(se_u.about_me))

            form = EditUserEmailFeedsForm()
            form.reset()
            if se_u.opt_in_email == True:#set up daily subscription on "own" items
                form.initial['individually_selected'] = 'd'
                form.initial['asked_by_me'] = 'd'
                form.initial['answered_by_me'] = 'd'
            #
            form.save(user=u, save_unbound=True)
            USER[se_u.id] = u
