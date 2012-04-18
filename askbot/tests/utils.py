"""utility functions used by Askbot test cases
"""
from django.test import TestCase
from functools import wraps
from askbot import models

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
    user.set_status(status)
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
    return user


class AskbotTestCase(TestCase):
    """adds some askbot-specific methods
    to django TestCase class
    """

    def create_user(
                self,
                username = 'user',
                email = None,
                notification_schedule = None,
                date_joined = None,
                status = 'a'
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
                    username = username,
                    email = email,
                    notification_schedule = notification_schedule,
                    date_joined = date_joined,
                    status = status
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


    def post_question(
                    self, 
                    user = None,
                    title = 'test question title',
                    body_text = 'test question body text',
                    tags = 'test',
                    wiki = False,
                    is_anonymous = False,
                    follow = False,
                    timestamp = None
                ):
        """posts and returns question on behalf
        of user. If user is not given, it will be self.user

        ``tags`` is a string with tagnames

        if follow is True, question is followed by the poster
        """

        if user is None:
            user = self.user

        question = user.post_question(
                            title = title,
                            body_text = body_text,
                            tags = tags,
                            wiki = wiki,
                            is_anonymous = is_anonymous,
                            timestamp = timestamp
                        )

        if follow:
            user.follow_question(question)

        return question

    def reload_object(self, obj):
        """reloads model object from the database
        """
        return obj.__class__.objects.get(id = obj.id)
        
    def post_answer(
                    self,
                    user = None,
                    question = None,
                    body_text = 'test answer text',
                    follow = False,
                    wiki = False,
                    timestamp = None
                ):

        if user is None:
            user = self.user
        return user.post_answer(
                        question = question,
                        body_text = body_text,
                        follow = follow,
                        wiki = wiki,
                        timestamp = timestamp
                    )

    def post_comment(
                self,
                user = None,
                parent_post = None,
                body_text = 'test comment text',
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
