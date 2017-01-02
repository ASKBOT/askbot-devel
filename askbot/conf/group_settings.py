"""Group settings"""
from django.utils.translation import ugettext_lazy as _
from askbot.conf.settings_wrapper import settings
from askbot.conf.super_groups import LOGIN_USERS_COMMUNICATION
from askbot.deps import livesettings

GROUP_SETTINGS = livesettings.ConfigurationGroup(
    'GROUP_SETTINGS',
    _('Group settings'),
    super_group=LOGIN_USERS_COMMUNICATION
)

settings.register(
    livesettings.BooleanValue(
        GROUP_SETTINGS,
        'GROUPS_ENABLED',
        default=False,
        description=_('Enable user groups'),
    )
)

# def group_name_update_callback(old_name, new_name):
#     from askbot.models.tag import clean_group_name
#     from askbot.models import Group
#     cleaned_new_name = clean_group_name(new_name.strip())
#
#     if new_name == '':
#         #name cannot be empty
#         return old_name
#
#     group = Group.objects.get_global_group()
#     group.name = cleaned_new_name
#     group.save()
#     return new_name


settings.register(
    livesettings.StringValue(
        GROUP_SETTINGS,
        'GLOBAL_GROUP_NAME',
        default=_('everyone'),
        description=_('Global user group name'),
        help_text=_('All users belong to this group automatically'),
        # update_callback=group_name_update_callback
    )
)

settings.register(
    livesettings.BooleanValue(
        GROUP_SETTINGS,
        'GROUP_EMAIL_ADDRESSES_ENABLED',
        default=False,
        description=_('Enable group email addresses'),
        help_text=_('If selected, users can post to groups by email '
                    '"group-name@domain.com"')
    )
)
