from askbot.conf import settings as askbot_settings
from askbot.conf import gravatar_enabled
from askbot.models import User, user_can_see_karma
from askbot.utils.forms import get_error_list
from avatar.conf import settings as avatar_settings
from avatar.forms import PrimaryAvatarForm, UploadAvatarForm
from avatar.models import Avatar
from avatar.signals import avatar_updated
from django.conf import settings as django_settings
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.encoding import force_str
from django.utils.translation import gettext as _
import functools


def admin_or_owner_required(func):
    """decorator that allows admin or account owner to
    call the view function"""
    @functools.wraps(func)
    def wrapped(request, user_id=None):
        if not request.user.is_authenticated:
            return login_required(func)(request, user_id)

        # Convert user_id to int for proper comparison (URL params are strings)
        try:
            user_id_int = int(user_id) if user_id is not None else None
        except (ValueError, TypeError):
            return HttpResponseForbidden("Invalid user ID")

        if request.user.is_administrator() or request.user.id == user_id_int:
            return func(request, user_id)

        return HttpResponseForbidden("Access denied")
    return wrapped


def get_avatar_data(user, avatar_size):
    """avatar data and boolean, which is true is user has custom avatar
    avatar data is a list of dictionaries, one for each avatar with keys:
    * id - avatar id (this field is missing for gravatar and default avatar)
    * avatar_type (string , 'uploaded_avatar', 'gravatar', 'default_avatar')
    * url (url to avatar of requested size)
    * is_primary (True if primary)
    Primary avatar data must be first in the list.
    There will always be only one primary_avatar.
    List includes gravatar, default avatar and any uploaded avatars.
    """
    avatar_type = user.get_avatar_type()

    #determine avatar data for the view
    avatar_data = list()

    if 'avatar' in django_settings.INSTALLED_APPS:
        avatars = user.avatar_set.all()
        #iterate through uploaded avatars
        for avatar in avatars:
            datum = {
                'id': avatar.id,
                'avatar_type': 'uploaded_avatar',
                'url': avatar.avatar_url(avatar_size),
                #avatar app always keeps one avatar as primary
                #but we may want to allow user select gravatar
                #and/or default fallback avatar!!!
                'is_primary': avatar.primary and avatar_type == 'a'
            }
            avatar_data.append(datum)

    if gravatar_enabled():
        #add gravatar datum
        gravatar_datum = {
            'avatar_type': 'gravatar',
            'url': user.get_gravatar_url(avatar_size),
            'is_primary': (avatar_type == 'g')
        }
        avatar_data.append(gravatar_datum)

    #add default avatar datum
    default_datum = {
        'avatar_type': 'default_avatar',
        'url': user.get_default_avatar_url(avatar_size),
        'is_primary': (avatar_type == 'n')
    }
    avatar_data.append(default_datum)

    #if there are >1 primary avatar, select just one
    primary_avatars = [v for v in avatar_data if v['is_primary']]
    if len(primary_avatars) > 1:
        def clear_primary(datum):
            datum['is_primary'] = False
        list(map(clear_primary, primary_avatars))
        primary_avatars[0]['is_primary'] = True

    #insert primary avatar first
    primary_avatars = [v for v in avatar_data if v['is_primary']]
    if len(primary_avatars):
        primary_avatar = primary_avatars[0]
        avatar_data.remove(primary_avatar)
        avatar_data.insert(0, primary_avatar)

    can_upload = avatars.count() < avatar_settings.AVATAR_MAX_AVATARS_PER_USER
    return avatar_data, bool(avatars.count()), can_upload


def redirect_to_show_list(user_id):
    return HttpResponseRedirect(
        reverse('askbot_avatar_show_list', kwargs={'user_id': user_id})
    )


@admin_or_owner_required
def show_list(request, user_id=None, extra_context=None, avatar_size=128):
    """lists user's avatars, including gravatar and the default avatar"""
    user = get_object_or_404(User, pk=user_id)
    avatar_data, has_uploaded_avatar, can_upload = get_avatar_data(user, avatar_size)
    status_message = request.session.pop('askbot_avatar_status_message', None)

    if not isinstance(status_message, str):
        #work around bug where this was accidentally encoded into str
        #and stored into session - we lose this message
        #delete this branch some time in 2017
        status_message = ''

    context = {
        #these are user profile context vars
        'can_show_karma': user_can_see_karma(request.user, user),
        'user_follow_feature_on': ('followit' in django_settings.INSTALLED_APPS),
        #below are pure avatar view context vars
        'avatar_data': avatar_data,
        'has_uploaded_avatar': has_uploaded_avatar,
        'can_upload': can_upload,
        'upload_avatar_form': UploadAvatarForm(user=user),
        'status_message': status_message,
        'view_user': user
    }
    context.update(extra_context or {})
    return render(request, 'avatar/show_list.html', context)

@admin_or_owner_required
def set_primary(request, user_id=None, extra_context=None, avatar_size=128):
    """changes default uploaded avatar"""
    user = get_object_or_404(User, pk=user_id)

    if request.method == "POST":
        updated = False
        form = PrimaryAvatarForm(
                        request.POST,
                        user=user,
                        avatars=user.avatar_set.all()
                    )
        if 'choice' in request.POST and form.is_valid():
            avatar = Avatar.objects.get(id=form.cleaned_data['choice'])
            avatar.primary = True
            avatar.save()
            avatar_updated.send(sender=Avatar, user=request.user, avatar=avatar)
            user.avatar_type = 'a'
            user.clear_avatar_urls()
            user.save()
            from askbot.models.recent_contributors import AvatarsBlockData
            AvatarsBlockData.update_user(user)

    return redirect_to_show_list(user_id)


@admin_or_owner_required
def upload(request, user_id=None):
    user = get_object_or_404(User, pk=user_id)
    if request.method == 'POST':
        if 'avatar' in request.FILES:
            form = UploadAvatarForm(
                            request.POST,
                            request.FILES,
                            user=user)
            if form.is_valid():
                avatar = Avatar(user=user, primary=True)
                image_file = request.FILES['avatar']
                avatar.avatar.save(image_file.name, image_file)
                avatar.save()
                sizes = avatar_settings.AVATAR_AUTO_GENERATE_SIZES
                for size in sizes:
                    avatar.create_thumbnail(size)
                avatar_updated.send(sender=Avatar, user=user, avatar=avatar)
                user.avatar_type = 'a'
                user.clear_avatar_urls()
                user.save()
                message = _('Avatar uploaded and set as primary')
            else:
                errors = get_error_list(form)
                message = ', '.join([force_str(v) for v in errors])
        else:
            message = _('Please choose file to upload')

        request.session['askbot_avatar_status_message'] = message

    return redirect_to_show_list(user_id)


def delete(request, avatar_id):
    """deletes uploded avatar"""
    avatar = get_object_or_404(Avatar, pk=avatar_id)
    if request.method == 'POST' \
        and request.user.is_authenticated \
        and (request.user.is_administrator_or_moderator() \
            or avatar.user_id == request.user.id):
        user = avatar.user
        avatar.delete()
        if user.avatar_set.count() == 0:
            if user.avatar_type == 'a':
                user.avatar_type = 'n'
        elif user.avatar_type != 'a':
            user.avatar_set.update(primary=False)
        user.clear_avatar_urls()
        user.save()
        from askbot.models.recent_contributors import AvatarsBlockData
        AvatarsBlockData.update_user(user)

    return redirect_to_show_list(user.id)


@admin_or_owner_required
def enable_gravatar(request, user_id=None):
    if request.method == 'POST':
        user = get_object_or_404(User, pk=user_id)
        user.avatar_type = 'g'
        user.avatar_set.update(primary=False)
        user.clear_avatar_urls()
        user.save()
    return redirect_to_show_list(user_id)


@admin_or_owner_required
def enable_default_avatar(request, user_id=None):
    if request.method == 'POST':
        user = get_object_or_404(User, pk=user_id)
        user.avatar_type = 'n'
        user.avatar_set.update(primary=False)
        user.clear_avatar_urls()
        user.save()
    return redirect_to_show_list(user_id)


@admin_or_owner_required
def disable_gravatar(request, user_id=None):
    if request.method == 'POST':
        user = get_object_or_404(User, pk=user_id)
        user.avatar_type = 'a'
        if user.avatar_set.count():
            avatar = user.avatar_set.all()[0]
            avatar.primary = True
            avatar.save()
            avatar_updated.send(sender=Avatar, user=request.user, avatar=avatar)
        user.clear_avatar_urls()
        user.save()
    return redirect_to_show_list(user_id)
