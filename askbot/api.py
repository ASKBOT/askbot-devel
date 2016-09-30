"""place for the API calls into askbot
at this point most of the useful functions are still
in the askbot.models module, but
api must become a place to manupulate the data in the askbot application
so that other implementations of the data storage could be possible
"""
from django.db.models import Q
from askbot import models
from askbot import const


def get_info_on_moderation_items(user):
    """returns a dictionary with
    counts of new and seen moderation items for a given user
    if user is not a moderator or admin, returns None
    """
    if user.is_anonymous():
        return None
    if not(user.is_moderator() or user.is_administrator()):
        return None

    content_types = (
        const.TYPE_ACTIVITY_MARK_OFFENSIVE,
        const.TYPE_ACTIVITY_MODERATED_NEW_POST,
        const.TYPE_ACTIVITY_MODERATED_POST_EDIT,
    )

    messages = models.ActivityAuditStatus.objects.filter(
        activity__activity_type__in=content_types, user=user)

    seen_count = messages.filter(
        status=models.ActivityAuditStatus.STATUS_SEEN).count()
    new_count = messages.filter(
        status=models.ActivityAuditStatus.STATUS_NEW).count()
    return {
        'seen_count': seen_count,
        'new_count': new_count
    }


def get_admin(seed_user_id=None):
    """returns user objects with id == seed_user_id
    if the user with that id is not an administrator,
    the function will try to find another admin or moderator
    who has the smallest user id

    if the user is not found, or there are no moderators/admins
    User.DoesNotExist will be raised

    The reason this function is here and not on a manager of
    the user object is because we still patch the django-auth User table
    and it's probably better not to patch the manager
    """
    if seed_user_id:
        user = models.User.objects.get(id=seed_user_id)  # let it raise error here
        if user.is_administrator() or user.is_moderator():
            return user
    try:
        return models.User.objects.filter(
            Q(is_superuser=True) | Q(askbot_profile__status__in=('m', 'd'))
        ).order_by('id')[0]
    except IndexError:
        raise models.User.DoesNotExist(
                """Please add a moderator or an administrator to the forum first
                there don't seem to be any"""
            )
