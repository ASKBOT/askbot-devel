from askbot.deps.django_authopenid.models import UserAssociation
from askbot.management.commands.base import BaseImportXMLCommand
from askbot.models import Award
from askbot.models import BadgeData
from askbot.models import Post
from askbot.models import PostRevision
from askbot.models import Thread
from askbot.models import Tag
from askbot.models import User
from askbot.utils.slug import slugify_camelcase
from bs4 import BeautifulSoup
from datetime import datetime
from django.db.models import Q
from django.utils import translation
from django.conf import settings as django_settings
from django.utils.http import urlquote  as django_urlquote
from django.template.defaultfilters import slugify
from HTMLParser import HTMLParser

def decode_datetime(data):
    """Decodes formats:
    * '2013-10-25 09:46:34'
    * '2013-10-25'
    """
    if data:
        try:
            return datetime.strptime(data, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return datetime.strptime(data, '%Y-%m-%d')
    return None

class DataObject(object):
    def __init__(self, soup):
        """Initializes object based on the values passed
        via BeautifulSoup instance for that object"""
        self.soup = soup
        self.data = dict()

    def decode_typed_value(self, field):
        field_type = field['type']
        value = field.text.strip()
        if field_type == 'BooleanField':
            if value == 'False':
                return False
            else:
                return True
        elif field_type in ('CharField', 'TextField'):
            return value
        elif 'Integer' in field_type:
            return int(value)
        elif field_type in ('DateField', 'DateTimeField'):
            return decode_datetime(value)
        else:
            raise ValueError('unknown field type: %s' % field_type)

    def decode_rel_value(self, field):
        rel_type = field['rel']
        if rel_type in ('ManyToOneRel', 'OneToOneRel'):
            try:
                return int(field.text)
            except:
                return None
        elif rel_type == 'ManyToManyRel':
            items = field.find_all('object')
            return [item['pk'] for item in items]
        else:
            raise ValueError('unknown relation type %s' % rel_type)

    def decode_value(self, key):
        """
        type="DateField">
        type="DateTimeField">
        """
        if key in ('pk', 'id'):
            return int(self.soup['pk'])
        field = self.soup.find('field', attrs={'name': key})
        if field is None:
            raise ValueError('could not find field %s' % key)
        if field.get('type') != None:
            return self.decode_typed_value(field)
        elif field.get('rel') != None:
            return self.decode_rel_value(field)
        else:
            raise ValueError('unknown field class %s - neither data nor relation')


    def __getattr__(self, key):
        """Returns value of property, if decoded
        or decodes the property first from the bs4 soup"""
        if key not in self.data:
            value = self.decode_value(key)
            self.data[key] = value
        return self.data[key]


class Command(BaseImportXMLCommand):
    args = '<xml file>'
    help = 'Adds XML OSQA data produced by the "dumpdata" command'

    def handle(self, *args, **options):
        translation.activate(django_settings.LANGUAGE_CODE)

        self.setup_run()
        self.redirect_format = self.get_redirect_format(options['redirect_format'])

        dump_file_name = args[0]
        xml = open(dump_file_name, 'r').read()
        self.soup = BeautifulSoup(xml, ['lxml', 'xml'])

        #site settings
        #forum.keyvalue
        self.import_users()
        self.import_user_logins()
        #model="forum.tag"
        self.import_tags()

        #model="forum.question"/answer/comment - derivatives of the Node model
        self.import_threads()
        self.import_posts('question', True)
        #inside we also mark accepted answer, b/c it's more convenient that way
        self.import_posts('answer')
        self.import_posts('comment')
        #model="forum.noderevision"
        self.import_post_revisions()

        self.fix_answer_counts()
        self.fix_comment_counts()

        #model="forum.subscriptionsettings"
        #this model has no correspondence in Askbot

        #model="forum.actionrepute"
        #model="forum.award"

        #model="forum.nodestate"

        #model="forum.question"
        #model="forum.questionsubscription"
        #model="forum.userproperty"
        #model="forum.validationhash"
        #model="forum.vote"

        #self.import_marked_tags()

        #self.apply_groups_to_threads()

        #self.apply_question_followers()
        self.import_votes()

        self.import_badges()
        #self.import_badge_awards()

    def get_objects_for_model(self, model):
        objects_soup = self.soup.find_all(attrs={'model': model})
        for item_soup in objects_soup:
            yield DataObject(item_soup)

    def import_users(self):
        """import OSQA users to Askbot users"""
        #in OSQA user profile is split in two models
        #auth.user
        #forum.user
        for from_user in self.get_objects_for_model('auth.user'):
            try:
                to_user = User.objects.get(email=from_user.email)
            except User.DoesNotExist:
                username = self.get_safe_username(from_user.username)
                to_user = User.objects.create_user(username, from_user.email)

            self.copy_string_parameter(from_user, to_user, 'first_name')
            self.copy_string_parameter(from_user, to_user, 'last_name')
            self.copy_string_parameter(from_user, to_user, 'password')
            self.copy_bool_parameter(from_user, to_user, 'is_staff')
            self.copy_bool_parameter(from_user, to_user, 'is_active')
            self.copy_bool_parameter(from_user, to_user, 'is_superuser')
            self.copy_numeric_parameter(from_user, to_user, 'last_login', operator='max')
            self.copy_numeric_parameter(from_user, to_user, 'date_joined', operator='min')
            to_user.save()

            self.log_action(from_user, to_user)

        for profile in self.get_objects_for_model('forum.user'):
            user = self.get_imported_object_by_old_id(User, profile.id)
            self.copy_bool_parameter(profile, user, 'email_isvalid')
            user.reputation = max(user.reputation + profile.reputation - 1, 1)
            user.gold += profile.gold
            user.silver += profile.silver
            user.bronze += profile.bronze
            self.copy_string_parameter(profile, user, 'real_name')
            self.copy_numeric_parameter(profile, user, 'last_seen', operator='max')
            self.copy_string_parameter(profile, user, 'website')
            self.copy_string_parameter(profile, user, 'location')
            self.copy_numeric_parameter(profile, user, 'date_of_birth')
            self.copy_string_parameter(profile, user, 'about')
            user.save()

    def import_user_logins(self):
        """import user's login methods from OSQA to Askbot"""
        for user_login in self.get_objects_for_model('forum.authkeyuserassociation'):
            assoc = UserAssociation()
            assoc.openid_url = user_login.key
            assoc.user =  self.get_imported_object_by_old_id(User, user_login.user)
            assoc.provider_name = user_login.provider
            assoc.last_used_timestamp = user_login.added_at
            assoc.save()

    def import_tags(self):
        """imports OSQA tags to Askbot tags"""
        """
        <object model="forum.tag" pk="2">
            <field name="name" type="CharField">
            pro
            </field>
            <field name="created_by" rel="ManyToOneRel" to="forum.user">
            1
            </field>
            <field name="created_at" type="DateTimeField">
            2012-06-09 18:34:13
            </field>
            <field name="used_count" type="PositiveIntegerField">
            259
            </field>
        </object>
        """
        for osqa_tag in self.get_objects_for_model('forum.tag'):
            tag = Tag()
            tag.name = osqa_tag.name
            tag.created_by = self.get_imported_object_by_old_id(User, osqa_tag.created_by)
            tag.used_count = osqa_tag.used_count
            tag.save()

    def import_badges(self):
        """remembers relation of OSQA badges with Askbot badges"""
        #model="forum.badge"
        for osqa_badge in self.get_objects_for_model('forum.badge'):
            badge_slug = slugify_camelcase(osqa_badge.cls)
            try:
                askbot_badge = BadgeData.objects.get(slug=badge_slug)
            except BadgeData.DoesNotExist:
                print 'Could not find an equivalent to badge %s in Askbot' % osqa_badge.cls
                continue
            self.log_action(osqa_badge, askbot_badge)
        """
        <object model="forum.badge" pk="1">
            <field name="type" type="SmallIntegerField">
                3
            </field>
            <field name="cls" type="CharField">
                PopularQuestion
            </field>
            <field name="awarded_count" type="PositiveIntegerField">
                0
            </field>
        </object>
        """
        """
        slug = models.SlugField(max_length=50, unique=True)
        awarded_count = models.PositiveIntegerField(default=0)
        awarded_to = models.ManyToManyField(
                        User, through='Award', related_name='badges'
                    )
        """

    def import_badge_awards(self):
        """Makes sure that users are re-awarded all previously
        awarded OSQA badges"""
        for osqa_award in self.get_objects_for_model('forum.award'):
            user = self.get_imported_object_by_old_id(User, osqa_award.user)
            badge = self.get_imported_object_by_old_id(BadgeData, osqa_award.badge)
            if badge is None:
                continue
            print 'awarding badge %s' % badge.slug
            #if multiple or user does not have this badge, then award
            if badge.is_multiple() or (not user.has_badge(badge)):
                award = Award()
                award.badge = badge
                award.user = user
                award.notified = True
                #todo: here we need to map to the node object
                #content_type = self.get_content_type_by_old_id(award.content_type_id)
                #obj_class = content_type.model_class()
                #award.object_id = self.get_imported_object_id_by_old_id(obj_class, award.object_id)
                #award.content_type = content_type
                award.save()
            """
            <object model="forum.award" pk="1">
                <field name="user" rel="ManyToOneRel" to="forum.user">
                    1
                </field>
                <field name="badge" rel="ManyToOneRel" to="forum.badge">
                    32
                </field>
                <field name="node" rel="ManyToOneRel" to="forum.node">
                    <None/>
                </field>
                <field name="awarded_at" type="DateTimeField">
                    2012-06-08 17:49:15
                </field>
                <field name="trigger" rel="ManyToOneRel" to="forum.action">
                    4
                </field>
                <field name="action" rel="OneToOneRel" to="forum.action">
                    6
                </field>
            </object>
            """

    def import_threads(self):
        """import thread objects"""
        count = 0
        for osqa_thread in self.get_objects_for_model('forum.question'):
            count += 1
            #todo: there must be code lated to set the commented values
            lang = django_settings.LANGUAGE_CODE
            thread = Thread(
                title=osqa_thread.title,
                tagnames=osqa_thread.tagnames,
                view_count=osqa_thread.extra_count,
                #favourite_count=thread.favourite_count,
                #answer_count=thread.answer_count,
                last_activity_at=osqa_thread.last_activity_at,
                last_activity_by=self.get_imported_object_by_old_id(User, osqa_thread.last_activity_by),
                language_code=lang,
                #"closed" data is stored differently in OSQA
                #closed_by=self.get_imported_object_by_old_id(User, thread.closed_by_id),
                #closed=thread.closed,
                #closed_at=thread.closed_at,
                #close_reason=thread.close_reason,
                #deleted=False,
                approved=True, #no equivalent in OSQA
                #must be done later, after importing answers
                #answer_accepted_at=thread.answer_accepted_at,
                added_at=osqa_thread.added_at,
            )

            #apply tags to threads
            tag_names = thread.get_tag_names()
            if tag_names:

                tag_filter = Q(name__iexact=tag_names[0])
                for tag_name in tag_names[1:]:
                    tag_filter |= Q(name__iexact=tag_name)
                tags = Tag.objects.filter(tag_filter & Q(language_code=lang))

                thread.tagnames = ' '.join([tag.name for tag in tags])

                thread.save()
                for tag in tags:
                    thread.tags.add(tag)
                    tag.used_count += 1
                    tag.save()

            else:
                thread.save()

            self.log_action(osqa_thread, thread)

    def import_posts(self, post_type, save_redirects=False):
        """imports osqa Nodes to askbot Post objects"""
        if save_redirects:
            redirects_file = self.open_unique_file('question_redirects')

        models_map = {
            'question': 'forum.question',
            'answer': 'forum.answer',
            'comment': 'forum.comment'
        }

        model_name = models_map[post_type]

        for osqa_node in self.get_objects_for_model(model_name):
            #we iterate through all nodes, but pick only the ones we need
            if osqa_node.node_type != post_type:
                continue

            #cheat: do not import deleted content
            if '(deleted)' in osqa_node.state_string:
                continue

            post = Post()

            #this line is a bit risky, but should work if we import things in correct order
            if osqa_node.parent:
                post.parent = self.get_imported_object_by_old_id(Post, osqa_node.parent)
                if post.parent is None:
                    continue #deleted parent
                post.thread = post.parent.thread
            else:
                post.thread = self.get_imported_object_by_old_id(Thread, osqa_node.id)
                if post.thread is None:
                    continue #deleted thread

            post.post_type = osqa_node.node_type
            post.added_at = osqa_node.added_at

            if save_redirects:
                slug = django_urlquote(slugify(osqa_node.title))
                #todo: add i18n to the old url
                old_url = '/questions/%d/%s/' % (osqa_node.id, slug)

            post.author = self.get_imported_object_by_old_id(User, osqa_node.author)
            #html will de added with the revisions
            #post.html = HTMLParser().unescape(osqa_node.body)
            post.summary = post.get_snippet()

            #these don't have direct equivalent in the OSQA Node object
            #post.deleted_by - deleted nodes are not imported
            #post.locked_by
            #post.last_edited_by

            #these are to be set later with the real values
            post.points = 0
            post.vote_up_count = 0
            post.vote_down_count = 0
            post.offensive_flag_count = 0

            post.save()

            #mark accepted answer
            now = datetime.now()
            if osqa_node.node_type == 'answer':
                if '(accepted)' in osqa_node.state_string:
                    post.thread.accepted_answer = post
                    post.endorsed = True
                    post.endorsed_at = now
                    post.thread.save()


            if save_redirects:
                new_url = post.get_absolute_url()
                self.write_redirect(old_url, new_url, redirects_file)

            self.log_action_with_old_id(osqa_node.id, post)

        if save_redirects:
            redirects_file.close()

    def import_post_revisions(self):
        """Imports OSQA revisions to Askbot revisions"""
        for osqa_revision in self.get_objects_for_model('forum.noderevision'):
            post = self.get_imported_object_by_old_id(Post, osqa_revision.node)
            if post is None:
                continue #deleted post
            user = self.get_imported_object_by_old_id(User, osqa_revision.author)
            revision = PostRevision(
                            post=post,
                            author=user,
                            text=osqa_revision.body,
                            title=osqa_revision.title,
                            tagnames=osqa_revision.tagnames,
                            revised_at=osqa_revision.revised_at,
                            summary=osqa_revision.summary,
                            revision=osqa_revision.revision
                        )
            post.text = osqa_revision.body
            if osqa_revision == 1:
                post.added_at = osqa_revision.revised_at
            else:
                post.last_edited_at = osqa_revision.revised_at
                post.last_edited_by = user

            post.parse_and_save(author=user)
            revision.save()

    def import_votes(self):
        """Imports OSQA votes to Askbot votes"""
        for osqa_vote in self.get_objects_for_model('forum.vote'):
            post = self.get_imported_object_by_old_id(Post, osqa_vote.node)
            if post is None:
                continue #deleted post
            user = self.get_imported_object_by_old_id(User, osqa_vote.user)
            if osqa_vote.value > 0:
                user.upvote(post, timestamp=osqa_vote.voted_at, force=True)
            elif osqa_vote.value < 0:
                user.downvote(post, timestamp=osqa_vote.voted_at, force=True)

    def fix_answer_counts(self):
        for thread in Thread.objects.all():
            thread.answer_count = thread.get_answers().count()
            thread.save()

    def fix_comment_counts(self):
        for post in Post.objects.filter(post_type__in=('question', 'answer')):
            post.comment_count = Post.objects.filter(post_type='comment', parent=post).count()
            post.save()
