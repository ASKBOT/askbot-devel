from django.core.management.base import NoArgsCommand
from django.contrib.auth.models import User
from django.db import transaction
from askbot.utils.console import print_action

class Command(NoArgsCommand):
    help = 'updates data about currently used avatars, ' + \
        'necessary for display of avatars on the front page'

    @transaction.commit_manually
    def handle_noargs(self, **options):
        users = User.objects.all()
        has_avatar = User.objects.exclude(avatar_type='n').count()
        total_users = users.count()
        print '%s users in total, %s have valid avatar' \
           % (total_users, has_avatar)

        for count, user in enumerate(users):
            users_left = total_users - count
            print_action(
                'Updating %s (%d users left)' % (user.username, users_left)
            )
            user.update_avatar_type()
            transaction.commit()

        print 'Updated all the users'
        has_avatar = User.objects.exclude(avatar_type='n').count()
        transaction.commit()
        print '%s users in total, %s have valid avatar' \
            % (total_users, has_avatar)
