from askbot.utils.mail import send_mail
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email

class Command(BaseCommand):
    args = '<recipients email>'
    help = 'Sends a test email to the specified email address'

    def handle(self, *args, **options):

        if len(args) != 1:
            raise CommandError('Recipients email address required')

        try:
            validate_email(args[0])
        except ValidationError:
            raise CommandError('%s is not a valid email address' % (args[0]))

        send_mail(
            subject_line = 'Askbot Mail Test',
            body_text = 'Askbot Mail Test',
            recipient_list = [args[0]],
        )
