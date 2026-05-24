"""Tests for canonical tag-URL handling.

Without canonicalization, every permutation of the same tag set produces a
distinct URL serving identical content. This fragments caches and is
exploited by scrapers that enumerate tag orderings to bypass per-URL
caching. The fix sorts tags alphabetically and 301-redirects unsorted
tag URLs to the canonical (sorted) form.
"""
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser

from askbot.search.state_manager import SearchState
from askbot.tests.utils import AskbotTestCase
from askbot.views.readers import questions as questions_view


class SearchStateTagSortingTests(AskbotTestCase):
    """SearchState should normalize tag order on construction."""

    def test_tags_sorted_alphabetically(self):
        ss = SearchState(scope='all', sort='age-desc',
                         tags='zebra,apple,mango')
        self.assertEqual(ss.tags, ['apple', 'mango', 'zebra'])

    def test_already_sorted_unchanged(self):
        ss = SearchState(scope='all', sort='age-desc',
                         tags='apple,mango,zebra')
        self.assertEqual(ss.tags, ['apple', 'mango', 'zebra'])

    def test_duplicates_removed_then_sorted(self):
        ss = SearchState(scope='all', sort='age-desc',
                         tags='zebra,apple,zebra,mango')
        self.assertEqual(ss.tags, ['apple', 'mango', 'zebra'])

    def test_query_string_uses_sorted_tags(self):
        ss = SearchState(scope='all', sort='age-desc',
                         tags='zebra,apple,mango')
        self.assertIn('tags:apple,mango,zebra', ss.query_string())

    def test_no_tags_no_change(self):
        ss = SearchState(scope='all', sort='age-desc', tags=None)
        self.assertEqual(ss.tags, [])


class CanonicalUrlRedirectTests(AskbotTestCase):
    """questions() view should 301-redirect unsorted tag URLs."""

    def setUp(self):
        self.factory = RequestFactory()

    def _get(self, path, **kwargs):
        request = self.factory.get(path)
        request.user = AnonymousUser()
        return questions_view(request, **kwargs)

    def test_unsorted_tags_redirect_301(self):
        """An unsorted tag URL should 301 to the sorted-tag canonical URL."""
        response = self._get(
            '/questions/scope:all/sort:age-desc/tags:zebra,apple,mango/',
            scope='all', sort='age-desc', tags='zebra,apple,mango'
        )
        self.assertEqual(response.status_code, 301)
        self.assertIn('tags:apple,mango,zebra', response['Location'])

    def test_sorted_tags_no_redirect(self):
        """An already-canonical URL should be served, not redirected."""
        response = self._get(
            '/questions/scope:all/sort:age-desc/tags:apple,mango,zebra/page:1/',
            scope='all', sort='age-desc', tags='apple,mango,zebra'
        )
        # 200 or other content response, not a 301 redirect
        self.assertNotEqual(response.status_code, 301)

    def test_bare_questions_url_no_redirect(self):
        """The bare /questions/ URL has no tags; should not redirect."""
        response = self._get('/questions/')
        self.assertNotEqual(response.status_code, 301)

    def test_non_tag_filter_no_redirect(self):
        """A scope+sort URL without tags should not redirect."""
        response = self._get(
            '/questions/scope:unanswered/sort:age-desc/',
            scope='unanswered', sort='age-desc'
        )
        self.assertNotEqual(response.status_code, 301)

    def test_redirect_preserves_other_params(self):
        """Redirect should carry through scope, sort, page parameters."""
        response = self._get(
            '/questions/scope:unanswered/sort:votes-desc/tags:c,a,b/page:3/',
            scope='unanswered', sort='votes-desc', tags='c,a,b', page='3'
        )
        self.assertEqual(response.status_code, 301)
        location = response['Location']
        self.assertIn('scope:unanswered', location)
        self.assertIn('sort:votes-desc', location)
        self.assertIn('tags:a,b,c', location)
        self.assertIn('page:3', location)

    def test_duplicate_tags_redirected_to_deduped_sorted(self):
        """URL with duplicate tags should redirect to deduped sorted URL."""
        response = self._get(
            '/questions/scope:all/sort:age-desc/tags:b,a,b,c/',
            scope='all', sort='age-desc', tags='b,a,b,c'
        )
        self.assertEqual(response.status_code, 301)
        self.assertIn('tags:a,b,c', response['Location'])
