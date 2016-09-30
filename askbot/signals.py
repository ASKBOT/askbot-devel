"""Custom django signals defined for the askbot forum application.
"""
from collections import namedtuple

import django.dispatch

from django.db.models.signals import (pre_save, post_save,
                                      pre_delete, post_delete, post_syncdb)

try:
    from django.db.models.signals import m2m_changed
except ImportError:
    pass


GenericSignal = namedtuple(
    'GenericSignal', field_names=['signal', 'callback', 'dispatch_uid'])


tags_updated = django.dispatch.Signal(
    providing_args=['tags', 'user', 'timestamp'])

after_post_removed = django.dispatch.Signal(
    providing_args=['instance', 'deleted_by'])

after_post_restored = django.dispatch.Signal(
    providing_args=['instance', 'restored_by'])

flag_offensive = django.dispatch.Signal(providing_args=['instance', 'mark_by'])
remove_flag_offensive = django.dispatch.Signal(providing_args=['instance', 'mark_by'])
user_updated = django.dispatch.Signal(providing_args=['instance', 'updated_by'])
user_registered = django.dispatch.Signal(providing_args=['user'])

# TODO: move this to authentication app
user_logged_in = django.dispatch.Signal(providing_args=['session'])

new_answer_posted = django.dispatch.Signal(
    providing_args=['answer', 'user', 'form_data'])
new_question_posted = django.dispatch.Signal(
    providing_args=['question', 'user', 'form_data'])
new_comment_posted = django.dispatch.Signal(
    providing_args=['comment', 'user', 'form_data'])
answer_edited = django.dispatch.Signal(
    providing_args=['answer', 'user', 'form_data'])
question_visited = django.dispatch.Signal(
    providing_args=['request', 'question'])

post_updated = django.dispatch.Signal(
    providing_args=['post', 'updated_by', 'newly_mentioned_users'])

post_revision_published = django.dispatch.Signal(
    providing_args = ['revision', 'was_approved' ])

spam_rejected = django.dispatch.Signal(
    providing_args = ['text', 'spam', 'user', 'ip_addr' ])

site_visited = django.dispatch.Signal(providing_args=['user', 'timestamp'])
reputation_received = django.dispatch.Signal(providing_args=['user', 'reputation_before'])


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
        # django signals
        pre_save,
        post_save,
        pre_delete,
        post_delete,
        post_syncdb,
        question_visited,
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
    for (signal, receivers) in receiver_data.items():
        signal.receivers = receivers
