# -*- coding: utf-8 -*-
import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from picklefield.fields import PickledObjectField

import hashlib, random, sys, os, time

VERIFIER_EXPIRE_DAYS = getattr(settings, 'VERIFIER_EXPIRE_DAYS', 3)

__all__ = ['Nonce', 'Association', 'UserAssociation',
        'UserPasswordQueueManager', 'UserPasswordQueue',
        'UserEmailVerifier']

class Nonce(models.Model):
    """ openid nonce """
    server_url = models.CharField(max_length=255)
    timestamp = models.IntegerField()
    salt = models.CharField(max_length=40)

    def __unicode__(self):
        return u"Nonce: %s" % self.id


class Association(models.Model):
    """ association openid url and lifetime """
    server_url = models.TextField(max_length=2047)
    handle = models.CharField(max_length=255)
    secret = models.TextField(max_length=255) # Stored base64 encoded
    issued = models.IntegerField()
    lifetime = models.IntegerField()
    assoc_type = models.TextField(max_length=64)

    def __unicode__(self):
        return u"Association: %s, %s" % (self.server_url, self.handle)

class UserAssociation(models.Model):
    """
    model to manage association between openid and user
    """
    #todo: rename this field so that it sounds good for other methods
    #for exaple, for password provider this will hold password
    openid_url = models.CharField(blank=False, max_length=255)
    user = models.ForeignKey(User)
    #in the future this must be turned into an
    #association with a Provider record
    #to hold things like login badge, etc
    provider_name = models.CharField(max_length=64, default='unknown')
    last_used_timestamp = models.DateTimeField(null=True)

    class Meta(object):
        unique_together = (
                                ('user','provider_name'),
                                ('openid_url', 'provider_name')
                            )

    def __unicode__(self):
        return u"Openid %s with user %s" % (self.openid_url, self.user)

    def update_timestamp(self):
        self.last_used_timestamp = datetime.datetime.now()
        self.save()

class UserPasswordQueueManager(models.Manager):
    """ manager for UserPasswordQueue object """
    def get_new_confirm_key(self):
        "Returns key that isn't being used."
        # The random module is seeded when this Apache child is created.
        # Use SECRET_KEY as added salt.
        while 1:
            confirm_key = hashlib.md5("%s%s%s%s" % (
                random.randint(0, sys.maxint - 1), os.getpid(),
                time.time(), settings.SECRET_KEY)).hexdigest()
            try:
                self.get(confirm_key=confirm_key)
            except self.model.DoesNotExist:
                break
        return confirm_key


class UserPasswordQueue(models.Model):
    """
    model for new password queue.
    """
    user = models.OneToOneField(User)
    new_password = models.CharField(max_length=30)
    confirm_key = models.CharField(max_length=40)

    objects = UserPasswordQueueManager()

    def __unicode__(self):
        return self.user.username

class UserEmailVerifier(models.Model):
    '''Model that stores the required values to verify an email
    address'''
    key = models.CharField(max_length=255, unique=True, primary_key=True)
    value = PickledObjectField()
    verified = models.BooleanField(default=False)
    expires_on = models.DateTimeField(blank=True)

    def save(self, *args, **kwargs):
        if not self.expires_on:
            self.expires_on = timezone.now() + \
                    datetime.timedelta(VERIFIER_EXPIRE_DAYS)

        super(UserEmailVerifier, self).save(*args, **kwargs)

    def has_expired(self):
        now = timezone.now()
        return now > self.expires_on

    def __unicode__(self):
        return self.key
