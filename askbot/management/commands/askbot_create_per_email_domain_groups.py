"""A management command that creates groups for each email domain in the database."""
from django.core.management.base import BaseCommand
from askbot.conf import settings as askbot_settings
from askbot.models import Group, User
from askbot.models.analytics import get_unique_user_email_domains_qs
from askbot.models.user import get_organization_name_from_domain
from askbot.utils.console import ProgressBar

class Command(BaseCommand): # pylint: disable=missing-docstring
    help = 'Create groups for each email domain in the database.'

    def add_arguments(self, parser): # pylint: disable=missing-docstring
        parser.add_argument('--silent', action='store_true', help='Do not print progress messages.')

    def handle(self, *args, **options): # pylint: disable=missing-docstring, unused-argument
        """Obtains a list of unique email domains names.
        Creates a group for each domain name, if such group does not exist.
        Group visibility is set to the value of settings.PER_EMAIL_DOMAIN_GROUP_DEFAULT_VISIBILITY.
        """
        domains = get_unique_user_email_domains_qs()
        count = len(domains)
        message = 'Creating groups by the email address domain names'
        created_groups = []
        unchanged_groups = []
        done_lowercased_domains = []
        silent = options['silent']
        for domain in ProgressBar(domains.iterator(), count, message=message, silent=silent):

            domain_name = domain['domain'] or 'Unknown Organization'
            if domain_name.lower() in done_lowercased_domains:
                continue

            done_lowercased_domains.append(domain_name.lower())

            organization_name = get_organization_name_from_domain(domain_name)
            group, created = Group.objects.get_or_create(
                name=organization_name,
                visibility=askbot_settings.PER_EMAIL_DOMAIN_GROUP_DEFAULT_VISIBILITY,
                used_for_analytics=True
            )

            if not created:
                if not group.used_for_analytics:
                    group.used_for_analytics = True
                    group.save()

            users = User.objects.filter(email__iendswith='@' + domain_name)
            for user in users.iterator():
                user.join_group(group, force=True)

            if created:
                created_groups.append(group)
            else:
                unchanged_groups.append(group)
