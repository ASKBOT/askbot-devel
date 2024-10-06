"""Custom django signals defined for the askbot forum application.
"""
from collections import namedtuple

import django.dispatch

from django.db.models.signals import (pre_save, post_save,
                                      pre_delete, post_delete, post_migrate)

try:
    from django.db.models.signals import m2m_changed
except ImportError:
    pass


GenericSignal = namedtuple(
    'GenericSignal', field_names=['signal', 'callback', 'dispatch_uid'])


tags_updated = django.dispatch.Signal()

after_post_removed = django.dispatch.Signal()

after_post_restored = django.dispatch.Signal()

flag_offensive = django.dispatch.Signal()
remove_flag_offensive = django.dispatch.Signal()
user_updated = django.dispatch.Signal()
# TODO: move this to authentication app
user_registered = django.dispatch.Signal()
user_logged_in = django.dispatch.Signal()

new_answer_posted = django.dispatch.Signal()
new_question_posted = django.dispatch.Signal()
new_comment_posted = django.dispatch.Signal()
answer_edited = django.dispatch.Signal()
question_visited = django.dispatch.Signal()
voted = django.dispatch.Signal()

post_updated = django.dispatch.Signal()

post_revision_published = django.dispatch.Signal()

spam_rejected = django.dispatch.Signal()

site_visited = django.dispatch.Signal()
reputation_received = django.dispatch.Signal()
posts_marked_as_spam = django.dispatch.Signal()


def pop_signal_receivers(signal):
    """disables a given signal by removing listener functions
    and returns the list
    """
    receivers = signal.receivers
    signal.receivers = list()
    return receivers


def set_signal_receivers(signal, receiver_list):
    """assigns a value of the receiver_list
    to the signal receivers
    """
    signal.receivers = receiver_list


def pop_all_db_signal_receivers():
    """loops through all relevant signals
    pops their receivers and returns a
    dictionary where signals are keys
    and lists of receivers are values
    """
    # this is the only askbot signal that is not defined here
    # must use this to avoid a circular import
    from askbot.models.badges import award_badges_signal
    signals = (
        # askbot signals
        tags_updated,
        after_post_removed,
        after_post_restored,
        flag_offensive,
        remove_flag_offensive,
        user_updated,
        user_logged_in,
        user_registered,
        post_updated,
        award_badges_signal,
        posts_marked_as_spam,
        question_visited,
        voted,
        # django signals
        pre_save,
        post_save,
        pre_delete,
        post_delete,
        post_migrate,
    )
    if 'm2m_changed' in globals():
        signals += (m2m_changed, )

    receiver_data = dict()
    for signal in signals:
        receiver_data[signal] = pop_signal_receivers(signal)

    return receiver_data


def register_generic_signal(generic_signal, sender):
    generic_signal.signal.connect(
        receiver=generic_signal.callback,
        sender=sender,
        dispatch_uid=generic_signal.dispatch_uid
    )


def set_all_db_signal_receivers(receiver_data):
    """takes receiver data as an argument
    where the argument is as returned by the
    pop_all_db_signal_receivers() call
    and sets the receivers back to the signals
    """
    for (signal, receivers) in list(receiver_data.items()):
        signal.receivers = receivers
