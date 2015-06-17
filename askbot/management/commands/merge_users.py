from django.core.management.base import CommandError, BaseCommand
from django.db import transaction
from askbot.models import User

# TODO: this command is broken - doesn't take into account UNIQUE constraints
#       and therefore causes db errors:
# In SQLite: "Warning: columns feed_type, subscriber_id are not unique"
# In MySQL: "Warning: (1062, "Duplicate entry 'm_and_c-2' for key 'askbot_emailfeedsetting_feed_type_6da6fdcd_uniq'")"
# In PostgreSQL: "Warning: duplicate key value violates unique constraint "askbot_emailfeedsetting_feed_type_6da6fdcd_uniq"
#                "DETAIL:  Key (feed_type, subscriber_id)=(m_and_c, 619) already exists."
#                (followed by series of "current transaction is aborted, commands ignored until end of transaction block" warnings)

class MergeUsersBaseCommand(BaseCommand):
    args = '<from_user_id> <to_user_id>'
    help = 'Merge an account and all information from a <user_id> to a <user_id>, deleting the <from_user>'

    @transaction.commit_manually
    def handle(self, *arguments, **options):
        self.parse_arguments(*arguments)

        for rel in User._meta.get_all_related_objects():
            sid = transaction.savepoint()
            try:
                self.process_field(rel.model, rel.field.name)
                transaction.savepoint_commit(sid)
            except Exception, error:
                self.stdout.write((u'Warning: %s\n' % error).encode('utf-8'))
                transaction.savepoint_rollback(sid)
            transaction.commit()

        for rel in User._meta.get_all_related_many_to_many_objects():
            sid = transaction.savepoint()
            try:
                self.process_m2m_field(rel.model, rel.field.name)
                transaction.savepoint_commit(sid)
            except Exception, error:
                self.stdout.write((u'Warning: %s\n' % error).encode('utf-8'))
                transaction.savepoint_rollback(sid)
            transaction.commit()

        self.process_custom_user_fields()
        self.cleanup()
        transaction.commit()

    def cleanup(self):
        raise Exception, 'Not implemented'

    def process_custom_user_fields(self):
        """Put app specific logic here."""
        raise Exception, 'Not implemented'

    def parse_arguments(self, *arguments):
        if len(arguments) != 2:
            raise CommandError('Arguments are <from_user_id> to <to_user_id>')
        self.from_user = User.objects.get(id = arguments[0])
        self.to_user = User.objects.get(id = arguments[1])

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

    def process_custom_user_fields(self):
        self.to_user.reputation += self.from_user.reputation - 1
        self.to_user.gold += self.from_user.gold
        self.to_user.silver += self.from_user.silver
        self.to_user.bronze += self.from_user.bronze

        if self.from_user.last_seen > self.to_user.last_seen:
            self.to_user.last_seen = self.from_user.last_seen

        if self.from_user.date_joined < self.to_user.date_joined:
            self.to_user.date_joined = self.from_user.date_joined

    def cleanup(self):
        self.to_user.save()
        self.from_user.set_status('b')
