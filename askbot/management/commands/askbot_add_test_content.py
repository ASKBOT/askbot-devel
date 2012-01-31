from django.core.management.base import NoArgsCommand
from askbot.models import User
from optparse import make_option
from askbot.utils.console import choice_dialog


NUM_USERS = 40
# KEEP NEXT 3 SETTINGS LESS THAN OR EQUAL TO NUM_USERS!
NUM_QUESTIONS = 40
NUM_ANSWERS = 20
NUM_COMMENTS = 20

# To ensure that all the actions can be made, repute each user high positive
# karma. This can be calculated dynamically - max of MIN_REP_TO_... settings
INITIAL_REPUTATION = 500

# Defining template inputs.
USERNAME_TEMPLATE = "test_user_%s"
PASSWORD_TEMPLATE = "test_password_%s"
EMAIL_TEMPLATE = "test_user_%s@askbot.org"
TITLE_TEMPLATE = "Test question title No.%s"
TAGS_TEMPLATE = ["tag-%s-0", "tag-%s-1"] # len(TAGS_TEMPLATE) tags per question

CONTENT_TEMPLATE = """Lorem lean startup ipsum product market fit customer
                    development acquihire technical cofounder. User engagement
                    **A/B** testing *shrink* a market venture capital pitch."""

ANSWER_TEMPLATE = """Accelerator photo sharing business school drop out ramen
                    hustle crush it revenue traction platforms."""

COMMENT_TEMPLATE = """Main differentiators business model micro economics
                    marketplace equity augmented reality human computer"""


class Command(NoArgsCommand):
    option_list = NoArgsCommand.option_list + (
        make_option('--noinput', action='store_false', dest='interactive', default=True,
            help='Do not prompt the user for input of any kind.'),
    )

    def print_if_verbose(self, text):
        "Only print if user chooses verbose output"
        if self.verbosity > 0:
            print text

    def create_users(self):
        "Create the users and return an array of created users"
        users = []

        #add admin with the same password
        admin = User.objects.create_user('admin', 'admin@example.com')
        admin.set_password('admin')
        self.print_if_verbose("Created User 'admin'")
        users.append(admin)

        # Keeping the created users in array - we will iterate over them
        # several times, we don't want querying the model each and every time.
        for i in range(NUM_USERS):
            s_idx = str(i)
            user = User.objects.create_user(USERNAME_TEMPLATE % s_idx,
                                            EMAIL_TEMPLATE % s_idx)
            user.set_password(PASSWORD_TEMPLATE % s_idx)
            user.reputation = INITIAL_REPUTATION
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
            user = users[i]
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
            tags = " ".join([t%user.id for t in TAGS_TEMPLATE])
            if i < NUM_QUESTIONS/2:
                tags += ' one-tag'
            active_question = user.post_question(
                        title = TITLE_TEMPLATE % user.id,
                        body_text = CONTENT_TEMPLATE,
                        tags = tags,
                    )
            self.print_if_verbose("Created Question '%s' with tags: '%s'" % (
                                                active_question.thread.title, tags,)
                                            )
        return active_question


    def create_answers(self, users, active_question):
        "Create the answers for the active question, return the active answer"
        active_answer = None
        last_vote = False
        # Now, fill the last added question with answers
        for user in users[:NUM_ANSWERS]:
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
                        body_text = ANSWER_TEMPLATE,
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

        for user in users[:NUM_COMMENTS]:
            active_question_comment = user.post_comment(
                                    parent_post = active_question,
                                    body_text = COMMENT_TEMPLATE
                                )
            self.print_if_verbose("%s posted a question comment"%user.username)
            active_answer_comment = user.post_comment(
                                    parent_post = active_answer,
                                    body_text = COMMENT_TEMPLATE
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


    def handle_noargs(self, **options):
        self.verbosity = int(options.get("verbosity", 1))
        self.interactive = options.get("interactive")

        if self.interactive:
            answer = choice_dialog("This command will DELETE ALL DATA in the current database, and will fill the database with test data. Are you absolutely sure you want to proceed?",
                            choices = ("yes", "no", ))
            if answer != "yes":
                return



        # Create Users
        users = self.create_users()

        # Create Questions, vote for questions
        active_question = self.create_questions(users)

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
                            body_text = CONTENT_TEMPLATE,
                            revision_comment = "EDITED",
                            force = True
                        )
        self.print_if_verbose("User has edited the active question")

        active_answer.author.edit_answer(
                            answer = active_answer,
                            body_text = COMMENT_TEMPLATE,
                            force = True
                        )
        self.print_if_verbose("User has edited the active answer")

        active_answer_comment.author.edit_comment(
                            comment_post = active_answer_comment,
                            body_text = ANSWER_TEMPLATE
                        )
        self.print_if_verbose("User has edited the active answer comment")

        active_question_comment.author.edit_comment(
                            comment_post = active_question_comment,
                            body_text = ANSWER_TEMPLATE
                        )
        self.print_if_verbose("User has edited the active question comment")

        # Accept best answer
        active_question.author.accept_best_answer(
                            answer = active_answer,
                            force = True,
                        )
        self.print_if_verbose("User has accepted a best answer")

        self.print_if_verbose("DONE")
