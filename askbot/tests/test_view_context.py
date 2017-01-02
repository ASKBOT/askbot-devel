from django.contrib.auth.models import AnonymousUser
from askbot.tests.utils import AskbotTestCase
from askbot.models import Group
from askbot.views import context

class ViewContextTests(AskbotTestCase):
    def test_get_for_inbox_anonymous(self):
        anon = AnonymousUser()
        inbox_context = context.get_for_inbox(anon)
        self.assertEqual(inbox_context, None)

    def test_get_for_inbox_group_join(self):
        mod = self.create_user('mod', status='d')
        group = Group(name='grp', openness=Group.MODERATED)
        group.save()
        mod.join_group(group)

        simple = self.create_user('simple')
        simple.join_group(group)

        inbox_context = context.get_for_inbox(mod)

        self.assertEqual(inbox_context['re_count'], 0)
        self.assertEqual(inbox_context['group_join_requests_count'], 1)

        inbox_context = context.get_for_inbox(simple)
        values = set(inbox_context.values())
        self.assertEqual(values, set([0, 0]))
