from django.core.management.base import NoArgsCommand
from askbot.utils.console import ProgressBar
from askbot.models import Activity
from askbot import const

class Command(NoArgsCommand):
    def handle_noargs(self, **options):
        act_type = const.TYPE_ACTIVITY_PRIZE
        acts = Activity.objects.filter(activity_type = act_type)
        deleted_count = 0
        message = "Searching for context-less award activity objects:"
        for act in ProgressBar(acts.iterator(), acts.count(), message):
            if act.content_object == None:
                act.delete()
                deleted_count += 1
        if deleted_count:
            print "%d activity objects deleted" % deleted_count
        else:
            print "None found"
