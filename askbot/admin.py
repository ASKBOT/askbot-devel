"""
:synopsis: connector to standard Django admin interface

To make more models accessible in the Django admin interface, add more classes subclassing ``django.contrib.admin.Model``

Names of the classes must be like `SomeModelAdmin`, where `SomeModel` must
exactly match name of the model used in the project
"""
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext as _
from askbot import models
from askbot.const import TAG_EMAIL_FILTER_FULL_STRATEGY_CHOICES
from askbot.models.user_profile import USER_PROFILE_PROPERTIES


class PostAdmin(admin.ModelAdmin):
    date_hierarchy = 'added_at'
    list_display = ('author', 'post_type', 'added_at')
    list_filter = ('added_at', 'post_type')
    ordering = ('-added_at',)
    fieldsets = (
        (None, {
            'fields': (
                ('author', 'post_type', 'added_at'),
                ('old_question_id', 'old_answer_id', 'old_comment_id'),
                ('parent', 'thread', 'current_revision'),
                ('endorsed', 'endorsed_by', 'endorsed_at'),
                'approved',
                ('deleted', 'deleted_at', 'deleted_by'),
                ('wiki', 'wikified_at'),
                ('locked', 'locked_by', 'locked_at'),
                ('points', 'vote_up_count', 'vote_down_count'),
                'comment_count',
                'offensive_flag_count',
                ('last_edited_at', 'last_edited_by'),
                'language_code',
                ('html', 'text'),
                'summary',
                'is_anonymous',
            )
        }),
    )


class AnonymousQuestionAdmin(admin.ModelAdmin):
    """AnonymousQuestion admin class"""


class TagAdmin(admin.ModelAdmin):
    """Tag admin class"""


class VoteAdmin(admin.ModelAdmin):
    date_hierarchy = 'voted_at'
    list_display = ('user', 'vote', 'voted_post', 'voted_at')
    list_filter = ('voted_at', 'vote')
    ordering = ('-voted_at',)
    fieldsets = (
        (None, {
            'fields': (
                ('user', 'voted_post'),
                ('vote', 'voted_at'),
            )
        }),
    )


class FavoriteQuestionInline(admin.TabularInline):
    model = models.FavoriteQuestion


class ThreadAdmin(admin.ModelAdmin):
    date_hierarchy = 'added_at'
    list_display = ('title', 'added_at', 'last_activity_at', 'closed',
                    'deleted', 'approved')
    list_filter = ('added_at', 'last_activity_at', 'closed', 'deleted',
                   'approved')
    ordering = ('-added_at',)
    inlines = (FavoriteQuestionInline,)
    fieldsets = (
        (None, {
            'fields': (
                ('title', 'points'),
                'tags',
                ('followed_by'),
                ('closed', 'closed_by', 'closed_at', 'close_reason'),
                'deleted',
                ('approved', 'accepted_answer'),
            )
        }),
        (_("Question"), {
            'fields': (
                ('language_code', 'tagnames'),
                ('view_count', 'favourite_count', 'answer_count'),
                ('last_activity_by', 'last_activity_at'),
            )
        }),
    )


class ThreadToGroupAdmin(admin.ModelAdmin):
    list_display = ('thread', 'group', 'visibility')
    list_filter = ('visibility',)
    ordering = ('-thread',)
    fieldsets = (
        (None, {
            'fields': (
                ('thread', 'group', 'visibility'),
            )
        }),
    )


class QuestionViewAdmin(admin.ModelAdmin):
    date_hierarchy = 'when'
    list_display = ('who', 'question', 'when',)
    list_filter = ('when',)
    ordering = ('-when',)
    fieldsets = (
        (None, {
            'fields': (
                ('who', 'question', 'when'),
            )
        }),
    )


class FavoriteQuestionAdmin(admin.ModelAdmin):
    date_hierarchy = 'added_at'
    list_display = ('user', 'thread', 'added_at')
    list_filter = ('added_at',)
    ordering = ('-added_at',)
    fieldsets = (
        (None, {
            'fields': (
                ('user', 'thread', 'added_at'),
            )
        }),
    )


class PostRevisionAdmin(admin.ModelAdmin):
    date_hierarchy = 'revised_at'
    list_display = ('post', 'author', 'revised_at')
    list_filter = ('revised_at', 'approved', 'is_anonymous')
    ordering = ('-revised_at',)
    fieldsets = (
        (None, {
            'fields': (
                ('post', 'revision', 'author', 'revised_at'),
                ('summary', 'text'),
                ('approved', 'approved_by', 'approved_at'),
                ('by_email', 'email_address'),
            )
        }),
        (_("Specific to question"), {
            'fields': (
                'title',
                'tagnames',
                'is_anonymous',
                'ip_addr',
            )
        }),
    )


class AwardAdmin(admin.ModelAdmin):
    date_hierarchy = 'awarded_at'
    list_display = ('user', 'badge', 'awarded_at')
    list_filter = ('awarded_at', 'notified')
    ordering = ('-awarded_at',)
    fieldsets = (
        (None, {
            'fields': (
                ('user', 'badge', 'awarded_at'),
                ('content_type', 'object_id'),
                'notified',
            )
        }),
    )


class ReputeAdmin(admin.ModelAdmin):
    date_hierarchy = 'reputed_at'
    list_display = ('user', 'reputation')
    list_filter = ('reputed_at',)
    ordering = ('-reputed_at',)
    fieldsets = (
        (None, {
            'fields': (
                ('user', 'reputation', 'reputation_type', 'reputed_at'),
                ('positive', 'negative'),
                ('question', 'language_code'),
                'comment',
            )
        }),
    )


class ActivityAdmin(admin.ModelAdmin):
    date_hierarchy = 'active_at'
    list_display = ('user', 'activity_type', 'active_at')
    list_filter = ('active_at', 'activity_type')
    ordering = ('-active_at',)
    fieldsets = (
        (None, {
            'fields': (
                ('user', 'activity_type', 'active_at'),
                ('content_type', 'object_id'),
                ('question', 'is_auditted'),
                'summary',
            )
        }),
    )


class ReplyAddressAdmin(admin.ModelAdmin):
    date_hierarchy = 'used_at'
    list_display = ('user', 'reply_action',)
    list_filter = ('used_at', 'reply_action',)
    ordering = ('-used_at',)
    fieldsets = (
        (None, {
            'fields': (
                ('address', 'allowed_from_email'),
                ('user', 'post'),
                ('reply_action', 'response_post'),
            )
        }),
    )


class BadgeDataAdmin(admin.ModelAdmin):
    list_display = ('slug', 'awarded_count')
    ordering = ('-awarded_count',)
    fieldsets = (
        (None, {
            'fields': (
                'slug',
                'awarded_count',
                'display_order',
            )
        }),
    )


class IsPersonal(SimpleListFilter):
    title = 'is personal group'
    parameter_name = 'is_personal'

    def lookups(self, request, model_admin):
        return (('1', 'Yes'), ('0', 'No'))

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(name__contains=models.user.PERSONAL_GROUP_NAME_PREFIX)
        elif self.value() == '0':
            return queryset.exclude(name__contains=models.user.PERSONAL_GROUP_NAME_PREFIX)
        else:
            return queryset


class GroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'logo_url', 'description', 'moderate_email', 'openness', 'read_only')
    list_display_links = ('id', 'name')
    list_filter = (IsPersonal, 'moderate_email', 'openness', 'read_only')
    search_fields = ('name', 'logo_url')


class EmailFeedSettingAdmin(admin.ModelAdmin):
    search_fields = ('subscriber__username', )


def profile_owner(obj):
    try:
        user = models.User.objects.filter(askbot_profile=obj)[0]
        return f'{user.username} ({user.email})'
    except Exception: #pylint: disable=broad-except
        return 'Unknown'


class UserProfileAdmin(admin.ModelAdmin):
    model = models.user_profile.UserProfile
    search_fields = ('auth_user_ptr__username', 'auth_user_ptr__email')
    list_display = (profile_owner, 'email_is_confidential')
    list_filter = ('email_is_confidential', 'status')
    fieldsets = (
        (None, {
            'fields': (
                ('email_is_confidential'),
                ('email_isvalid'),
                ('status',),
                ('is_fake',),
                ('last_seen'),
            )
        }),
    )


admin.site.register(models.BadgeData, BadgeDataAdmin)
admin.site.register(models.Group, GroupAdmin)
admin.site.register(models.Post, PostAdmin)
admin.site.register(models.Tag, TagAdmin)
admin.site.register(models.Vote, VoteAdmin)
admin.site.register(models.FavoriteQuestion, FavoriteQuestionAdmin)
admin.site.register(models.PostRevision, PostRevisionAdmin)
admin.site.register(models.Award, AwardAdmin)
admin.site.register(models.Repute, ReputeAdmin)
admin.site.register(models.Activity, ActivityAdmin)
admin.site.register(models.BulkTagSubscription)
admin.site.register(models.Thread, ThreadAdmin)
admin.site.register(models.question.ThreadToGroup, ThreadToGroupAdmin)
admin.site.register(models.QuestionView, QuestionViewAdmin)
admin.site.register(models.ReplyAddress, ReplyAddressAdmin)
admin.site.register(models.EmailFeedSetting, EmailFeedSettingAdmin)
admin.site.register(models.user_profile.UserProfile, UserProfileAdmin)


class MarkedTagInlineAdmin(admin.TabularInline):
    model = models.MarkedTag

UserAdmin.readonly_fields = USER_PROFILE_PROPERTIES
UserAdmin.fieldsets = UserAdmin.fieldsets + (('User Profile', {'fields': tuple(USER_PROFILE_PROPERTIES)}), )
UserAdmin.inlines = [MarkedTagInlineAdmin]


def user_admin_email_tag_filter_strategy(self, instance):
    return dict(TAG_EMAIL_FILTER_FULL_STRATEGY_CHOICES)[instance.email_tag_filter_strategy]


UserAdmin.email_tag_filter_strategy = user_admin_email_tag_filter_strategy
