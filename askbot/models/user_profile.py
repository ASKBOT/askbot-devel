from askbot import const
from askbot.models.fields import LanguageCodeField
from django.conf import settings as django_settings
from django.core.cache import cache
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from jsonfield import JSONField
from django_countries.fields import CountryField

def get_profile_cache_key(user):
    if user.pk:
        return 'askbot-profile-{}'.format(user.pk)
    raise ValueError('auth.models.User is not saved, cant make cache key')


def get_localized_profile_cache_key(user, lang):
    if user.pk:
        data = {'pk': user.pk, 'lang': lang}
        return 'localized-askbot-profile-{pk}-{lang}'.format(**data)
    raise ValueError('auth.models.User is not saved, cant make cache key')


def get_profile_from_db(user):
    if user.pk:
        profile, junk = UserProfile.objects.get_or_create(auth_user_ptr=user)
        return profile
    raise ValueError('auth.models.User is not saved, cant make UserProfile')


def get_profile(user):
    key = get_profile_cache_key(user)
    profile = cache.get(key)
    if not profile:
        profile = get_profile_from_db(user)
        cache.set(key, profile)

    setattr(user, 'askbot_profile', profile)
    return profile


def user_profile_property(field_name):
    """returns property that will access Askbot UserProfile
    of auth_user by field name"""
    def getter(user):
        profile = get_profile(user)
        return getattr(profile, field_name)

    def setter(user, value):
        profile = get_profile(user)
        setattr(profile, field_name, value)
        UserProfile.objects.filter(pk=profile.pk).update(**{field_name: value})
        profile.update_cache()

    return property(getter, setter)


def add_profile_property(cls, name):
    prop = user_profile_property(name)
    cls.add_to_class(name, prop)


def add_profile_properties(cls):
    names = (
        'avatar_type',
        'avatar_urls',
        'bronze',
        'consecutive_days_visit_count',
        'country',
        'date_of_birth',
        'display_tag_filter_strategy',
        'email_isvalid',
        'email_key',
        'email_signature',
        'email_tag_filter_strategy',
        'gold',
        'gravatar',
        'ignored_tags',
        'interesting_tags',
        'is_fake',
        'languages',
        'last_seen',
        'location',
        'new_response_count',
        'primary_language',
        'real_name',
        'reputation',
        'seen_response_count',
        'show_country',
        'show_marked_tags',
        'silver',
        'social_sharing_mode',
        'status',
        'subscribed_tags',
        'twitter_access_token',
        'twitter_handle',
        'website',
    )
    for name in names:
        add_profile_property(cls, name)


class UserProfile(models.Model):
    #text_search_vector           | tsvector                 | 
    auth_user_ptr = models.OneToOneField(
                                User,
                                parent_link=True,
                                related_name='askbot_profile',
                                primary_key=True
                            )
    avatar_urls = JSONField(default={})
    status = models.CharField(
                            max_length=2,
                            default=const.DEFAULT_USER_STATUS,
                            choices=const.USER_STATUS_CHOICES,
                            db_index=True
                        )
    is_fake = models.BooleanField(default=False)
    email_isvalid = models.BooleanField(default=False)
    email_key = models.CharField(max_length=32, null=True)
    #hardcoded initial reputaion of 1, no setting for this one
    reputation = models.PositiveIntegerField(default=const.MIN_REPUTATION, db_index=True)
    gravatar = models.CharField(max_length=32)
    #has_custom_avatar = models.BooleanField(default=False)
    avatar_type = models.CharField(
            max_length=1,
            choices=const.AVATAR_TYPE_CHOICES,
            default='n' #for real set by the init_avatar_type based
            #on the livesetting value
        )
    gold = models.SmallIntegerField(default=0)
    silver = models.SmallIntegerField(default=0)
    bronze = models.SmallIntegerField(default=0)
    #todo: remove const.QUESTIONS_PER_PAGE_USER_CHOICES, no longer used!
    last_seen = models.DateTimeField(default=timezone.now)
    #todo: maybe remove
    real_name = models.CharField(max_length=100, blank=True)
    website = models.URLField(max_length=200, blank=True)
    #location field is actually city
    location = models.CharField(max_length=100, blank=True)
    country = CountryField(blank=True, null=True)
    show_country = models.BooleanField(default=False)
    date_of_birth = models.DateField(null=True, blank=True)
    #interesting tags and ignored tags are to store wildcard tag selections only
    interesting_tags = models.TextField(blank=True)
    ignored_tags = models.TextField(blank=True)
    subscribed_tags = models.TextField(blank=True)
    email_signature = models.TextField(blank=True)
    show_marked_tags = models.BooleanField(default=True)
    email_tag_filter_strategy = models.SmallIntegerField(
            choices=const.TAG_EMAIL_FILTER_FULL_STRATEGY_CHOICES,
            default=const.EXCLUDE_IGNORED
        )
    display_tag_filter_strategy = models.SmallIntegerField(
            choices=const.TAG_DISPLAY_FILTER_STRATEGY_CHOICES,
            default=const.INCLUDE_ALL
        )
    new_response_count = models.IntegerField(default=0)
    seen_response_count = models.IntegerField(default=0)
    consecutive_days_visit_count = models.IntegerField(default=0)
    #list of languages for which user should receive email alerts
    languages = models.CharField(
                            max_length=128,
                            default=django_settings.LANGUAGE_CODE
                        )
    primary_language = models.CharField(
                            max_length=16,
                            choices=django_settings.LANGUAGES,
                            default=django_settings.LANGUAGE_CODE
                        )

    twitter_access_token = models.CharField(max_length=256, default='')
    twitter_handle = models.CharField(max_length=32, default='')
    social_sharing_mode = models.IntegerField(
                                default=const.SHARE_NOTHING,
                                choices=const.SOCIAL_SHARING_MODE_CHOICES
                            )

    class Meta:
        app_label = 'askbot'

    def get_cache_key(self):
        return get_profile_cache_key(self.auth_user_ptr)

    def update_cache(self):
        key = self.get_cache_key()
        cache.set(key, self)

    def save(self, *args, **kwargs):
        self.update_cache()
        super(UserProfile, self).save(*args, **kwargs)


class LocalizedUserProfile(models.Model):
    auth_user = models.ForeignKey(User, related_name='localized_askbot_profiles')
    about = models.TextField(blank=True)
    language_code = LanguageCodeField(db_index=True)
    reputation = models.PositiveIntegerField(default=0, db_index=True)
    is_claimed = models.BooleanField(
                            default=False,
                            db_index=True,
                            help_text='True, if user selects this language'
                        )

    class Meta:
        app_label = 'askbot'

    def get_cache_key(self):
        return get_localized_profile_cache_key(self.auth_user, self.language_code)

    def get_reputation(self):
        return self.reputation + const.MIN_REPUTATION

    def get_last_seen(self):
        return self.last_seen

    def update_cache(self):
        key = self.get_cache_key()
        cache.set(key, self)

    def save(self, *args, **kwargs):
        self.update_cache()
        super(LocalizedUserProfile, self).save(*args, **kwargs)


def update_user_profile(instance, **kwargs):
    profile = get_profile(instance)
    profile.save()


post_save.connect(
    update_user_profile,
    sender=User,
    dispatch_uid='update_profile_on_authuser_save'
)
