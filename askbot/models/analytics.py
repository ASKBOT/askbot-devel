"""Models for the Analytics feature"""
import datetime
from django.db import models
from django.db.models import Q
from django.db.models import Value
from django.db.models.functions import Substr, StrIndex
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.conf import settings as django_settings
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from askbot.models.user import Group as AskbotGroup
from askbot.models.repute import Vote
from askbot import signals

#for convenience, here are the activity types from used in the Activity object
#TYPE_ACTIVITY_ASK_QUESTION = 1
#TYPE_ACTIVITY_ANSWER = 2
#TYPE_ACTIVITY_COMMENT_QUESTION = 3
#TYPE_ACTIVITY_COMMENT_ANSWER = 4
#TYPE_ACTIVITY_UPDATE_QUESTION = 5
#TYPE_ACTIVITY_UPDATE_ANSWER = 6
#TYPE_ACTIVITY_PRIZE = 7
#TYPE_ACTIVITY_MARK_ANSWER = 8
#TYPE_ACTIVITY_VOTE_UP = 9
#TYPE_ACTIVITY_VOTE_DOWN = 10
#TYPE_ACTIVITY_CANCEL_VOTE = 11
#TYPE_ACTIVITY_DELETE_QUESTION = 12
#TYPE_ACTIVITY_DELETE_ANSWER = 13
#TYPE_ACTIVITY_MARK_OFFENSIVE = 14
#TYPE_ACTIVITY_UPDATE_TAGS = 15
#TYPE_ACTIVITY_FAVORITE = 16
#TYPE_ACTIVITY_USER_FULL_UPDATED = 17
#TYPE_ACTIVITY_EMAIL_UPDATE_SENT = 18
#TYPE_ACTIVITY_MENTION = 19
#TYPE_ACTIVITY_UNANSWERED_REMINDER_SENT = 20
#TYPE_ACTIVITY_ACCEPT_ANSWER_REMINDER_SENT = 21
#TYPE_ACTIVITY_CREATE_TAG_WIKI = 22
#TYPE_ACTIVITY_UPDATE_TAG_WIKI = 23
#TYPE_ACTIVITY_MODERATED_NEW_POST = 24
#TYPE_ACTIVITY_MODERATED_POST_EDIT = 25
#TYPE_ACTIVITY_CREATE_REJECT_REASON = 26
#TYPE_ACTIVITY_UPDATE_REJECT_REASON = 27
#TYPE_ACTIVITY_VALIDATION_EMAIL_SENT = 28
#TYPE_ACTIVITY_POST_SHARED = 29
#TYPE_ACTIVITY_ASK_TO_JOIN_GROUP = 30
#TYPE_ACTIVITY_MODERATION_ALERT_SENT = 31
#TYPE_ACTIVITY_FORBIDDEN_PHRASE_FOUND = 50 #added gap
#TYPE_ACTIVITY_USER_REGISTERED = 51
#TYPE_ACTIVITY_QUESTION_VIEWED = 52
#TYPE_ACTIVITY_ANSWER_VIEWED = 53

EVENT_TYPE_USER_REGISTERED = 1
EVENT_TYPE_LOGGED_IN = 2
EVENT_TYPE_LOGGED_OUT = 3
EVENT_TYPE_QUESTION_VIEWED = 4
EVENT_TYPE_ANSWER_VIEWED = 5
EVENT_TYPE_UPVOTED = 6
EVENT_TYPE_DOWNVOTED = 7
EVENT_TYPE_VOTE_CANCELED = 8
EVENT_TYPE_ASKED = 9
EVENT_TYPE_ANSWERED = 10
EVENT_TYPE_QUESTION_COMMENTED = 11
EVENT_TYPE_ANSWER_COMMENTED = 12
EVENT_TYPE_QUESTION_RETAGGED = 13
EVENT_TYPE_SEARCHED = 14

EVENT_TYPES = (
    (EVENT_TYPE_USER_REGISTERED, _('registered')), # Activity.activity_type == 51
    (EVENT_TYPE_LOGGED_IN, _('logged in')),
    (EVENT_TYPE_LOGGED_OUT, _('logged out')),
    (EVENT_TYPE_QUESTION_VIEWED, _('question viewed')), # Activity.activity_type == 52
    (EVENT_TYPE_ANSWER_VIEWED, _('answer viewed')), # Activity.activity_type == 53
    (EVENT_TYPE_UPVOTED, _('upvoted')), # Activity.activity_type == 9
    (EVENT_TYPE_DOWNVOTED, _('downvoted')), # Activity.activity_type == 10
    (EVENT_TYPE_VOTE_CANCELED, _('canceled vote')), # Activity.activity_type == 11
    (EVENT_TYPE_ASKED, _('asked')), # Activity.activity_type == 1
    (EVENT_TYPE_ANSWERED, _('answered')), # Activity.activity_type == 2
    (EVENT_TYPE_QUESTION_COMMENTED, _('commented question')), # Activity.activity_type == 3
    (EVENT_TYPE_ANSWER_COMMENTED, _('commented answer')), # Activity.activity_type == 4
    (EVENT_TYPE_QUESTION_RETAGGED, _('retagged question')), # Activity.activity_type == 15
    (EVENT_TYPE_SEARCHED, _('searched')),
)

# Dimension and Metric would make a generic implementation of the analytics feature
# however it is more complex.
#class Dimension(models.Model):
#    name = models.CharField(max_length=64, help_text="Name of the dimension")
#    description = models.TextField(blank=True, null=True, help_text="Description of the dimension")
#    query = models.CharField(max_length=256, help_text="Django ORM query, Python code string")
#    created_at = models.DateTimeField(auto_now_add=True)
#    updated_at = models.DateTimeField(auto_now=True)
#
#class Metric(models.Model):
#    name = models.CharField(max_length=64, help_text="Name of the metric")
#    description = models.TextField(blank=True, null=True, help_text="Description of the metric")
#    query = models.CharField(max_length=256, help_text="Django ORM query, Python code string")
#    created_at = models.DateTimeField(auto_now_add=True)
#    updated_at = models.DateTimeField(auto_now=True)

def get_non_admins_count():
    """Returns the count of non-admin users, as relevant for Askbot analytics"""
    non_admins = User.objects.exclude(Q(is_superuser=True) | Q(is_staff=True))
    non_admins = non_admins.exclude(Q(askbot_profile__status='d') | Q(askbot_profile__status='m'))
    admin_filter = django_settings.ASKBOT_ANALYTICS_ADMINS_FILTER
    if admin_filter:
        non_admins = non_admins.exclude(**admin_filter)
    return non_admins.count()


def get_unique_user_email_domains_qs():
    """Returns the query set of organization domain names"""
    domain_annotation = Substr('email', StrIndex('email', Value('@')) + 1)
    return User.objects.annotate(domain=domain_annotation).values('domain').distinct()


def get_organizations_count():
    """Returns the count of organizations.
    An organization is a collection of users with the same email domain.
    """
    if not django_settings.ASKBOT_ANALYTICS_EMAIL_DOMAIN_ORGANIZATIONS_ENABLED:
        return 0
    return get_unique_user_email_domains_qs().count()


def get_unique_user_email_domains():
    """Returns a list of unique email domain names"""
    return list(get_unique_user_email_domains_qs().values_list('domain', flat=True))


class SessionManager(models.Manager):
    """Manager for the Session model"""
    def create_session(self, user, ip_address, user_agent):
        """Creates a new session"""
        now = timezone.now()
        return self.create(user=user,
                           ip_address=ip_address,
                           user_agent=user_agent,
                           created_at=now,
                           updated_at=now,
                           last_summarized_at=now)

    def get_active_session(self, user):
        """Filters out the session that has not expired and returns the first one,
        if there isn't one - returns None
        """
        timeout_minutes = django_settings.ASKBOT_ANALYTICS_SESSION_TIMEOUT_MINUTES
        timeout = datetime.timedelta(minutes=timeout_minutes)
        sessions = self.filter(user=user, updated_at__gte=timezone.now() - timeout)
        return sessions.first()

class Session(models.Model):
    """Analytics session"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, null=True, blank=True)
    created_at = models.DateTimeField() # no auto_now_add or auto_now for created_at and updated_at
    updated_at = models.DateTimeField() # b/c we want to set it manually for the testing purposes
    last_summarized_at = models.DateTimeField() # used for calculating the time on site

    objects = SessionManager()

    def __str__(self):
        created_at = self.created_at.isoformat() # pylint: disable=no-member
        updated_at = self.updated_at.isoformat() # pylint: disable=no-member
        email = self.user.email # pylint: disable=no-member
        return f"Session: {email} {created_at} - {updated_at}"

    def touch(self):
        """Updates the updated_at field"""
        self.updated_at = timezone.now()
        self.save()


class Event(models.Model):
    """Analytics event"""
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    event_type = models.SmallIntegerField(choices=EVENT_TYPES)
    timestamp = models.DateTimeField() # no auto_now_add or auto_now for created_at and updated_at
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    summarized = models.BooleanField(default=False,
                                   help_text="True if the event is included into a summary")

    def __str__(self):
        timestamp = self.timestamp.isoformat() # pylint: disable=no-member
        return f"Event: {self.get_event_type_display()} {timestamp}" # pylint: disable=no-member


class BaseSummary(models.Model):
    """
    An abstract model for per-interval summaries.
    An interval name is defined in the subclass.
    """
    num_questions = models.PositiveIntegerField(default=0)
    num_answers = models.PositiveIntegerField(default=0)
    num_upvotes = models.PositiveIntegerField(default=0)
    num_downvotes = models.PositiveIntegerField(default=0)
    question_views = models.PositiveIntegerField(default=0)
    time_on_site = models.DurationField(default=datetime.timedelta(0))
    summarized = models.BooleanField(default=False)

    class Meta: # pylint: disable=too-few-public-methods, missing-class-docstring
        abstract = True


    def add_event(self, event):
        """Increments the attribute appropriate for the event type"""
        if event.event_type == EVENT_TYPE_ASKED:
            self.num_questions += 1
        elif event.event_type == EVENT_TYPE_ANSWERED:
            self.num_answers += 1
        elif event.event_type == EVENT_TYPE_UPVOTED:
            self.num_upvotes += 1
        elif event.event_type == EVENT_TYPE_DOWNVOTED:
            self.num_downvotes += 1
        elif event.event_type == EVENT_TYPE_QUESTION_VIEWED:
            self.question_views += 1


    def __add__(self, other):
        """Adds the attributes of two summaries"""
        self.num_questions += other.num_questions
        self.num_answers += other.num_answers
        self.num_upvotes += other.num_upvotes
        self.num_downvotes += other.num_downvotes
        self.question_views += other.question_views
        self.time_on_site += other.time_on_site
        return self


class HourlySummary(BaseSummary):
    """An abstract class for hourly summaries."""
    hour = models.DateTimeField(db_index=True)

    class Meta: # pylint: disable=too-few-public-methods, missing-class-docstring
        abstract = True


class HourlyUserSummary(HourlySummary):
    """User summary for each hour with activity."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class HourlyGroupSummary(HourlySummary):
    """Group summary for each hour with activity."""
    group = models.ForeignKey(AskbotGroup, on_delete=models.CASCADE)
    num_users = models.PositiveIntegerField(
        default=0,
        help_text="Number of users in the group by the end of the hour"
    )
    num_users_added = models.PositiveIntegerField(
        default=0,
        help_text="Number of users added to the group during the hour"
    )


class DailySummary(BaseSummary):
    """An abstract class for daily summaries."""
    date = models.DateField(db_index=True)

    class Meta: # pylint: disable=too-few-public-methods, missing-class-docstring
        abstract = True


class DailyUserSummary(DailySummary):
    """User summary for each day with activity."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class DailyGroupSummary(DailySummary):
    """Group summary for each day with activity."""
    group = models.ForeignKey(AskbotGroup, on_delete=models.CASCADE)
    num_users = models.PositiveIntegerField(
        default=0,
        help_text="Number of users in the group by the end of the day"
    )
    num_users_added = models.PositiveIntegerField(
        default=0,
        help_text="Number of users added to the group during the day"
    )

    def add_event(self, event):
        raise RuntimeError("Cannot add events to DailyGroupSummary")

    def __add__(self, other):
        if not isinstance(other, HourlyGroupSummary):
            raise RuntimeError("Only HourlyGroupSummary can be added to DailyGroupSummary")
        super().__add__(other)
        self.num_users = other.num_users # assume that the last value is the correct one
        self.num_users_added += other.num_users_added
        return self


@receiver(signals.user_registered)
def record_user_registration(sender, user, **kwargs): # pylint: disable=unused-argument
    """Records user registration event"""
    session = Session.objects.get_active_session(user)
    if not session:
        return

    event = Event(
        session=Session.objects.get_active_session(user),
        event_type=EVENT_TYPE_USER_REGISTERED,
        timestamp=user.date_joined,
        content_object=user
    )
    event.save()


@receiver(signals.user_logged_in)
def record_user_login(sender, user, **kwargs): # pylint: disable=unused-argument
    """Records user login event"""
    session = Session.objects.get_active_session(user)
    if not session:
        return

    event = Event(
        session=session,
        event_type=EVENT_TYPE_LOGGED_IN,
        timestamp=timezone.now(),
        content_object=user
    )
    event.save()


@receiver(signals.voted)
def record_user_vote(sender, user=None, vote_type=None, canceled=None, # pylint: disable=unused-argument, too-many-arguments
                     post=None, timestamp=None, **kwargs): # pylint: disable=unused-argument
    """Records user vote event
    Event types:
    * EVENT_TYPE_UPVOTED = 6
    * EVENT_TYPE_DOWNVOTED = 7
    * EVENT_TYPE_VOTE_CANCELED = 8
    """
    session = Session.objects.get_active_session(user)
    if not session:
        return

    if canceled:
        event_type = EVENT_TYPE_VOTE_CANCELED
    elif vote_type == Vote.VOTE_UP:
        event_type = EVENT_TYPE_UPVOTED
    elif vote_type == Vote.VOTE_DOWN:
        event_type = EVENT_TYPE_DOWNVOTED
    else:
        return

    event = Event(
        session=session,
        event_type=event_type,
        timestamp=timestamp,
        content_object=post
    )
    event.save()


@receiver(signals.new_question_posted)
def record_new_question(sender, question, **kwargs): # pylint: disable=unused-argument
    """Records new question event"""
    session = Session.objects.get_active_session(question.author)
    if not session:
        return

    event = Event(
        session=session,
        event_type=EVENT_TYPE_ASKED,
        timestamp=question.added_at,
        content_object=question
    )
    event.save()


@receiver(signals.new_answer_posted)
def record_new_answer(sender, answer, **kwargs): # pylint: disable=unused-argument
    """Records new answer event"""
    session = Session.objects.get_active_session(answer.author)
    if not session:
        return

    event = Event(
        session=session,
        event_type=EVENT_TYPE_ANSWERED,
        timestamp=answer.added_at,
        content_object=answer
    )
    event.save()


@receiver(signals.new_comment_posted)
def record_new_comment(sender, comment, **kwargs): # pylint: disable=unused-argument
    """Records new comment event
    Event types:
    * EVENT_TYPE_QUESTION_COMMENTED = 11
    * EVENT_TYPE_ANSWER_COMMENTED = 12
    """
    session = Session.objects.get_active_session(comment.author)
    if not session:
        return

    parent_type = comment.parent.post_type
    if parent_type == 'question':
        event_type = EVENT_TYPE_QUESTION_COMMENTED
    elif parent_type == 'answer':
        event_type = EVENT_TYPE_ANSWER_COMMENTED
    else:
        return

    event = Event(
        session=session,
        event_type=event_type,
        timestamp=comment.added_at,
        content_object=comment
    )
    event.save()


@receiver(signals.tags_updated)
def record_tag_update(sender, thread=None, user=None, timestamp=None, **kwargs): # pylint: disable=unused-argument
    """Records tag update event"""
    session = Session.objects.get_active_session(user)
    if not session:
        return

    event = Event(
        session=session,
        event_type=EVENT_TYPE_QUESTION_RETAGGED,
        timestamp=timestamp,
        content_object=thread
    )
    event.save()

@receiver(signals.question_visited)
def record_question_visit(sender, request, question, timestamp, **kwargs): # pylint: disable=unused-argument
    """Records question visit event"""
    if not request.user.is_authenticated:
        return

    session = Session.objects.get_active_session(request.user)
    if not session:
        return

    event = Event(
        session=session,
        event_type=EVENT_TYPE_QUESTION_VIEWED,
        timestamp=timestamp,
        content_object=question
    )
    event.save()


"""
EVENT_TYPE_ANSWER_VIEWED = 5
EVENT_TYPE_SEARCHED = 14
"""