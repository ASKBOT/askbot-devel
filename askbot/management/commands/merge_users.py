from django.core.management.base import CommandError, BaseCommand
from django.db import transaction
from askbot.models import (
    GroupMembership,
    LocalizedUserProfile,
    Post,
    User,
    UserProfile
)
from askbot import const

# TODO: this command is broken - doesn't take into account UNIQUE constraints
#       and therefore causes db errors:
# In SQLite: "Warning: columns feed_type, subscriber_id are not unique"
# In MySQL: "Warning: (1062, "Duplicate entry 'm_and_c-2' for key 'askbot_emailfeedsetting_feed_type_6da6fdcd_uniq'")"
# In PostgreSQL: "Warning: duplicate key value violates unique constraint "askbot_emailfeedsetting_feed_type_6da6fdcd_uniq"
#                "DETAIL:  Key (feed_type, subscriber_id)=(m_and_c, 619) already exists."
#                (followed by series of "current transaction is aborted, commands ignored until end of transaction block" warnings)

def print_post_info():
    for p in Post.objects.all():
        print(p.author, end=' ')
    print('')

class MergeUsersBaseCommand(BaseCommand):
    args = '<from_user_id> <to_user_id>'
    help = 'Merge an account and all information from a <user_id> to a <user_id>, deleting the <from_user>'

    def add_arguments(self, parser):
        parser.add_argument('from_user_id', type=int, nargs=1)
        parser.add_argument('to_user_id', type=int, nargs=1)

    def handle(self, *arguments, **options):
        self.parse_arguments(options['from_user_id'][0], options['to_user_id'][0])
        self.prepare()

        #rel_objs = User._meta.get_all_related_objects()
        # according to https://docs.djangoproject.com/en/1.10/ref/models/meta/ this becomes:
        rel_objs = [
            f for f in User._meta.get_fields()
            if (f.one_to_many or f.one_to_one)
            and f.auto_created and not f.concrete
        ]
        for rel in rel_objs:
            self.process_relation(rel)

        #rel_m2ms = User._meta.get_all_related_many_to_many_objects()
        rel_m2ms = [
            f for f in User._meta.get_fields(include_hidden=True)
            if f.many_to_many and f.auto_created
        ]
        for rel in rel_m2ms:
            self.process_m2m(rel)

        self.cleanup()

    def cleanup(self):
        raise Exception('Not implemented')

    def prepare(self):
        pass

    def parse_arguments(self, *arguments):
        if len(arguments) != 2:
            raise CommandError('Arguments are <from_user_id> to <to_user_id>')
        self.from_user = User.objects.get(id=arguments[0])
        self.to_user = User.objects.get(id=arguments[1])

    def process_relation(self, rel):
        try:
            self.process_field(rel.related_model, rel.field.name)
        except Exception as error:
            self.stdout.write(('Warning: %s\n' % error).encode('utf-8'))

    def process_m2m(self, rel):
        try:
            self.process_m2m_field(rel.related_model, rel.field.name)
        except Exception as error:
            self.stdout.write(('Warning: %s\n' % error).encode('utf-8'))

    def process_field(self, model, field_name):
        """reassigns the related object to the new user"""
        filter_condition = {field_name: self.from_user}
        related_objects_qs = model.objects.filter(**filter_condition)
        update_condition = {field_name: self.to_user}
        related_objects_qs.update(**update_condition)

    def process_m2m_field(self, model, field_name):
        """removes the old user from the M2M relation
        and adds the new user"""
        filter_condition = {field_name: self.from_user}
        related_objects_qs = model.objects.filter(**filter_condition)
        for obj in related_objects_qs:
            m2m_field = getattr(obj, field_name)
            m2m_field.remove(self.from_user)
            m2m_field.add(self.to_user)


class Command(MergeUsersBaseCommand):

    def prepare(self):
        """Takes care of things that cannot be done automatically"""
        #copy group memberships
        memberships = GroupMembership.objects.filter(user=self.from_user)
        for from_gm in memberships:
            to_gm = self.to_user.get_group_membership(from_gm.group)
            if to_gm:
                to_gm.level = max(to_gm.level, from_gm.level)
                to_gm.save()
                from_gm.delete()
            else:
                from_gm.user = self.to_user
                from_gm.save()

        #move followers
        for follower in self.from_user.get_followers():
            follower.unfollow_user(self.from_user)
            if follower.pk != self.to_user.pk:
                if not follower.is_following(self.to_user):
                    follower.follow_user(self.to_user)

        #move followed users
        for followed in self.from_user.get_followed_users():
            self.from_user.unfollow_user(followed)
            if followed.pk != self.to_user.pk:
                if not self.to_user.is_following(followed):
                    self.to_user.follow_user(followed)

        #delete subscriptions (todo: merge properly)
        self.from_user.notification_subscriptions.all().delete()

        #merge reputations
        localized_profiles = LocalizedUserProfile.objects.filter(auth_user=self.from_user)
        for profile in localized_profiles:
            self.to_user.receive_reputation(profile.reputation, profile.language_code)
        #delete dupes of localized profiles
        localized_profiles.delete()

        #merge items stored in the user.askbot_profile
        try:
            from_profile = self.from_user.askbot_profile
        except UserProfile.DoesNotExist:
            pass
        else:
            self.to_user.gold += from_profile.gold
            self.to_user.silver += from_profile.silver
            self.to_user.bronze += from_profile.bronze

            #merge last seen dates
            if from_profile.last_seen > self.to_user.last_seen:
                self.to_user.last_seen = from_profile.last_seen

            #merge date joined dates
            if self.from_user.date_joined < self.to_user.date_joined:
                self.to_user.date_joined = self.from_user.date_joined

            self.to_user.askbot_profile.save()
            self.to_user.save()
            from_profile.delete()

    def cleanup(self):
        self.to_user.save()
        self.from_user.delete()
