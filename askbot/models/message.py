'''Copied from Django 1.3.1 source code, it will use this model to'''
from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy


class Message(models.Model):
    """
    The message system is a lightweight way to queue messages for given
    users. A message is associated with a User instance (so it is only
    applicable for registered users). There's no concept of expiration or
    timestamps. Messages are created by the Django admin after successful
    actions. For example, "The poll Foo was created successfully." is a
    message.
    """
    user = models.ForeignKey(User, related_name='_message_set')
    message = models.TextField(ugettext_lazy('message'))

    class Meta:
        '''Added for backwards compatibility with databases
           migrated from django 1.3'''
        app_label = 'askbot'
        db_table = 'askbot_message'

    def __unicode__(self):
        return self.message

    def __str__(self):
        return self.message.encode('utf-8')
