from askbot.management.base import NoArgsJob
from askbot import models

def fix_inbox_counts(user):
    """a unit of job - returns True if change was made
    and False otherwise
    """
    old_new_count = user.new_response_count
    old_seen_count = user.seen_response_count

    user.update_response_counts()

    (changed1, changed2) = (False, False)
    if user.new_response_count != old_new_count:
        changed1 = True
    if user.seen_response_count != old_seen_count:
        changed2 = True

    return (changed1 or changed2)

class Command(NoArgsJob):
    """definition of the job that fixes response counts
    destined for the user inboxes
    """
    def __init__(self, *args, **kwargs):
        self.batches = ({
            'title': 'Checking inbox item counts for all users: ',
            'query_set': models.User.objects.all(),
            'function': fix_inbox_counts,
            'changed_count_message': 'Corrected records for %d users',
            'nothing_changed_message': 'No problems found'
        },)
        super().__init__(*args, **kwargs)
