"""A management command that creates groups for each email domain in the database."""
from django.core.management.base import BaseCommand
from askbot.conf import settings
from askbot.models import User
from askbot.models.analytics import get_organization_domains
from askbot.models.user import get_organization_name_from_domain
from askbot.utils.console import ProgressBar

class Command(BaseCommand): # pylint: disable=missing-docstring
    help = 'Create groups for each email domain in the database.'

    def handle(self, *args, **options): # pylint: disable=missing-docstring, unused-argument
        """Obtains a list of unique email domains names.
        Creates a group for each domain name, if such group does not exist.
        Group visibility is set to the value of settings.PER_EMAIL_DOMAIN_GROUP_DEFAULT_VISIBILITY.
        """
        domains = get_organization_domains()
        count = len(domains)
        message = 'Initializing groups by the email address domain names'
        for domain in ProgressBar(domains, count, message):
            organization_name = get_organization_name_from_domain(domain)
            group = User.objects.get_or_create_group(
                organization_name,
                visibility=settings.PER_EMAIL_DOMAIN_GROUP_DEFAULT_VISIBILITY
            )
            print('Group {0} created.'.format(group.name))

