from askbot.tests.utils import AskbotTestCase
from django.core.urlresolvers import reverse
import simplejson

class ApiV1Tests(AskbotTestCase):
    def test_api_v1_user(self):
        user = self.create_user('apiuser')
        response = self.client.get(reverse('api_v1_user', args=(user.id,)))
        response_data = simplejson.loads(response.content)
        expected_keys = set(['id', 'username', 'reputation', 'questions', 'comments',
                'avatar', 'joined_at', 'last_seen_at', 'answers', 'gold', 'silver',
                'bronze'])
        self.assertEqual(expected_keys, set(response_data.keys()))

    def test_api_v1_info(self):
        response = self.client.get(reverse('api_v1_info'))
        response_data = simplejson.loads(response.content)
        expected_keys = set(['answers', 'comments', 'users', 'groups', 'questions'])
        self.assertEqual(expected_keys, set(response_data.keys()))

    def test_api_v1_users(self):
        self.create_user('somebody')
        response = self.client.get(reverse('api_v1_users'))
        response_data = simplejson.loads(response.content)
        expected_keys = set(['pages', 'count', 'users'])
        self.assertEqual(expected_keys, set(response_data.keys()))

        expected_keys = set(['id', 'avatar', 'username',
                            'joined_at', 'last_seen_at', 'reputation',
                            'gold', 'silver', 'bronze'])
        self.assertEqual(expected_keys, set(response_data['users'][0].keys()))

    def test_api_v1_questions(self):
        user = self.create_user('user')
        self.post_question(user=user)
        response = self.client.get(reverse('api_v1_questions'))
        response_data = simplejson.loads(response.content)
        expected_keys = set(['count', 'pages', 'questions'])
        self.assertEqual(expected_keys, set(response_data.keys()))

        expected_keys = set([
                        'id', 'view_count', 'title', 'answer_count', 'answer_ids',
                        'last_activity_by', 'last_activity_at', 'author',
                        'url', 'tags', 'added_at', 'score', 'summary',
                        'accepted_answer_id'
                    ])
        self.assertEqual(expected_keys, set(response_data['questions'][0].keys()))

        author_info = response_data['questions'][0]['author']
        self.assertEqual(set(author_info.keys()), set(['id', 'username']))
        self.assertEqual(set(author_info.values()), set([user.id, user.username]))

        last_act_info = response_data['questions'][0]['last_activity_by']
        self.assertEqual(set(last_act_info.keys()), set(['id', 'username']))
        self.assertEqual(set(last_act_info.values()), set([user.id, user.username]))
