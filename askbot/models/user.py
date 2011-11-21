import datetime
import logging
from django.db import models
from django.db.backends.dummy.base import IntegrityError
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _
from django.utils.html import strip_tags
from askbot import const
from askbot.utils import functions

class ResponseAndMentionActivityManager(models.Manager):
    def get_query_set(self):
        response_types = const.RESPONSE_ACTIVITY_TYPES_FOR_DISPLAY
        response_types += (const.TYPE_ACTIVITY_MENTION, )
        return super(
                    ResponseAndMentionActivityManager,
                    self
                ).get_query_set().filter(
                    activity_type__in = response_types
                )

class ActivityManager(models.Manager):
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
                            % unicode(post)
                        )
        return list(origin_posts)

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
    user = models.ForeignKey(User)
    activity = models.ForeignKey('Activity')
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
    user = models.ForeignKey(User)
    receiving_users = models.ManyToManyField(User, related_name='received_activity')
    recipients = models.ManyToManyField(User, through=ActivityAuditStatus, related_name='incoming_activity')
    activity_type = models.SmallIntegerField(choices = const.TYPE_ACTIVITY)
    active_at = models.DateTimeField(default=datetime.datetime.now)
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')
    #todo: remove this denorm question field when Post model is set up
    question = models.ForeignKey('Question', null=True)
    is_auditted = models.BooleanField(default=False)
    #add summary field.
    summary = models.TextField(default='')

    objects = ActivityManager()
    responses_and_mentions = ResponseAndMentionActivityManager()

    def __unicode__(self):
        return u'[%s] was active at %s' % (self.user.username, self.active_at)

    class Meta:
        app_label = 'askbot'
        db_table = u'activity'

    def add_recipients(self, recipients):
        """have to use a special method, because django does not allow
        auto-adding to M2M with "through" model
        """
        for recipient in recipients:
            #todo: may optimize for bulk addition
            aas = ActivityAuditStatus(user = recipient, activity = self)
            aas.save()

    def get_mentioned_user(self):
        assert(self.activity_type == const.TYPE_ACTIVITY_MENTION)
        user_qs = self.recipients.all()
        user_count = len(user_qs)
        if user_count == 0:
            return None
        assert(user_count == 1)
        return user_qs[0]

    def get_preview(self):
        if  self.summary == '':
            return strip_tags(self.content_object.html)[:300]
        else:
            return self.summary

    def get_absolute_url(self):
        return self.content_object.get_absolute_url()

class EmailFeedSettingManager(models.Manager):
    def filter_subscribers(
                        self,
                        potential_subscribers = None,
                        feed_type = None,
                        frequency = None
                    ):
        """returns set of users who have matching subscriptions
        and if potential_subscribers is not none, search will
        be limited to only potential subscribers,

        otherwise search is unrestricted

        todo: when EmailFeedSetting is merged into user table
        this method may become unnecessary
        """
        matching_feeds = self.filter(
                                        feed_type = feed_type,
                                        frequency = frequency
                                    )
        if potential_subscribers is not None:
            matching_feeds = matching_feeds.filter(
                            subscriber__in = potential_subscribers
                        )
        subscriber_set = set()
        for feed in matching_feeds:
            subscriber_set.add(feed.subscriber)

        return subscriber_set

class EmailFeedSetting(models.Model):
    #definitions of delays before notification for each type of notification frequency
    DELTA_TABLE = {
        'i':datetime.timedelta(-1),#instant emails are processed separately
        'd':datetime.timedelta(1),
        'w':datetime.timedelta(7),
        'n':datetime.timedelta(-1),
    }
    #definitions of feed schedule types
    FEED_TYPES = (
            'q_ask', #questions that user asks
            'q_all', #enture forum, tag filtered
            'q_ans', #questions that user answers
            'q_sel', #questions that user decides to follow
            'm_and_c' #comments and mentions of user anywhere
    )
    #email delivery schedule when no email is sent at all
    NO_EMAIL_SCHEDULE = {
        'q_ask': 'n',
        'q_ans': 'n',
        'q_all': 'n',
        'q_sel': 'n',
        'm_and_c': 'n'
    }
    FEED_TYPE_CHOICES = (
                    ('q_all',_('Entire forum')),
                    ('q_ask',_('Questions that I asked')),
                    ('q_ans',_('Questions that I answered')),
                    ('q_sel',_('Individually selected questions')),
                    ('m_and_c',_('Mentions and comment responses')),
                    )
    UPDATE_FREQUENCY = (
                    ('i',_('Instantly')),
                    ('d',_('Daily')),
                    ('w',_('Weekly')),
                    ('n',_('No email')),
                   )


    subscriber = models.ForeignKey(User, related_name='notification_subscriptions')
    feed_type = models.CharField(max_length=16, choices=FEED_TYPE_CHOICES)
    frequency = models.CharField(
                                    max_length=8,
                                    choices=const.NOTIFICATION_DELIVERY_SCHEDULE_CHOICES,
                                    default='n',
                                )
    added_at = models.DateTimeField(auto_now_add=True)
    reported_at = models.DateTimeField(null=True)
    objects = EmailFeedSettingManager()

    class Meta:
        #added to make account merges work properly
        unique_together = ('subscriber', 'feed_type')

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

    def save(self,*args,**kwargs):
        type = self.feed_type
        subscriber = self.subscriber
        similar = self.__class__.objects.filter(
                                            feed_type=type,
                                            subscriber=subscriber
                                        ).exclude(pk=self.id)
        if len(similar) > 0:
            raise IntegrityError('email feed setting already exists')
        super(EmailFeedSetting,self).save(*args,**kwargs)

    def get_previous_report_cutoff_time(self):
        now = datetime.datetime.now()
        return now - self.DELTA_TABLE[self.frequency]

    def should_send_now(self):
        now = datetime.datetime.now()
        cutoff_time = self.get_previous_report_cutoff_time()
        if self.reported_at == None or self.reported_at <= cutoff_time:
            return True
        else:
            return False

    def mark_reported_now(self):
        self.reported_at = datetime.datetime.now()
        self.save()

    class Meta:
        app_label = 'askbot'
