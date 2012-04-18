from django.core.management.base import NoArgsCommand
from django.core import management
import os
import askbot
from optparse import make_option
from askbot.utils.console import choice_dialog


# FULL PATH HERE
# DEFAULTS TO askbot_path/tests/test_data.json
FIXTURE_NAME = os.path.join(os.path.dirname(askbot.__file__),
                                "tests", "test_data.json")

# The data from these apps gets auto-populated on signals, saves and updates
# We have to exclude it otherwise we get Constraint errors
EXCLUDE_APPS = ['contenttypes',
                'sites',
                'askbot.activity',
                'askbot.activityauditstatus',
                'askbot.badgedata',
                'askbot.EmailFeedSetting',
                'auth.Message']


class Command(NoArgsCommand):
    """
    Flushes the database, fills it with test data, dumps a fixture and then
    flushes the database again.
    """

    option_list = NoArgsCommand.option_list + (
        make_option('--noinput', action='store_false', dest='interactive', default=True,
            help='Do not prompt the user for input of any kind.'),
    )

    def print_if_verbose(self, text):
        "Only print if user chooses verbose output"
        if self.verbosity > 0:
            print text


    def handle_noargs(self, **options):
        self.verbosity = int(options.get("verbosity", 1))
        self.interactive = options.get("interactive")

        if self.interactive:
            answer = choice_dialog("This command will DELETE ALL DATA in the current database, fill the database with test data and flush the test data. Are you absolutely sure you want to proceed?",
                            choices = ("yes", "no", ))
            if answer != "yes":
                return

        # First, flush the data
        self.print_if_verbose("FLUSHING THE DATABASE")
        management.call_command('flush', verbosity=0, interactive=False)

        # Then, fill the database with test content
        self.print_if_verbose("FILLING THE DB WITH TEST CONTENT")
        management.call_command('askbot_add_test_content', verbosity=0,
                                                        interactive=False)

        # At last, dump the data into a fixture
        # Create a file object ready for writing
        self.print_if_verbose("DUMPING THE DATA IN FILE '%s'" % FIXTURE_NAME)
        fixture = open(FIXTURE_NAME, 'wb')
        management.call_command('dumpdata', stdout = fixture,
                            exclude = EXCLUDE_APPS, indent = 4, natural = True)
        fixture.close()

        # FLUSH AGAIN
        self.print_if_verbose("FLUSHING THE DATABASE")
        management.call_command('flush', verbosity=0, interactive=False)

        self.print_if_verbose("You can load this data now by invoking ./manage.py %s" % FIXTURE_NAME)


