"""Adds analytics content to the database for testing purposes."""
# pylint: disable=trailing-newlines
import random
import sys
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.conf import settings as django_settings
from askbot.models import User, Activity, Post
from askbot.models.analytics import Session
from askbot.utils.console import ProgressBar
from askbot.utils.functions import generate_random_key
from askbot import const

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:2.0b8pre) Gecko/20101221 Firefox/4.0b8pre',
    'Chrome/14.0.835.202 Safari/535.1',
    'Samsung-SGH-i900/1.0 (compatible; MSIE 6.0; Windows CE; IEMobile 7.11)',
    'Safari/6533.18.5',
    'Opera/9.80 (Windows NT 6.1; U; en) Presto/2.8.131 Version/11.10',
]

class Command(BaseCommand): #pylint: disable=missing-docstring
    def handle(self, *args, **options): #pylint: disable=unused-argument,missing-docstring
        """Using the current askbot database, adds analytics events
        and fake sessions"""
        users = User.objects.all() # pylint: disable=no-member
        count = users.count()
        message = 'Adding analytics content to the database for each user'
        for user in ProgressBar(users.iterator(), count, message):
            self.add_analytics_content(user)


    def add_analytics_content(self, user):
        """Adds analytics content to the database for the given user."""
        #print(f'Adding analytics content for user {user.username}')

        # for each user add a TYPE_ACTIVITY_USER_REGISTERED
        Activity.objects.create(user=user, # pylint: disable=no-member
                                activity_type=const.TYPE_ACTIVITY_USER_REGISTERED,
                                active_at=user.date_joined,
                                content_object=user)

        # find an answer posted before user.last_seen,
        # add "question viewed" and "answer viewed
        # activities for those, active_at should be 10 minutes after the answer is posted
        try:
            answer = Post.objects.filter(post_type='answer', added_at__lte=user.last_seen).first() # pylint: disable=no-member, line-too-long
        except Post.DoesNotExist: # pylint: disable=no-member
            pass
        else:
            question = answer.thread._question_post() # pylint: disable=protected-access
            Activity.objects.create(user=user,
                                    activity_type=const.TYPE_ACTIVITY_QUESTION_VIEWED,
                                    active_at=user.date_joined + timedelta(minutes=10),
                                    content_object=question)
            Activity.objects.create(user=user,
                                    activity_type=const.TYPE_ACTIVITY_ANSWER_VIEWED,
                                    active_at=user.date_joined + timedelta(minutes=11),
                                    content_object=answer)

        # attach a session to each activity
        count = 0
        activities = user.activity_set.filter(activity_type__in=const.TYPE_ACTIVITY_BY_USER)
        activities = activities.order_by('active_at')
        for act in activities.only('id', 'active_at').iterator():
            timestamp = act.active_at
            session = self.get_session(user, timestamp)
            #print(act)
            #print(session)
            Session.objects.filter(id=session.id).update(updated_at=timestamp) # pylint: disable=no-member
            Activity.objects.filter(id=act.id).update(session=session) # pylint: disable=no-member
            count += 1

        #print(f'Added {count} activities for user {user.username}')
        sys.stdout.flush()

    def get_session(self, user, timestamp):
        """Returns session object for the given user and timestamp."""
        try:
            timeout_delta = timedelta(minutes=django_settings.ASKBOT_ANALYTICS_SESSION_TIMEOUT_MINUTES) # pylint: disable=line-too-long
            session = Session.objects.get(user=user, # pylint: disable=no-member
                                          created_at__lte=timestamp,
                                          updated_at__gt=timestamp - timeout_delta)
            #print('reusing session')
            sys.stdout.flush()
        except Session.DoesNotExist: # pylint: disable=no-member
            session = Session()
            session.session_id = generate_random_key(32)
            session.user = user
            session.ip_address = '0.0.0.0'
            session.user_agent = random.choice(USER_AGENTS)
            session.created_at = timestamp
            session.updated_at = timestamp
            session.save()
            #print('created new session')
            sys.stdout.flush()
        except Session.MultipleObjectsReturned:
            sessions = Session.objects.filter(user=user, # pylint: disable=no-member
                                              created_at__lte=timestamp,
                                              updated_at__gt=timestamp - timeout_delta)
            import pdb; pdb.set_trace()
        return session

