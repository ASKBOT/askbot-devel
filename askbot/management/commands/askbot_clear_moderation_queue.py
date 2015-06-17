from django.core.management.base import NoArgsCommand
from askbot import const
from askbot.models import Activity

ACTIVITY_TYPES = (
    const.TYPE_ACTIVITY_MODERATED_NEW_POST,
    const.TYPE_ACTIVITY_MODERATED_POST_EDIT,
    const.TYPE_ACTIVITY_MARK_OFFENSIVE
)

class Command(NoArgsCommand):
    help = 'deletes all items from the moderation queue'
    def handle_noargs(self, *args, **kwargs):
        acts = Activity.objects.filter(activity_type__in=ACTIVITY_TYPES)
        acts.delete()
