from __future__ import print_function
import datetime

from askbot.models import badges
from askbot.models import Award
from askbot.conf import settings as askbot_settings
from askbot.utils.console import ProgressBar
from django.core.management.base import NoArgsCommand
from django.utils import timezone

class Command(NoArgsCommand):
    def handle_noargs(self, *args, **kwargs):
        help = 'expires RapidResponder badges'

        expire_date = timezone.now() - datetime.timedelta(askbot_settings.RAPID_RESPONDER_BADGE_EXPIRES)
        awards = Award.objects.filter(badge__slug = badges.RapidResponder.key, awarded_at__lte = expire_date)

        expired_count = 0
        for award in ProgressBar(awards.iterator(), awards.count(), 'Expiring RapidResponder Badges'):
            award.delete()
            expired_count += 1

        print('Expired %d RapidResponder badges' % expired_count)
