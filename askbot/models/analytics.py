from django.db import models
from django.db.models import Q
from django.db.models import Value, Count
from django.db.models.functions import Substr, StrIndex
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model

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
    session_id = models.CharField(max_length=40, help_text="Django session ID")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=512)
    created_at = models.DateTimeField() # no auto_now_ad or auto_now for created_at and updated_at
    updated_at = models.DateTimeField() # because we want to set it manually for the testing purposes

    def __str__(self):
        return f"Session: {self.user.email} {self.created_at.isoformat()} - {self.updated_at.isoformat()}"


# Event model is users.Activity - probably will be moved here
