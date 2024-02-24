
import sys
from askbot.conf import settings as askbot_settings
from askbot.models import User
from askbot.utils.console import choice_dialog
from django.core.management import BaseCommand
from django.conf import settings as django_settings
from django.utils import translation
from askbot.utils.translation import get_language


NUM_USERS = 40
# KEEP NEXT 3 SETTINGS LESS THAN OR EQUAL TO NUM_USERS!
NUM_QUESTIONS = 40
NUM_ANSWERS = 20
NUM_COMMENTS = 20

# To ensure that all the actions can be made, repute each user high positive
# karma. This can be calculated dynamically - max of MIN_REP_TO_... settings
INITIAL_REPUTATION = 500

if '--with-spam' in sys.argv:
    BAD_STUFF = "<script>alert('hohoho')</script>"
else:
    BAD_STUFF = ''

# Defining template inputs.
USERNAME_TEMPLATE = "test_user_%s"
PASSWORD_TEMPLATE = "test_password_%s"
EMAIL_TEMPLATE = "test_user_%s@askbot.org"
TITLE_TEMPLATE = "Question No.%s"
LONG_TITLE_TEMPLATE = TITLE_TEMPLATE + 'a lot more text a lot more text a lot more text '*5
TAGS_TEMPLATE = ["tag-%s-0", "tag-%s-1"] # len(TAGS_TEMPLATE) tags per question

CONTENT_TEMPLATE = """Lorem lean startup ipsum product market fit customer
                    development acquihire technical cofounder. User engagement
                    **A/B** testing *shrink* a market venture capital pitch."""

ANSWER_TEMPLATE = """Accelerator photo sharing business school drop out ramen
                    hustle crush it revenue traction platforms."""

COMMENT_TEMPLATE = """Main differentiators business model micro economics
                    marketplace equity augmented reality human computer"""

ALERT_SETTINGS_KEYS = (
    'DEFAULT_NOTIFICATION_DELIVERY_SCHEDULE_Q_ASK',
    'DEFAULT_NOTIFICATION_DELIVERY_SCHEDULE_Q_ANS',
    'DEFAULT_NOTIFICATION_DELIVERY_SCHEDULE_Q_ALL',
    'DEFAULT_NOTIFICATION_DELIVERY_SCHEDULE_Q_SEL',
    'DEFAULT_NOTIFICATION_DELIVERY_SCHEDULE_M_AND_C',
)

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--noinput', action='store_false', dest='interactive', default=True,
            help='Do not prompt the user for input of any kind.'
        )
        parser.add_argument(
            '--with-spam', action='store_true', dest='with_spam', default=False,
            help='Add XSS snippets'
        )

    def bad_stuff(self):
        if self.options['with_spam']:
            return "<script>alert('hohoho')</script>"
        return ''

    def backup_settings(self):
        settings = {}
        for key in ALERT_SETTINGS_KEYS:
            settings[key] = getattr(askbot_settings, key)
        self.alert_settings = settings
        self.limit_on_answer_setting = askbot_settings.LIMIT_ONE_ANSWER_PER_USER


    def modify_settings(self):
        for key in ALERT_SETTINGS_KEYS:
            askbot_settings.update(key, 'n')
        askbot_settings.update('LIMIT_ONE_ANSWER_PER_USER', False)

    def restore_settings(self):
        for key in ALERT_SETTINGS_KEYS:
            askbot_settings.update(key, self.alert_settings[key])
        value = self.limit_on_answer_setting
        askbot_settings.update('LIMIT_ONE_ANSWER_PER_USER', value)

    def print_if_verbose(self, text):
        "Only print if user chooses verbose output"
        if self.verbosity > 0:
            print(text)

    def create_users(self):
        "Create the users and return an array of created users"
        users = []

        #add admin with the same password - this user will be admin automatically
        admin = User.objects.create_user('admin', 'admin@example.com')
        admin.set_password('admin')
        admin.save()
        self.print_if_verbose("Created User 'admin'")
        users.append(admin)

        #this user will have regular privileges, because it's second
        joe = User.objects.create_user('joe', 'joe@example.com')
        joe.set_password('joe')
        joe.save()
        self.print_if_verbose("Created User 'joe'")

        # Keeping the created users in array - we will iterate over them
        # several times, we don't want querying the model each and every time.
        for i in range(NUM_USERS):
            s_idx = str(i)
            username = self.bad_stuff() + USERNAME_TEMPLATE % s_idx
            user = User.objects.create_user(username,
                                            EMAIL_TEMPLATE % s_idx)
            user.set_password(PASSWORD_TEMPLATE % s_idx)
            user.receive_reputation(INITIAL_REPUTATION, get_language())
            user.save()
            self.print_if_verbose("Created User '%s'" % user.username)
            users.append(user)

        return users


    def create_questions(self, users):
        "Create the questions and return the last one as active question"

        # Keeping the last active question entry for later use. Questions API
        # might change, so we rely solely on User data entry API.
        active_question = None
        last_vote = False
        # Each user posts a question
        for i in range(NUM_QUESTIONS):
            user = users[i % len(users)]#allows to post many questions all by less users
            # Downvote/upvote the questions - It's reproducible, yet
            # gives good randomized data
            if not active_question is None:
                if last_vote:
                    user.downvote(active_question)
                    self.print_if_verbose("%s downvoted a question"%(
                                        user.username
                                    ))
                else:
                    user.upvote(active_question)
                    self.print_if_verbose("%s upvoted a question"%(
                                        user.username
                                    ))
                last_vote = ~last_vote

            # len(TAGS_TEMPLATE) tags per question - each tag is different
            tags = " ".join([(t + self.bad_stuff()) % user.id for t in TAGS_TEMPLATE])
            if i < NUM_QUESTIONS/2:
                tags += ' one-tag'

            if i % 2 == 0:
                question_template = TITLE_TEMPLATE + self.bad_stuff()
            else:
                question_template = LONG_TITLE_TEMPLATE + self.bad_stuff()

            active_question = user.post_question(
                        title = question_template % user.id,
                        body_text = self.bad_stuff() + CONTENT_TEMPLATE,
                        tags = tags,
                    )

            self.print_if_verbose("Created Question '{}' with tags: '{}'".format(
                                                active_question.thread.title, tags,)
                                            )
        return active_question


    def create_answers(self, users, active_question):
        "Create the answers for the active question, return the active answer"
        active_answer = None
        last_vote = False
        # Now, fill the last added question with answers
        for i in range(NUM_ANSWERS):
            user = users[i % len(users)]
            # We don't need to test for data validation, so ONLY users
            # that aren't authors can post answer to the question
            if not active_question.author is user:
                # Downvote/upvote the answers - It's reproducible, yet
                # gives good randomized data
                if not active_answer is None:
                    if last_vote:
                        user.downvote(active_answer)
                        self.print_if_verbose("%s downvoted an answer"%(
                                            user.username
                                        ))
                    else:
                        user.upvote(active_answer)
                        self.print_if_verbose("%s upvoted an answer"%(
                                            user.username
                                        ))
                    last_vote = ~last_vote

                active_answer = user.post_answer(
                        question = active_question,
                        body_text = self.bad_stuff() + ANSWER_TEMPLATE,
                        follow = True
                    )
                self.print_if_verbose("%s posted an answer to the active question"%(
                                            user.username
                                        ))
                # Upvote the active question
                user.upvote(active_question)
                # Follow the active question
                user.follow_question(active_question)
                self.print_if_verbose("%s followed the active question"%(
                                                user.username)
                                            )
                # Subscribe to the active question
                user.subscribe_for_followed_question_alerts()
                self.print_if_verbose("%s subscribed to followed questions"%(
                                                user.username)
                                            )
        return active_answer


    def create_comments(self, users, active_question, active_answer):
        """Create the comments for the active question and the active answer,
        return 2 active comments - 1 question comment and 1 answer comment"""

        active_question_comment = None
        active_answer_comment = None

        for i in range(NUM_COMMENTS):
            user = users[i % len(users)]
            active_question_comment = user.post_comment(
                                    parent_post = active_question,
                                    body_text = self.bad_stuff() + COMMENT_TEMPLATE
                                )
            self.print_if_verbose("%s posted a question comment"%user.username)
            active_answer_comment = user.post_comment(
                                    parent_post = active_answer,
                                    body_text = self.bad_stuff() + COMMENT_TEMPLATE
                                )
            self.print_if_verbose("%s posted an answer comment"%user.username)

            # Upvote the active answer
            user.upvote(active_answer)

        # Upvote active comments
        if active_question_comment and active_answer_comment:
            num_upvotees = NUM_COMMENTS - 1
            for user in users[:num_upvotees]:
                user.upvote(active_question_comment)
                user.upvote(active_answer_comment)

        return active_question_comment, active_answer_comment


    def handle(self, **options):
        self.options = options
        self.verbosity = int(options.get("verbosity", 1))
        self.interactive = options.get("interactive")

        # post a bunch of answers by admin now - that active_question is
        # posted by someone else
        if self.interactive:
            answer = choice_dialog("This command will DELETE ALL DATA in the current database, and will fill the database with test data. Are you absolutely sure you want to proceed?",
                            choices = ("yes", "no", ))
            if answer != "yes":
                return

        translation.activate(django_settings.LANGUAGE_CODE)
        self.backup_settings()
        self.modify_settings()# saves time on running the command

        # Create Users
        users = self.create_users()

        # Create a bunch of questions and answers by a single user
        # to test pagination in the user profile
        active_question = self.create_questions(users[0:1])

        # Create Questions, vote for questions by all other users
        active_question = self.create_questions(users)

        active_answer = self.create_answers(users[0:1], active_question)

        # Create Answers, vote for the answers, vote for the active question
        # vote for the active answer
        active_answer = self.create_answers(users, active_question)

        # Create Comments, vote for the active answer
        active_question_comment, active_answer_comment = self.create_comments(
                                users, active_question, active_answer)

        # Edit the active question, answer and comments
        active_question.author.edit_question(
                            question = active_question,
                            title = TITLE_TEMPLATE % "EDITED",
                            body_text = self.bad_stuff() + CONTENT_TEMPLATE,
                            revision_comment = "EDITED",
                            force = True
                        )
        self.print_if_verbose("User has edited the active question")

        active_answer.author.edit_answer(
                            answer = active_answer,
                            body_text = self.bad_stuff() + COMMENT_TEMPLATE,
                            force = True
                        )
        self.print_if_verbose("User has edited the active answer")

        active_answer_comment.author.edit_comment(
                            comment_post = active_answer_comment,
                            body_text = self.bad_stuff() + ANSWER_TEMPLATE
                        )
        self.print_if_verbose("User has edited the active answer comment")

        active_question_comment.author.edit_comment(
                            comment_post = active_question_comment,
                            body_text = self.bad_stuff() + ANSWER_TEMPLATE
                        )
        self.print_if_verbose("User has edited the active question comment")

        # Accept best answer
        active_question.author.accept_best_answer(
                            answer = active_answer,
                            force = True,
                        )
        self.print_if_verbose("User has accepted a best answer")
        self.restore_settings()
        self.print_if_verbose("DONE")
