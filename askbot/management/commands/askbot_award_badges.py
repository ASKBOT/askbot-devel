"""WARNING:
This command is incomplete, current awards only
Civic Duty badge
"""

from askbot.models import badges
from askbot.models import User
from askbot.models import Vote
from askbot.utils.console import ProgressBar
import datetime
from django.core.management.base import NoArgsCommand

class Command(NoArgsCommand):
    def handle_noargs(self, *args, **kwargs):
        now = datetime.datetime.now()
        awarded_count = 0

        users = User.objects.all()
        count = users.count()
        message = 'Awarding badges for each user'
        for user in ProgressBar(users.iterator(), count, message):
            try:
                #get last vote
                vote = Vote.objects.filter(user=user).order_by('-id')[0]
            except IndexError:
                #user did not vote
                continue
            else:
                cd = badges.CivicDuty()
                awarded = cd.consider_award(
                            actor=user,
                            context_object=vote.voted_post,
                            timestamp=now
                        )
                awarded_count += int(awarded)

        print 'Awarded %d badges' % awarded_count
