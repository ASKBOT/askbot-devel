from askbot.tests.utils import AskbotTestCase
from askbot.search.state_manager import SearchState
import askbot.conf
from django.core import urlresolvers


class SearchStateTests(AskbotTestCase):
    def _ss(self, query=None, tags=None):
        return SearchState(
            scope=None,
            sort=None,
            query=query,
            tags=tags,
            author=None,
            page=None,

            user_logged_in=False
        )

    def test_no_selectors(self):
        ss = self._ss()
        self.assertEqual(
            'scope:all/sort:activity-desc/page:1/',  # search defaults
            ss.query_string()
        )

    def test_buggy_selectors(self):
        ss = SearchState(
            scope='blah1',
            sort='blah2',
            query=None,
            tags=None,

            # INFO: URLs for the following selectors accept only digits!
            author=None,
            page='0',

            user_logged_in=False
        )
        self.assertEqual(
            'scope:all/sort:activity-desc/page:1/',  # search defaults
            ss.query_string()
        )

    def test_all_valid_selectors(self):
        ss = SearchState(
            scope='unanswered',
            sort='age-desc',
            query=' alfa',
            tags='miki, mini',
            author='12',
            page='2',

            user_logged_in=False
        )
        self.assertEqual(
            'scope:unanswered/sort:age-desc/tags:miki,mini/author:12/page:2/query:alfa/',
            ss.query_string()
        )
        self.assertEqual(
            'scope:unanswered/sort:age-desc/tags:miki,mini/author:12/page:2/query:alfa/',
            ss.deepcopy().query_string()
        )

    def test_edge_cases_1(self):
        ss = SearchState(
            scope='followed', # this is not a valid choice for non-logger users
            sort='age-desc',
            query=' alfa',
            tags='miki, mini',
            author='12',
            page='2',

            user_logged_in=False
        )
        self.assertEqual(
            'scope:all/sort:age-desc/tags:miki,mini/author:12/page:2/query:alfa/',
            ss.query_string()
        )
        self.assertEqual(
            'scope:all/sort:age-desc/tags:miki,mini/author:12/page:2/query:alfa/',
            ss.deepcopy().query_string()
        )

        ss = SearchState(
            scope='followed',
            sort='age-desc',
            query=' alfa',
            tags='miki, mini',
            author='12',
            page='2',

            user_logged_in=True
        )
        self.assertEqual(
            'scope:followed/sort:age-desc/tags:miki,mini/author:12/page:2/query:alfa/',
            ss.query_string()
        )
        self.assertEqual(
            'scope:followed/sort:age-desc/tags:miki,mini/author:12/page:2/query:alfa/',
            ss.deepcopy().query_string()
        )

    def test_edge_cases_2(self):
        old_func = askbot.conf.should_show_sort_by_relevance
        askbot.conf.should_show_sort_by_relevance = lambda: True # monkey patch

        ss = SearchState(
            scope='all',
            sort='relevance-desc',
            query='hejho',
            tags='miki, mini',
            author='12',
            page='2',

            user_logged_in=False
        )
        self.assertEqual(
            'scope:all/sort:relevance-desc/tags:miki,mini/author:12/page:2/query:hejho/',
            ss.query_string()
        )

        ss = SearchState(
            scope='all',
            sort='relevance-desc', # this is not a valid choice for empty queries
            query=None,
            tags='miki, mini',
            author='12',
            page='2',

            user_logged_in=False
        )
        self.assertEqual(
            'scope:all/sort:activity-desc/tags:miki,mini/author:12/page:2/',
            ss.query_string()
        )

        askbot.conf.should_show_sort_by_relevance = lambda: False # monkey patch

        ss = SearchState(
            scope='all',
            sort='relevance-desc', # this is also invalid for db-s other than Postgresql
            query='hejho',
            tags='miki, mini',
            author='12',
            page='2',

            user_logged_in=False
        )
        self.assertEqual(
            'scope:all/sort:activity-desc/tags:miki,mini/author:12/page:2/query:hejho/',
            ss.query_string()
        )

        askbot.conf.should_show_sort_by_relevance = old_func

    def test_query_escaping(self):
        ss = self._ss(query=' alfa miki maki +-%#?= lalala/: ') # query coming from URL is already unescaped

        qs = 'scope:all/sort:activity-desc/page:1/query:alfa%20miki%20maki%20+-%25%23%3F%3D%20lalala%2F%3A/'
        self.assertEqual(qs, ss.query_string())
        self.assertEqual(qs, ss.deepcopy().query_string())

    def test_tag_escaping(self):
        ss = self._ss(tags=' aA09_+.-#, miki ') # tag string coming from URL is already unescaped
        self.assertEqual(
            'scope:all/sort:activity-desc/tags:aA09_+.-%23,miki/page:1/',
            ss.query_string()
        )

    def test_extract_users(self):
        ss = self._ss(query='"@anna haha @"maria fernanda" @\'diego maradona\' hehe [user:karl  marx] hoho  user:\' george bush  \'')
        self.assertEqual(
            sorted(ss.query_users),
            sorted(['anna', 'maria fernanda', 'diego maradona', 'karl marx', 'george bush'])
        )
        self.assertEqual(sorted(ss.query_users), sorted(ss.deepcopy().query_users))

        self.assertEqual(ss.stripped_query, '" haha hehe hoho')
        self.assertEqual(ss.stripped_query, ss.deepcopy().stripped_query)

        self.assertEqual(
            'scope:all/sort:activity-desc/page:1/query:%22%40anna%20haha%20%40%22maria%20fernanda%22%20%40%27diego%20maradona%27%20hehe%20%5Buser%3Akarl%20%20marx%5D%20hoho%20%20user%3A%27%20george%20bush%20%20%27/',
            ss.query_string()
        )

    def test_extract_tags(self):
        ss = self._ss(query='#tag1 [tag: tag2] some text [tag3] query')
        self.assertEqual(set(ss.query_tags), set(['tag1', 'tag2', 'tag3']))
        self.assertEqual(ss.stripped_query, 'some text query')

        self.assertFalse(ss.deepcopy().query_tags is ss.query_tags)
        self.assertEqual(set(ss.deepcopy().query_tags), set(ss.query_tags))
        self.assertTrue(ss.deepcopy().stripped_query is ss.stripped_query)
        self.assertEqual(ss.deepcopy().stripped_query, ss.stripped_query)

    def test_extract_title1(self):
        ss = self._ss(query='some text query [title: what is this?]')
        self.assertEqual(ss.query_title, 'what is this?')
        self.assertEqual(ss.stripped_query, 'some text query')

    def test_extract_title2(self):
        ss = self._ss(query='some text query title:"what is this?"')
        self.assertEqual(ss.query_title, 'what is this?')
        self.assertEqual(ss.stripped_query, 'some text query')

    def test_extract_title3(self):
        ss = self._ss(query='some text query title:\'what is this?\'')
        self.assertEqual(ss.query_title, 'what is this?')
        self.assertEqual(ss.stripped_query, 'some text query')

    def test_deep_copy_1(self):
        # deepcopy() is tested in other tests as well, but this is a dedicated test
        # just to make sure in one place that everything is ok:
        # 1. immutable properties (strings, ints) are just assigned to the copy
        # 2. lists are cloned so that change in the copy doesn't affect the original

        ss = SearchState(
            scope='unanswered',
            sort='votes-desc',
            query='hejho #tag1 [tag: tag2] @user @user2 title:"what is this?"',
            tags='miki, mini',
            author='12',
            page='2',

            user_logged_in=False
        )
        ss2 = ss.deepcopy()

        self.assertEqual(ss.scope, 'unanswered')
        self.assertTrue(ss.scope is ss2.scope)

        self.assertEqual(ss.sort, 'votes-desc')
        self.assertTrue(ss.sort is ss2.sort)

        self.assertEqual(ss.query, 'hejho #tag1 [tag: tag2] @user @user2 title:"what is this?"')
        self.assertTrue(ss.query is ss2.query)

        self.assertFalse(ss.tags is ss2.tags)
        self.assertItemsEqual(ss.tags, ss2.tags)

        self.assertEqual(ss.author, 12)
        self.assertTrue(ss.author is ss2.author)

        self.assertEqual(ss.page, 2)
        self.assertTrue(ss.page is ss2.page)

        self.assertEqual(ss.stripped_query, 'hejho')
        self.assertTrue(ss.stripped_query is ss2.stripped_query)

        self.assertItemsEqual(ss.query_tags, ['tag1', 'tag2'])
        self.assertFalse(ss.query_tags is ss2.query_tags)

        self.assertItemsEqual(ss.query_users, ['user', 'user2'])
        self.assertFalse(ss.query_users is ss2.query_users)

        self.assertEqual(ss.query_title, 'what is this?')
        self.assertTrue(ss.query_title is ss2.query_title)

        self.assertEqual(ss._questions_url, urlresolvers.reverse('questions'))
        self.assertTrue(ss._questions_url is ss2._questions_url)

    def test_deep_copy_2(self):
        # Regression test: a special case of deepcopy() when `tags` list is empty,
        # there was a bug before where this empty list in original and copy pointed
        # to the same list object
        ss = SearchState.get_empty()
        ss2 = ss.deepcopy()

        self.assertFalse(ss.tags is ss2.tags)
        self.assertItemsEqual(ss.tags, ss2.tags)
        self.assertItemsEqual([], ss2.tags)

    def test_cannot_add_already_added_tag(self):
        ss = SearchState.get_empty().add_tag('double').add_tag('double')
        self.assertListEqual(['double'], ss.tags)

    def test_prevent_dupped_tags(self):
        ss = SearchState(
            scope=None,
            sort=None,
            query=None,
            tags='valid1,dupped,valid2,dupped',
            author=None,
            page=None,
            user_logged_in=False
        )
        self.assertEqual(
            'scope:all/sort:activity-desc/tags:valid1,dupped,valid2/page:1/',
            ss.query_string()
        )

