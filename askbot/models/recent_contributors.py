"""`AvatarBlockData` - class helping to access data
needed to draw user avatars on the main page"""
from collections import defaultdict
from django.core.cache import cache
from askbot import const
from askbot.models import Activity, Post, User
from askbot.conf import settings as askbot_settings
from askbot.utils.translation import get_language


class AvatarsBlockData:
    """Class managing data for the avatars
    block, displayed on the main page"""
    CACHE_KEY = 'askbot-avatar-block-data'

    @classmethod
    def get_data(cls):
        """Returns list of (id, avatar_url, username)"""
        if not askbot_settings.SIDEBAR_MAIN_SHOW_AVATARS:
            return []

        data = cls.get_cached_data()
        if data:
            return data
        data = cls.get_fresh_data()
        cls.cache_data(data[:askbot_settings.SIDEBAR_MAIN_AVATAR_LIMIT])
        return data


    @classmethod
    def get_cached_data(cls): #pylint: disable=missing-docstring
        return cache.get(cls.CACHE_KEY)


    @classmethod
    def cache_data(cls, data): #pylint: disable=missing-docstring
        cache.set(cls.CACHE_KEY, data[:askbot_settings.SIDEBAR_MAIN_AVATAR_LIMIT])


    @classmethod
    def get_user_datum(cls, data, user):
        """Returns user datum from data or `None`"""
        for datum in data:
            if datum['id'] == user.id:
                return datum
        return None


    @classmethod
    def push_user(cls, user):
        """Sets avatar of the `user` first in the list,
        updates the user data"""
        if not askbot_settings.SIDEBAR_MAIN_SHOW_AVATARS:
            return

        data = cls.get_data()
        user_datum = cls.get_user_datum(data, user)
        if user_datum:
            data.remove(user_datum)
        else:
            user_datum = cls.init_user_datum(user)

        data.insert(0, user_datum)
        cls.cache_data(data)


    @classmethod
    def update_user(cls, user):
        """Updates user's avatar, if present"""
        if not askbot_settings.SIDEBAR_MAIN_SHOW_AVATARS:
            return

        data = cls.get_data()
        user_datum = cls.get_user_datum(data, user)
        if not user_datum:
            return
        user_datum['avatar_url'] = user.get_avatar_url()
        cls.cache_data(data)


    @classmethod
    def get_fresh_data(cls):
        """Returns data from the database queries"""
        max_users = askbot_settings.SIDEBAR_MAIN_AVATAR_LIMIT
        data = []
        while len(data) < max_users:
            try:
                more_data = cls.get_new_data_batch(data)
            except StopIteration:
                break
            else:
                data.extend(more_data)

            if not more_data:
                break

        return data[:max_users]


    @classmethod
    def init_user_datum(cls, user):
        """Returns user datum dictionary"""
        return {
            'id': user.id,
            'avatar_url': user.get_avatar_url(),
            'profile_url': user.get_absolute_url(),
            'username': user.username
        }


    @classmethod
    def get_user_data_by_uids(cls, uids):
        """Returns data tuples for given user ids"""
        users = User.objects.filter(pk__in=uids)
        users = users.only('id', 'username', 'askbot_profile__gravatar')
        users_by_id = {user.id: user for user in users}
        data = []
        for uid in uids:
            user = users_by_id[uid]
            data.append(cls.init_user_datum(user))
        return data


    @classmethod
    def get_new_data_batch(cls, data):
        """Returns up to the desired limit of unique
        by id data sets (id, avatar_url, username)"""
        uids = [datum['id'] for datum in data]
        uids_by_post_id = defaultdict(list)
        post_ids = set()
        acts = cls.get_activities_batch(data)
        if not acts:
            raise StopIteration

        for act in acts:
            if act.user_id not in uids:
                uids_by_post_id[act.question_id].append(act.user_id)
                post_ids.add(act.question_id)

        posts = Post.objects.filter(id__in=post_ids, language_code=get_language())
        posts = posts.order_by('-id').only('id')

        new_uids = []
        for post in posts:
            act_uids = uids_by_post_id[post.pk]
            for uid in act_uids:
                if uid not in new_uids:
                    new_uids.append(uid)

        return cls.get_user_data_by_uids(new_uids)


    @classmethod
    def get_activity_query_set(cls):
        """Returns query set of activities"""
        act_types = const.SIDEBAR_AVATARS_BLOCK_ACTIVITY_TYPES
        acts = Activity.objects.filter(activity_type__in=act_types)
        acts = acts.only('user_id', 'question_id')
        return acts.order_by('-id')


    @classmethod
    def get_activities_batch(cls, data):
        """Returns batch of activity objects equal in size
        to the max number of avatars in the block"""
        acts = cls.get_activity_query_set()
        if data:
            max_user_id = data[-1]['id']
            acts = acts.filter(user_id__lt=max_user_id)
        return list(acts[:2*askbot_settings.SIDEBAR_MAIN_AVATAR_LIMIT])
