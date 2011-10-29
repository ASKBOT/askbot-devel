from django.core.management.base import CommandError, BaseCommand
from django.db.models import get_model
from askbot.models import User


class Command(BaseCommand):
  args = '<from_user_id> <to_user_id>'
  help = 'Migrate an account and all information from a <user_id> to a <user_id>, deleting the <from_user>'

  def parse_arguments(self, *arguments):
    if len(arguments) != 2:
      raise CommandError('Arguments are <from_user_id> to <to_user_id>')
    self.from_user = User.objects.get(id = arguments[0])
    self.to_user = User.objects.get(id = arguments[1])

  def handle(self, *arguments, **options):
    self.parse_arguments(*arguments)

    for rel in User._meta.get_all_related_objects():
      try:
        self.process_field(rel.model, rel.field.name)
      except Exception, e:
        if rel.field.name == 'UserAssociation':
          self.stdout.write('had problem with UserAssociation uniquiness')
        elif rel.field.name == 'UserPasswordQueue':
          self.stdout.write('had problem with UserPasswordQueue uniquiness')
        else:
          self.stdout.write('Recieved Error: %s' % (e))

    for rel in User._meta.get_all_related_many_to_many_objects():
      self.process_m2m_field(rel.model, rel.field.name)
           
    self.to_user.reputation += self.from_user.reputation - 1
    self.to_user.gold += self.from_user.gold
    self.to_user.silver += self.from_user.silver
    self.to_user.bronze += self.from_user.bronze

    if self.from_user.last_seen > self.to_user.last_seen:
      self.to_user.last_seen = self.from_user.last_seen

    if self.from_user.date_joined < self.to_user.date_joined:
      self.to_user.date_joined = self.from_user.date_joined

    self.to_user.save()

    self.from_user.delete()

  def process_field(self, model, field_name):
    filter_condition = {field_name: self.from_user}
    related_objects_qs = model.objects.filter(**filter_condition)
    update_condition = {field_name: self.to_user}
    related_objects_qs.update(**update_condition)

  def process_m2m_field(self, model, field_name):
    filter_condition = {field_name: self.from_user}
    related_objects_qs = model.objects.filter(**filter_condition)
    for obj in related_objects_qs:
      m2m_field = getattr(obj, field_name)
      m2m_field.remove(self.from_user)
      m2m_field.add(self.to_user)
