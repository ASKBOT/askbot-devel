# pylint: disable=missing-docstring
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from askbot.models import GroupMembership

class Command(BaseCommand):

    def handle(self, *args, **kwargs): #pylint: disable=unused-argument
        #1) select distinct group ids from memberships
        print('Getting group ids assigned to Group Memberships')
        memb_group_ids = GroupMembership.objects.values_list('group_id', flat=True)
        #2) distinct group ids from groups
        print('Getting all group ids')
        group_ids = Group.objects.values_list('pk', flat=True)
        #3) calc the diff
        missing_group_ids = set(memb_group_ids) - set(group_ids)
        print(f'Found {len(missing_group_ids)} missing groups')
        bad_gms = GroupMembership.objects.filter(group_id__in=missing_group_ids)
        print('Deleting bad group memberships')
        bad_gms.delete()
        print('Done')
