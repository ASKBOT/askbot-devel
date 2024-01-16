import datetime
import logging
import re
from django.db import models
from django.db.models import Q
from django.db.utils import IntegrityError
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import fields
from django.contrib.auth.models import User
from django.contrib.auth.models import Group as AuthGroup
from django.core import exceptions
from django.forms import EmailField, URLField
from django.utils import translation, timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.utils.html import strip_tags
from askbot import const
from askbot.conf import settings as askbot_settings
from askbot.utils import functions
from askbot.models.base import BaseQuerySetManager
from askbot.models.analytics import Session
from collections import defaultdict

PERSONAL_GROUP_NAME_PREFIX = '_personal_'

class InvitedModerator(object):
    """Mock user class to represent invited moderators"""
    def __init__(self, username, email):
        self.username = username
        self.email = email
        self.reputation = 1
        self.invited_outside_moderator = True

    def is_anonymous(self):
        return False

    def is_authenticated(self):
        return True

    @classmethod
    def make_from_setting(cls, setting_line):
        """Takes one line formatted as <email> <name>
        and if first value is a valid email,
        returns an instance of InvitedModerator,
        otherwise returns `None`"""
        bits = setting_line.strip().split()
        if len(bits) < 2:
            return None

        email = bits[0]
        if not functions.is_email_valid(email):
            return None
        name = ' '.join(bits[1:])

        return cls(name, email)

def get_invited_moderators(include_registered=False):
    """Returns list of InvitedModerator instances
    corresponding to values of askbot_settings.INVITED_MODERATORS"""
    values = askbot_settings.INVITED_MODERATORS.strip()
    moderators = set()
    for user_line in values.split('\n'):
        mod = InvitedModerator.make_from_setting(user_line)
        if mod:
            moderators.add(mod)

    # exclude existing users
    clean_emails = set([mod.email for mod in moderators])

    if include_registered == True:
        return set(moderators)

    existing_users = User.objects.filter(email__in=clean_emails)
    existing_emails = set(existing_users.values_list('email', flat=True))
    outside_emails = clean_emails - existing_emails

    def is_outside_mod(mod):
        return mod.email in outside_emails

    return set(filter(is_outside_mod, moderators))


def remove_email_from_invited_moderators(email):
    """Update the `INVITED_MODERATORS` setting by removing
    the matching email entry"""
    lines = askbot_settings.INVITED_MODERATORS.strip().split('\n')
    clean_lines = list()
    prefix = email + ' '
    for line in lines:
        if not line.startswith(prefix):
            clean_lines.append(line)
    if len(clean_lines) != len(lines):
        value = '\n'.join(clean_lines)
        askbot_settings.update('INVITED_MODERATORS', value)


class MockUser(object):
    def __init__(self):
        self.username = ''

    def get_avatar_url(self, size):
        return ''

    def get_full_name(self):
        return ''

    def get_profile_url(self):
        return ''

    def get_absolute_url(self):
        return ''

    def is_anonymous(self):
        return True

    def is_authenticated(self):
        return False

    def is_administrator_or_moderator(self):
        return False

    def is_blocked(self):
        return False

    def is_approved(self):
        return False

    def is_suspended(self):
        return False

    def is_watched(self):
        return False


class ActivityQuerySet(models.query.QuerySet):
    """query set for the `Activity` model"""
    def get_all_origin_posts(self):
        #todo: redo this with query sets
        origin_posts = set()
        for m in self.all():
            post = m.content_object
            if post and hasattr(post, 'get_origin_post'):
                origin_posts.add(post.get_origin_post())
            else:
                logging.debug(
                            'method get_origin_post() not implemented for %s' \
                            % str(post)
                        )
        return list(origin_posts)

    def fetch_content_objects_dict(self):
        """return a dictionary where keys are activity ids
        and values - content objects"""
        content_object_ids = defaultdict(list)# lists of c.object ids by c.types
        activity_type_ids = dict()#links c.objects back to activity objects
        for act in self:
            content_type_id = act.content_type_id
            object_id = act.object_id
            content_object_ids[content_type_id].append(object_id)
            activity_type_ids[(content_type_id, object_id)] = act.id

        #3) get links from activity objects to content objects
        objects_by_activity = dict()
        for content_type_id, object_id_list in list(content_object_ids.items()):
            content_type = ContentType.objects.get_for_id(content_type_id)
            model_class = content_type.model_class()
            content_objects = model_class.objects.filter(id__in=object_id_list)
            for content_object in content_objects:
                key = (content_type_id, content_object.id)
                activity_id = activity_type_ids[key]
                objects_by_activity[activity_id] = content_object

        return objects_by_activity


class ActivityManager(BaseQuerySetManager):
    """manager class for the `Activity` model"""
    def get_queryset(self):
        return ActivityQuerySet(self.model)

    def create_new_mention(
                self,
                mentioned_by = None,
                mentioned_whom = None,
                mentioned_at = None,
                mentioned_in = None,
                reported = None
            ):

        #todo: automate this using python inspect module
        kwargs = dict()

        kwargs['activity_type'] = const.TYPE_ACTIVITY_MENTION

        if mentioned_at:
            #todo: handle cases with rich lookups here like __lt
            kwargs['active_at'] = mentioned_at

        if mentioned_by:
            kwargs['user'] = mentioned_by

        if mentioned_in:
            if functions.is_iterable(mentioned_in):
                raise NotImplementedError('mentioned_in only works for single items')
            else:
                post_content_type = ContentType.objects.get_for_model(mentioned_in)
                kwargs['content_type'] = post_content_type
                kwargs['object_id'] = mentioned_in.id

        if reported == True:
            kwargs['is_auditted'] = True
        else:
            kwargs['is_auditted'] = False

        mention_activity = Activity(**kwargs)
        mention_activity.question = mentioned_in.get_origin_post()
        mention_activity.save()

        if mentioned_whom:
            assert(isinstance(mentioned_whom, User))
            mention_activity.add_recipients([mentioned_whom])
            mentioned_whom.update_response_counts()

        return mention_activity

    def get_mentions(
                self,
                mentioned_by = None,
                mentioned_whom = None,
                mentioned_at = None,
                mentioned_in = None,
                reported = None,
                mentioned_at__lt = None,
            ):
        """extract mention-type activity objects
        todo: implement better rich field lookups
        """

        kwargs = dict()

        kwargs['activity_type'] = const.TYPE_ACTIVITY_MENTION

        if mentioned_at:
            #todo: handle cases with rich lookups here like __lt, __gt and others
            kwargs['active_at'] = mentioned_at
        elif mentioned_at__lt:
            kwargs['active_at__lt'] = mentioned_at__lt

        if mentioned_by:
            kwargs['user'] = mentioned_by

        if mentioned_whom:
            if functions.is_iterable(mentioned_whom):
                kwargs['recipients__in'] = mentioned_whom
            else:
                kwargs['recipients__in'] = (mentioned_whom,)

        if mentioned_in:
            if functions.is_iterable(mentioned_in):
                it = iter(mentioned_in)
                raise NotImplementedError('mentioned_in only works for single items')
            else:
                post_content_type = ContentType.objects.get_for_model(mentioned_in)
                kwargs['content_type'] = post_content_type
                kwargs['object_id'] = mentioned_in.id

        if reported == True:
            kwargs['is_auditted'] = True
        else:
            kwargs['is_auditted'] = False

        return self.filter(**kwargs)


class ActivityAuditStatus(models.Model):
    """bridge "through" relation between activity and users"""
    STATUS_NEW = 0
    STATUS_SEEN = 1
    STATUS_CHOICES = (
        (STATUS_NEW, 'new'),
        (STATUS_SEEN, 'seen')
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    activity = models.ForeignKey('Activity', on_delete=models.CASCADE)
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=STATUS_NEW)

    class Meta:
        unique_together = ('user', 'activity')
        app_label = 'askbot'
        db_table = 'askbot_activityauditstatus'

    def is_new(self):
        return (self.status == self.STATUS_NEW)


class Activity(models.Model):
    """
    We keep some history data for user activities
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True)
    recipients = models.ManyToManyField(User, through=ActivityAuditStatus, related_name='incoming_activity')
    activity_type = models.SmallIntegerField(choices=const.TYPE_ACTIVITY, db_index=True)
    active_at = models.DateTimeField(default=timezone.now)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = fields.GenericForeignKey('content_type', 'object_id')

    #todo: remove this denorm question field when Post model is set up
    question = models.ForeignKey('Post', null=True, on_delete=models.CASCADE)

    is_auditted = models.BooleanField(default=False) # todo: this field seems to be unused
    #add summary field.
    summary = models.TextField(default='')

    objects = ActivityManager()

    def __str__(self):
        activity_type = self.get_activity_type_display()
        return f'Activity: {self.user.username}@{self.active_at.isoformat()}: {activity_type}'

    class Meta:
        app_label = 'askbot'
        db_table = 'activity'
        verbose_name = _("activity")
        verbose_name_plural = _("activities")

    def add_recipients(self, recipients):
        """have to use a special method, because django does not allow
        auto-adding to M2M with "through" model
        """
        pre_existing = ActivityAuditStatus.objects.filter(user__in=recipients, activity=self)
        pre_existing = pre_existing.only('user__id')
        skip_user_ids = [user.id for user in pre_existing]

        for recipient in recipients:
            if recipient.id not in skip_user_ids:
                #todo: may optimize for bulk addition
                aas = ActivityAuditStatus(user=recipient, activity=self)
                aas.save()

    def get_mentioned_user(self):
        assert(self.activity_type == const.TYPE_ACTIVITY_MENTION)
        user_qs = self.recipients.all()
        user_count = len(user_qs)
        if user_count == 0:
            return None
        assert(user_count == 1)
        return user_qs[0]

    def get_snippet(self, max_length = 120):
        return self.content_object.get_snippet(max_length)

    def get_absolute_url(self):
        return self.content_object.get_absolute_url()

class EmailFeedSettingManager(models.Manager):
    def filter_subscribers(self, potential_subscribers=None,
                           feed_type=None, frequency=None):
        """returns set of users who have matching subscriptions
        and if potential_subscribers is not none, search will
        be limited to only potential subscribers,

        otherwise search is unrestricted

        todo: when EmailFeedSetting is merged into user table
        this method may become unnecessary
        """
        matching_feeds = self.filter(feed_type=feed_type, frequency=frequency)
        if potential_subscribers is not None:
            matching_feeds = matching_feeds.filter(
                            subscriber__in = potential_subscribers
                        )
        subscriber_set = set()
        for feed in matching_feeds:
            subscriber_set.add(feed.subscriber)

        return subscriber_set


class EmailFeedSetting(models.Model):
    # Definitions of delays before notification for each type of notification frequency
    DELTA_TABLE = {
        'i': datetime.timedelta(-1),  # Instant emails are processed separately
        'd': datetime.timedelta(1),
        'w': datetime.timedelta(7),
        'n': datetime.timedelta(-1),
    }
    # definitions of feed schedule types
    FEED_TYPES = (
            'q_ask',  # questions that user asks
            'q_all',  # enture forum, tag filtered
            'q_ans',  # questions that user answers
            'q_noans', # questions without answers
            'q_sel',  # questions that user decides to follow
            'm_and_c'  # comments and mentions of user anywhere
    )
    # email delivery schedule when no email is sent at all
    NO_EMAIL_SCHEDULE = {
        'q_ask': 'n',
        'q_ans': 'n',
        'q_noans': 'n',
        'q_all': 'n',
        'q_sel': 'n',
        'm_and_c': 'n'
    }
    MAX_EMAIL_SCHEDULE = {
        'q_ask': 'i',
        'q_ans': 'i',
        'q_noans': 'd',
        'q_all': 'i',
        'q_sel': 'i',
        'm_and_c': 'i'
    }
    # TODO: words
    FEED_TYPE_CHOICES = (
        ('q_all', gettext_lazy('Entire forum')),
        ('q_ask', gettext_lazy('Questions that I asked')),
        ('q_ans', gettext_lazy('Questions that I answered')),
        ('q_noans', gettext_lazy('Unanswered questions')),
        ('q_sel', gettext_lazy('Individually selected questions')),
        ('m_and_c', gettext_lazy('Mentions and comment responses')),
    )
    UPDATE_FREQUENCY = (
        ('i', gettext_lazy('Instantly')),
        ('d', gettext_lazy('Daily')),
        ('w', gettext_lazy('Weekly')),
        ('n', gettext_lazy('No email')),
    )

    subscriber = models.ForeignKey(User, related_name='notification_subscriptions', on_delete=models.CASCADE)
    feed_type = models.CharField(max_length=16, choices=FEED_TYPE_CHOICES)
    frequency = models.CharField(
                    max_length=8,
                    choices=const.NOTIFICATION_DELIVERY_SCHEDULE_CHOICES,
                    default='n'
                )
    added_at = models.DateTimeField(auto_now_add=True)
    reported_at = models.DateTimeField(null=True)

    objects = EmailFeedSettingManager()

    class Meta:
        # Added to make account merges work properly
        unique_together = ('subscriber', 'feed_type')
        app_label = 'askbot'

    def __str__(self):
        if self.reported_at is None:
            reported_at = "'not yet'"
        else:
            reported_at = '%s' % self.reported_at.strftime('%d/%m/%y %H:%M')
        return 'Email feed for %s type=%s, frequency=%s, reported_at=%s' % (
                                                     self.subscriber,
                                                     self.feed_type,
                                                     self.frequency,
                                                     reported_at
                                                 )

    def save(self, *args, **kwargs):
        type = self.feed_type
        subscriber = self.subscriber
        similar = self.__class__.objects\
            .filter(feed_type=type, subscriber=subscriber)\
            .exclude(pk=self.id)
        if similar.exists():
            raise IntegrityError('email feed setting already exists')
        super(EmailFeedSetting, self).save(*args, **kwargs)

    def get_previous_report_cutoff_time(self):
        now = timezone.now()
        return now - self.DELTA_TABLE[self.frequency]

    def should_send_now(self):
        now = timezone.now()
        cutoff_time = self.get_previous_report_cutoff_time()
        return (
            self.reported_at is None or
            self.reported_at <= cutoff_time
        )

    def mark_reported_now(self):
        self.reported_at = timezone.now()
        self.save()


class GroupMembership(models.Model):
    NONE = -1  # not part of the choices as for this records should be just missing
    PENDING = 0
    FULL = 1
    LEVEL_CHOICES = (  # 'none' is by absence of membership
        (PENDING, 'pending'),
        (FULL, 'full')
    )
    ALL_LEVEL_CHOICES = LEVEL_CHOICES + ((NONE, 'none'),)

    group = models.ForeignKey(AuthGroup, related_name='user_membership', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='group_membership', on_delete=models.CASCADE)
    level = models.SmallIntegerField(
        default=FULL, choices=LEVEL_CHOICES,)

    class Meta:
        app_label = 'askbot'
        unique_together = ('group', 'user')

    @classmethod
    def get_level_value_display(cls, level):
        """returns verbose value given a numerical value
        includes the "fanthom" NONE
        """
        values_dict = dict(cls.ALL_LEVEL_CHOICES)
        return values_dict[level]


class GroupQuerySet(models.query.QuerySet):
    """Custom query set for the group"""

    def exclude_personal(self):
        """excludes the personal groups"""
        return self.exclude(
            name__startswith=PERSONAL_GROUP_NAME_PREFIX
        )

    def get_personal(self):
        """filters for the personal groups"""
        return self.filter(
            name__startswith=PERSONAL_GROUP_NAME_PREFIX
        )

    def get_for_user(self, user=None, private=False):
        gms = GroupMembership.objects.filter(user=user)
        if private:
            global_group = Group.objects.get_global_group()
            gms = gms.exclude(group=global_group)
        group_ids = gms.values_list('group_id', flat=True)
        return Group.objects.filter(pk__in=group_ids)

    def get_by_name(self, group_name = None):
        from askbot.models.tag import clean_group_name#todo - delete this
        return self.get(name = clean_group_name(group_name))


class GroupManager(BaseQuerySetManager):
    """model manager for askbot groups"""

    def get_queryset(self):
        return GroupQuerySet(self.model)

    def get_global_group(self):
        """Returns the global group,
        if necessary, creates one
        """
        #todo: when groups are disconnected from tags,
        #find comment as shown below in the test cases and
        #revert the values
        #todo: change groups to django groups
        group_name = askbot_settings.GLOBAL_GROUP_NAME
        try:
            return self.get_queryset().get(name=group_name)
        except Group.DoesNotExist:
            return self.get_queryset().create(name=group_name)

    def create(self, **kwargs):
        name = kwargs['name']
        try:
            group_ptr = AuthGroup.objects.get(name=name)
            kwargs['group_ptr'] = group_ptr
        except AuthGroup.DoesNotExist:
            pass
        return super(GroupManager, self).create(**kwargs)

    def get_or_create(self, name=None, user=None, openness=None):
        """creates a group tag or finds one, if exists"""
        #todo: here we might fill out the group profile
        try:
            #iexact is important!!! b/c we don't want case variants
            #of tags
            group = self.get(name__iexact = name)
        except self.model.DoesNotExist:
            if openness is None:
                group = self.create(name=name)
            else:
                group = self.create(name=name, openness=openness)
        return group


class Group(AuthGroup):
    """group profile for askbot"""
    OPEN = 0
    MODERATED = 1
    CLOSED = 2
    OPENNESS_CHOICES = (
        (OPEN, 'open'),
        (MODERATED, 'moderated'),
        (CLOSED, 'closed'),
    )
    logo_url = models.URLField(null=True)
    description = models.OneToOneField(
                    'Post', related_name='described_group',
                    null=True, blank=True, on_delete=models.CASCADE
                )
    moderate_email = models.BooleanField(default=True)
    can_post_questions = models.BooleanField(default=False)
    can_post_answers = models.BooleanField(default=False)
    can_post_comments = models.BooleanField(default=False)
    can_upload_attachments = models.BooleanField(default=False)
    can_upload_images = models.BooleanField(default=False)

    openness = models.SmallIntegerField(default=CLOSED, choices=OPENNESS_CHOICES)
    # preapproved email addresses and domain names to auto-join groups
    # trick - the field is padded with space and all tokens are space separated
    preapproved_emails = models.TextField(
        null=True, blank=True, default='')
    # only domains - without the '@' or anything before them
    preapproved_email_domains = models.TextField(
        null=True, blank=True, default='')

    read_only = models.BooleanField(default=False)

    objects = GroupManager()

    class Meta:
        app_label = 'askbot'
        db_table = 'askbot_group'

    def get_moderators(self):
        """returns group moderators"""
        user_filter = models.Q(askbot_profile__status__in=('m', 'd'))
        user_filter = user_filter & models.Q(group_membership__group__in=[self])
        return User.objects.filter(user_filter)

    def has_moderator(self, user):
        """true, if user is a group moderator"""
        mod_ids = self.get_moderators().values_list('id', flat=True)
        return user.id in mod_ids

    def get_openness_choices(self):
        """gives answers to question
        "How can users join this group?"
        """
        return (
            (Group.OPEN, _('Can join when they want')),
            (Group.MODERATED, _('Users ask permission')),
            (Group.CLOSED, _('Moderator adds users'))
        )

    def get_openness_level_for_user(self, user):
        """returns descriptive value, because it is to be used in the
        templates. The value must match the verbose versions of the
        openness choices!!!
        """
        if user.is_anonymous:
            return 'closed'

        # A special case - automatic global group cannot be joined or left
        if self.name == askbot_settings.GLOBAL_GROUP_NAME:
            return 'closed'

        # TODO: return 'closed' for internal per user groups too

        if self.openness == Group.OPEN:
            return 'open'

        if user.is_administrator_or_moderator():
            return 'open'

        # Relying on a specific method of storage
        from askbot.utils.forms import email_is_allowed
        if email_is_allowed(
            user.email,
            allowed_emails=self.preapproved_emails,
            allowed_email_domains=self.preapproved_email_domains
        ):
            return 'open'

        if self.openness == Group.MODERATED:
            return 'moderated'

        return 'closed'

    def is_personal(self):
        """``True`` if the group is personal"""
        return self.name.startswith(PERSONAL_GROUP_NAME_PREFIX)

    def clean(self):
        """called in `save()`
        """
        emails = functions.split_list(self.preapproved_emails)
        email_field = EmailField()
        try:
            list(map(lambda v: email_field.clean(v), emails))
        except exceptions.ValidationError:
            raise exceptions.ValidationError(
                _('Please give a list of valid email addresses.')
            )
        self.preapproved_emails = ' ' + '\n'.join(emails) + ' '

        domains = functions.split_list(self.preapproved_email_domains)
        from askbot.forms import DomainNameField
        domain_field = DomainNameField()
        try:
            list(map(lambda v: domain_field.clean(v), domains))
        except exceptions.ValidationError:
            raise exceptions.ValidationError(
                _('Please give a list of valid email domain names.')
            )
        self.preapproved_email_domains = ' ' + '\n'.join(domains) + ' '

    def save(self, *args, **kwargs):
        self.clean()
        super(Group, self).save(*args, **kwargs)


class BulkTagSubscriptionManager(BaseQuerySetManager):

    def create(
                self,
                tag_names=None,
                user_list=None,
                group_list=None,
                tag_author=None,
                language_code=None,
                **kwargs
            ):

        tag_names = tag_names or []
        user_list = user_list or []
        group_list = group_list or []

        new_object = super(BulkTagSubscriptionManager, self).create(**kwargs)
        tag_name_list = []

        if tag_names:
            from askbot.models.tag import get_tags_by_names
            tags, new_tag_names = get_tags_by_names(tag_names, language_code)
            if new_tag_names:
                assert(tag_author)

            tags_id_list= [tag.id for tag in tags]
            tag_name_list = [tag.name for tag in tags]

            from askbot.models.tag import Tag
            new_tags = Tag.objects.create_in_bulk(
                                tag_names=new_tag_names,
                                user=tag_author,
                                language_code=translation.get_language()
                            )

            tags_id_list.extend([tag.id for tag in new_tags])
            tag_name_list.extend([tag.name for tag in new_tags])

            new_object.tags.add(*tags_id_list)

        if user_list:
            user_ids = []
            for user in user_list:
                user_ids.append(user.id)
                user.mark_tags(tagnames=tag_name_list,
                               reason='subscribed',
                               action='add')

            new_object.users.add(*user_ids)

        if group_list:
            group_ids = []
            for group in group_list:
                # TODO: do the group marked tag thing here
                group_ids.append(group.id)
            new_object.groups.add(*group_ids)

        return new_object


class BulkTagSubscription(models.Model):
    date_added = models.DateField(auto_now_add=True)
    tags = models.ManyToManyField('Tag')
    users = models.ManyToManyField(User)
    groups = models.ManyToManyField(Group)

    objects = BulkTagSubscriptionManager()

    def tag_list(self):
        return [tag.name for tag in self.tags.all()]

    class Meta:
        app_label = 'askbot'
        ordering = ['-date_added']

