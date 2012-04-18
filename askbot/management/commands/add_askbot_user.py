"""management command that
creates the askbot user account programmatically
the command can add password, but it will not create
associations with any of the federated login providers
"""
from optparse import make_option
from django.core.management.base import BaseCommand, CommandError
from askbot import models, forms

class Command(BaseCommand):
    "The command class itself"

    help = """
    """
    option_list = BaseCommand.option_list + (
        make_option('--user-name',
            action = 'store',
            type = 'str',
            dest = 'username',
            default = None,
            help = 'user name **required**, same as screen '
                    'name and django user name'
        ),
        make_option('--password',
            action = 'store',
            type = 'str',
            dest = 'password',
            default = None,
            help = 'cleartext password. If not given, an unusable '
                    'password will be set.'
        ),
        make_option('--email',
            action = 'store',
            type = 'str',
            dest = 'email',
            default = None,
            help = 'email address - **required**'
        ),
        make_option('--email-frequency',
            action = 'store',
            type = 'str',
            dest = 'frequency',
            default = None,
            help = 'email subscription frequency (n - never, i - '
                    'instant, d - daily, w - weekly, default - w)'
        ),
    )

    def handle(self, *args, **options):
        """create an askbot user account, given email address,
        user name, (optionally) password 
        and (also optionally) - the
        default email delivery schedule
        """
        if options['email'] is None:
            raise CommandError('the --email argument is required')
        if options['username'] is None:
            raise CommandError('the --user-name argument is required')

        password = options['password']
        email = options['email']
        username = options['username']
        frequency = options['frequency']

        user = models.User.objects.create_user(username, email)
        if password:
            user.set_password(password)
            user.save()
        subscription = {'subscribe': 'y'}
        email_feeds_form = forms.SimpleEmailSubscribeForm(subscription)
        if email_feeds_form.is_valid():
            email_feeds_form.save(user)
        else:
            raise CommandError('\n'.join(email_feeds_form.errors))
