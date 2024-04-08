from django.db import models
from django.db.models import Q
from django.db.models import Value
from django.db.models.functions import Substr, StrIndex
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.conf import settings as django_settings
from django.utils.translation import gettext_lazy as _

"""
for convenience, here are the activity types from used in the Activity object
TYPE_ACTIVITY_ASK_QUESTION = 1
TYPE_ACTIVITY_ANSWER = 2
TYPE_ACTIVITY_COMMENT_QUESTION = 3
TYPE_ACTIVITY_COMMENT_ANSWER = 4
TYPE_ACTIVITY_UPDATE_QUESTION = 5
TYPE_ACTIVITY_UPDATE_ANSWER = 6
TYPE_ACTIVITY_PRIZE = 7
TYPE_ACTIVITY_MARK_ANSWER = 8
TYPE_ACTIVITY_VOTE_UP = 9
TYPE_ACTIVITY_VOTE_DOWN = 10
TYPE_ACTIVITY_CANCEL_VOTE = 11
TYPE_ACTIVITY_DELETE_QUESTION = 12
TYPE_ACTIVITY_DELETE_ANSWER = 13
TYPE_ACTIVITY_MARK_OFFENSIVE = 14
TYPE_ACTIVITY_UPDATE_TAGS = 15
TYPE_ACTIVITY_FAVORITE = 16
TYPE_ACTIVITY_USER_FULL_UPDATED = 17
TYPE_ACTIVITY_EMAIL_UPDATE_SENT = 18
TYPE_ACTIVITY_MENTION = 19
TYPE_ACTIVITY_UNANSWERED_REMINDER_SENT = 20
TYPE_ACTIVITY_ACCEPT_ANSWER_REMINDER_SENT = 21
TYPE_ACTIVITY_CREATE_TAG_WIKI = 22
TYPE_ACTIVITY_UPDATE_TAG_WIKI = 23
TYPE_ACTIVITY_MODERATED_NEW_POST = 24
TYPE_ACTIVITY_MODERATED_POST_EDIT = 25
TYPE_ACTIVITY_CREATE_REJECT_REASON = 26
TYPE_ACTIVITY_UPDATE_REJECT_REASON = 27
TYPE_ACTIVITY_VALIDATION_EMAIL_SENT = 28
TYPE_ACTIVITY_POST_SHARED = 29
TYPE_ACTIVITY_ASK_TO_JOIN_GROUP = 30
TYPE_ACTIVITY_MODERATION_ALERT_SENT = 31
TYPE_ACTIVITY_FORBIDDEN_PHRASE_FOUND = 50 #added gap
TYPE_ACTIVITY_USER_REGISTERED = 51
TYPE_ACTIVITY_QUESTION_VIEWED = 52
TYPE_ACTIVITY_ANSWER_VIEWED = 53
""" #pylint: disable=pointless-string-statement

EVENT_TYPES = (
    (1, _('registered')), # Activity.activity_type == 51
    (2, _('logged in')),
    (3, _('logged out')),
    (4, _('question viewed')), # Activity.activity_type == 52
    (5, _('answer viewed')), # Activity.activity_type == 53
    (6, _('upvoted')), # Activity.activity_type == 9
    (7, _('downvoted')), # Activity.activity_type == 10
    (8, _('canceled vote')), # Activity.activity_type == 11
    (9, _('asked')), # Activity.activity_type == 1
    (10, _('answered')), # Activity.activity_type == 2
    (11, _('commented question')), # Activity.activity_type == 3
    (12, _('commented answer')), # Activity.activity_type == 4
    (13, _('retagged question')), # Activity.activity_type == 15
    (14, _('searched')),
)

"""
class Dimension(models.Model):
    name = models.CharField(max_length=64, help_text="Name of the dimension")
    description = models.TextField(blank=True, null=True, help_text="Description of the dimension")
    query = models.CharField(max_length=256, help_text="Django ORM query, Python code string")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Metric(models.Model):
    name = models.CharField(max_length=64, help_text="Name of the metric")
    description = models.TextField(blank=True, null=True, help_text="Description of the metric")
    query = models.CharField(max_length=256, help_text="Django ORM query, Python code string")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
"""

def get_non_admins_count():
    """Returns the count of non-admin users, as relevant for Askbot analytics"""
    non_admins = User.objects.exclude(Q(is_superuser=True) | Q(is_staff=True))
    non_admins = non_admins.exclude(Q(askbot_profile__status='d') | Q(askbot_profile__status='m'))
    admin_filter = django_settings.ASKBOT_ANALYTICS_ADMINS_FILTER
    if admin_filter:
        non_admins = non_admins.exclude(**admin_filter)
    return non_admins.count()


def get_organization_domains():
    """Returns the query set of organization domain names"""
    domain_annotation = Substr('email', StrIndex('email', Value('@')) + 1)
    return User.objects.annotate(domain=domain_annotation).values('domain').distinct()


def get_organizations_count():
    """Returns the count of organizations.
    An organization is a collection of users with the same email domain.
    """
    if not django_settings.ASKBOT_ANALYTICS_EMAIL_DOMAIN_ORGANIZATIONS_ENABLED:
        return 0
    return get_organization_domains().count()


class Session(models.Model):
    """Analytics session"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, null=True, blank=True)
    created_at = models.DateTimeField() # no auto_now_ad or auto_now for created_at and updated_at
    updated_at = models.DateTimeField() # because we want to set it manually for the testing purposes

    def __str__(self):
        return f"Session: {self.user.email} {self.created_at.isoformat()} - {self.updated_at.isoformat()}"

class Event(models.Model):
    """Analytics event"""
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=64, choices=EVENT_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = fields.GenericForeignKey('content_type', 'object_id')

    def __str__(self):
        return f"Event: {self.event_type} {self.created_at.isoformat()}"

