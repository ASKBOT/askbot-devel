import sys
from django.core.management.base import NoArgsCommand
from django.db import transaction
from askbot import signals
from askbot.utils import console

class NoArgsJob(NoArgsCommand):
    """Base class for a job command -
    the one that runs the same operation on
    sets of items - each item operation in its own
    transaction and prints progress in % of items
    completed

    The subclass must implement __init__() method
    where self.batches data structure must be defined as follows
    (#the whole thing is a tuple
       {#batch is described by a dictionary
        'title': <string>,
        'query_set': <query set for the items>,
        'function': <function or callable that performs
                     an operation on a single item
                     and returns True if item was changed
                     False otherwise
                     item is given as argument
                     >,
        'items_changed_message': <string with one %d placeholder>,
        'nothing_changed_message': <string>
       },
       #more batch descriptions
    )
    """
    batches = ()

    def handle_noargs(self, **options):
        """handler function that removes all signal listeners
        then runs the job and finally restores the listerers
        """
        signal_data = signals.pop_all_db_signal_receivers()
        self.run_command(**options)
        signals.set_all_db_signal_receivers(signal_data)

    def run_command(self, **options):
        """runs the batches"""
        for batch in self.batches:
            self.run_batch(batch)

    @transaction.commit_manually
    def run_batch(self, batch):
        """runs the single batch
        prints batch title
        then loops through the query set
        and prints progress in %
        afterwards there will be a short summary
        """

        sys.stdout.write(batch['title'].encode('utf-8'))
        changed_count = 0
        checked_count = 0
        total_count = batch['query_set'].count()

        if total_count == 0:
            transaction.commit()
            return

        for item in batch['query_set'].all():

            item_changed = batch['function'](item)
            transaction.commit()

            if item_changed:
                changed_count += 1
            checked_count += 1

            progress = 100*float(checked_count)/float(total_count)
            console.print_progress(checked_count, total_count)
        console.print_progress(checked_count, total_count)

        if changed_count:
            print batch['changed_count_message'] % changed_count
        else:
            print batch['nothing_changed_message']
