"""management command that
creates the askbot user account programmatically
the command can add password, but it will not create
associations with any of the federated login providers
"""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings as django_settings
from django.utils import translation
from askbot import models, forms

STATUS_INFO =  "'a' - approved, 'w' - watched, 'd' - admin, 'm' - moderator, " \
               "'b' and 's' - blocked and suspended, respectively"

class Command(BaseCommand):
    "The command class itself"

    help = """
    """
    def add_arguments(self, parser):
        parser.add_argument('--user-name',
            action='store',
            type=str,
            dest='username',
            default=None,
            help='user name **required**, same as screen '
                    'name and django user name'
        )
        parser.add_argument('--password',
            action='store',
            type=str,
            dest='password',
            default=None,
            help='cleartext password. If not given, an unusable '
                    'password will be set.'
        )
        parser.add_argument('--email',
            action='store',
            type=str,
            dest='email',
            default=None,
            help='email address - **required**'
        )
        parser.add_argument('--status',
            action='store',
            type=str,
            dest='status',
            default='a',
            help="Set user status. Options: %s" % STATUS_INFO
        )
        parser.add_argument('--frequency',
            action='store',
            type=str,
            dest='frequency',
            default='n',
            help="Set user's update frequency.i Options: i,d,w,n; see askbot.models.user.UPDATE_FREQUENCY"
        )

    def handle(self, *args, **options):
        """create an askbot user account, given email address,
        user name, (optionally) password
        and (also optionally) - the
        default email delivery schedule
        """
        translation.activate(django_settings.LANGUAGE_CODE)

        if options['email'] is None:
            raise CommandError('the --email argument is required')
        if options['username'] is None:
            raise CommandError('the --user-name argument is required')

        password = options['password']
        email = options['email']
        username = options['username']
        status = options['status']
        if status not in 'wamdsb':
            raise CommandError(
                        f'Illegal value of --status {status}. Allowed user statuses are: {STATUS_INFO}'
                    )

        user = models.User.objects.create_user(username, email)
        user.set_status(options['status'])

        if password:
            user.set_password(password)

        subscription = {'subscribe': 'y'}
        email_feeds_form = forms.SimpleEmailSubscribeForm(subscription)
        if email_feeds_form.is_valid():
            email_feeds_form.save(user)
        else:
            raise CommandError('\n'.join(email_feeds_form.errors))

        user.save()
