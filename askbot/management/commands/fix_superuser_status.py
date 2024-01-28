from django.core.management import BaseCommand
from askbot.models import UserProfile


def rebuild_profile_caches(profiles):
    pks = profiles.values_list('pk', flat=True)
    profiles = UserProfile.objects.filter(pk__in=pks)
    for profile in profiles.iterator():
        profile.update_cache()


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        # Make sure all superusers have their status set to 'd'
        profiles = (UserProfile.objects
                 .filter(pk__is_superuser=True)
                 .exclude(status='d'))

        fixed = profiles.count()

        for profile in profiles:
            user = User.objects.get(id=profile.auth_user_ptr_id)
            user.set_status('d')

        rebuild_profile_caches(profiles)

        # Make sure all normal users have their status not set to 'd'
        profiles = (UserProfile.objects
                      .filter(status='d')
                      .exclude(pk__is_superuser=True))

        fixed += profiles.count()

        for profile in profiles:
            user = User.objects.get(id=profile.auth_user_ptr_id)
            user.set_status('a')

        rebuild_profile_caches(profiles)

        self.stdout.write(f'Fixed the status of {fixed} users.')
