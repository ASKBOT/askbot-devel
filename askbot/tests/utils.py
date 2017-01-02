"""utility functions used by Askbot test cases
"""
from functools import wraps
from markdown2 import Markdown
from django.core.cache import cache
from django.test import TestCase
from askbot import models
from askbot import signals


def with_settings(**settings_dict):
    """a decorator that will run function with settings
    then apply previous settings and return the result
    of the function.
    If the function raises an exception - decorator
    still restores the previous settings
    """

    def decorator(func):

        @wraps(func)
        def wrapped(*args, **kwargs):
            from askbot.conf import settings as askbot_settings
            backup_settings_dict = dict()
            for key, value in settings_dict.items():
                backup_settings_dict[key] = getattr(askbot_settings, key)
                askbot_settings.update(key, value)

            try:
                return func(*args, **kwargs)
            except:
                raise
            finally:
                for key, value in backup_settings_dict.items():
                    askbot_settings.update(key, value)

        return wrapped

    return decorator



def create_user(
            username = None,
            email = None,
            notification_schedule = None,
            date_joined = None,
            status = 'a',
            reputation = 1
        ):
    """Creates a user and sets default update subscription
    settings

    ``notification_schedule`` is a dictionary with keys
    the same as in keys in
    :attr:`~askbot.models.EmailFeedSetting.FEED_TYPES`:

    * 'q_ask' - questions that user asks
    * 'q_all' - enture forum, tag filtered
    * 'q_ans' - questions that user answers
    * 'q_sel' - questions that user decides to follow
    * 'm_and_c' - comments and mentions of user anywhere

    and values as keys in
    :attr:`~askbot.models.EmailFeedSetting.FEED_TYPES`:

    * 'i' - instantly
    * 'd' - daily
    * 'w' - weekly
    * 'n' - never
    """
    user = models.User.objects.create_user(username, email)

    user.reputation = reputation
    if date_joined is not None:
        user.date_joined = date_joined
        user.save()
    if notification_schedule == None:
        notification_schedule = models.EmailFeedSetting.NO_EMAIL_SCHEDULE

    #a hack, we need to delete these, that will be created automatically
    #because just below we will be replacing them with the new values
    user.notification_subscriptions.all().delete()

    for feed_type, frequency in notification_schedule.items():
        feed = models.EmailFeedSetting(
                        feed_type = feed_type,
                        frequency = frequency,
                        subscriber = user
                    )
        feed.save()

    signals.user_registered.send(None, user=user)
    user.set_status(status)

    return user


class AskbotTestCase(TestCase):
    """adds some askbot-specific methods
    to django TestCase class
    """

    @classmethod
    def setUpClass(cls):
        cache.clear()
        super(AskbotTestCase, cls).setUpClass()

    def create_user(
                self,
                username='user',
                email=None,
                notification_schedule=None,
                date_joined=None,
                reputation=1,
                status='a'
            ):
        """creates user with username, etc and
        makes the result accessible as

        self.<username>

        newly created user object is also returned
        """
        assert(username is not None)
        assert(not hasattr(self, username))

        if email is None:
            email = username + '@example.com'

        user_object = create_user(
                    username=username,
                    email=email,
                    notification_schedule=notification_schedule,
                    date_joined=date_joined,
                    status=status,
                    reputation=reputation
                )

        setattr(self, username, user_object)
        return user_object

    def assertRaisesRegexp(self, *args, **kwargs):
        """a shim for python < 2.7"""
        try:
            #run assertRaisesRegex, if available
            super(AskbotTestCase, self).assertRaisesRegexp(*args, **kwargs)
        except AttributeError:
            #in this case lose testing for the error text
            #second argument is the regex that is supposed
            #to match the error text
            args_list = list(args)#conv tuple to list
            args_list.pop(1)#so we can remove an item
            self.assertRaises(*args_list, **kwargs)

    def assertQuerysetEqual(self, qs1, qs2, transform=repr, ordered=True):
        '''borrowed from django1.4 and modified a bit'''
        items = map(transform, qs1)
        values = map(transform, qs2)
        if not ordered:
            return self.assertEqual(set(items), set(values))
        return self.assertEqual(list(items), list(values))

    def post_question(
                    self,
                    user=None,
                    title='test question title',
                    body_text='test question body text',
                    tags='test',
                    by_email=False,
                    wiki=False,
                    is_anonymous=False,
                    is_private=False,
                    group_id=None,
                    follow=False,
                    timestamp=None,
                ):
        """posts and returns question on behalf
        of user. If user is not given, it will be self.user

        ``tags`` is a string with tagnames

        if follow is True, question is followed by the poster
        """

        if user is None:
            user = self.user

        question = user.post_question(
                            title=title,
                            body_text=body_text,
                            tags=tags,
                            by_email=by_email,
                            wiki=wiki,
                            is_anonymous=is_anonymous,
                            is_private=is_private,
                            group_id=group_id,
                            timestamp=timestamp
                        )

        if follow:
            user.follow_question(question)

        return question

    def edit_question(self,
                user=None,
                question=None,
                title='edited title',
                body_text='edited body text',
                revision_comment='edited the question',
                tags='one two three four',
                wiki=False,
                edit_anonymously=False,
                is_private=False,
                timestamp=None,
                force=False,#if True - bypass the assert
                by_email=False
            ):
        """helper editing the question,
        a bunch of fields are pre-filled for the ease of use
        """
        user.edit_question(
            question=question,
            title=title,
            body_text=body_text,
            revision_comment=revision_comment,
            tags=tags,
            wiki=wiki,
            edit_anonymously=edit_anonymously,
            is_private=is_private,
            timestamp=timestamp,
            force=False,#if True - bypass the assert
            by_email=False
        )

    def edit_answer(self,
            user=None,
            answer=None,
            body_text='edited answer body',
            revision_comment='editing answer',
            wiki=False,
            is_private=False,
            timestamp=None,
            force=False,#if True - bypass the assert
            by_email=False
        ):
        user.edit_answer(
            answer=answer,
            body_text=body_text,
            revision_comment=revision_comment,
            wiki=wiki,
            is_private=is_private,
            timestamp=timestamp,
            force=force,
            by_email=by_email
        )

    def reload_object(self, obj):
        """reloads model object from the database
        """
        return obj.__class__.objects.get(id = obj.id)

    def post_answer(
                    self,
                    user = None,
                    question = None,
                    body_text = 'test answer text',
                    by_email = False,
                    follow = False,
                    wiki = False,
                    is_private = False,
                    timestamp = None
                ):

        if user is None:
            user = self.user
        return user.post_answer(
                        question = question,
                        body_text = body_text,
                        by_email = by_email,
                        follow = follow,
                        wiki = wiki,
                        is_private = is_private,
                        timestamp = timestamp
                    )

    def create_tag(self, tag_name, user = None):
        """creates a user, b/c it is necessary"""
        if user is None:
            try:
                user = models.User.objects.get(username = 'tag_creator')
            except models.User.DoesNotExist:
                user = self.create_user('tag_creator')

        tag = models.Tag(created_by=user, name=tag_name, language_code='en')
        tag.save()
        return tag

    def create_group(self, group_name=None, openness=models.Group.OPEN):
        return models.Group.objects.get_or_create(
                    name='private', openness=openness
                )

    def post_comment(
                self,
                user = None,
                parent_post = None,
                body_text = 'test comment text',
                by_email = False,
                timestamp = None
            ):
        """posts and returns a comment to parent post, uses
        now timestamp if not given, dummy body_text
        author is required
        """
        if user is None:
            user = self.user

        comment = user.post_comment(
                        parent_post = parent_post,
                        body_text = body_text,
                        by_email = by_email,
                        timestamp = timestamp,
                    )

        return comment

"""
Some test decorators, taken from Django-1.3
"""


class SkipTest(Exception):
    """
    Raise this exception in a test to skip it.

    Usually you can use TestResult.skip() or one of the skipping decorators
    instead of raising this directly.
    """


def _id(obj):
    return obj


def skip(reason):
    """
    Unconditionally skip a test.
    """
    def decorator(test_item):
        if not (isinstance(test_item, type) and issubclass(test_item, TestCase)):
            @wraps(test_item)
            def skip_wrapper(*args, **kwargs):
                raise SkipTest(reason)
            test_item = skip_wrapper

        test_item.__unittest_skip__ = True
        test_item.__unittest_skip_why__ = reason
        return test_item
    return decorator


def skipIf(condition, reason):
    """
    Skip a test if the condition is true.
    """
    if condition:
        return skip(reason)
    return _id
