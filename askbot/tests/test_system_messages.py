"""Structural drift guard for the system_messages Jinja template.

This test pins the per-message DOM shape produced by the server-rendered
``components/system_messages.html`` template. The frontend counterpart
(``SystemMessage`` in ``askbot/media/js/utils/system_message.js``) must
emit the same shape so AJAX-injected banners and page-load banners look
identical.

Scope: this test runs only the Python/Jinja side. It catches drift when
the template changes. It does NOT execute the JS, so a change to
``system_message.js`` that breaks parity will only be caught here if the
expected shape below is updated to match. The real cross-render check
lives in the e2e coverage.
"""

from bs4 import BeautifulSoup
from django.template import engines
from django.template.loader import render_to_string
from django.test import SimpleTestCase


# Sanity guard: the Jinja2 engine is keyed by the basename of the
# BACKEND class because settings.py does not declare an explicit NAME.
# If that ever changes the assertion fails loudly.
assert 'jinja2' in engines, "Jinja2 template engine not registered as 'jinja2'"


def _assert_per_message_shape(test, node, expected_text):
    """Per-message subtree must be div.js-system-message > div.content-wrapper > text."""
    test.assertEqual(node.name, 'div')
    test.assertEqual(set(node.get('class', [])), {'js-system-message'})

    children = [child for child in node.children if getattr(child, 'name', None)]
    test.assertEqual(len(children), 1)

    inner = children[0]
    test.assertEqual(inner.name, 'div')
    test.assertEqual(set(inner.get('class', [])), {'content-wrapper'})

    inner_children = [child for child in inner.children if getattr(child, 'name', None)]
    test.assertEqual(inner_children, [])
    test.assertEqual(inner.get_text(strip=True), expected_text)


class SystemMessagesTemplateShapeTests(SimpleTestCase):
    """Uses SimpleTestCase: no DB, fixtures, or HTTP client needed.

    The render below goes through Django's template loader, which needs
    Django settings to be configured but does not need a database or
    askbot user setup. Do not "upgrade" this to TestCase.
    """

    def test_per_message_subtree_matches_system_message_js(self):
        html = render_to_string(
            'components/system_messages.html',
            {'user_messages': ['hello']},
            using='jinja2',
        )
        soup = BeautifulSoup(html, 'html5lib')

        container = soup.select_one('div.js-system-messages')
        assert container is not None, 'system_messages container missing'

        container_children = [
            child for child in container.children if getattr(child, 'name', None)
        ]
        self.assertGreaterEqual(len(container_children), 2)

        first = container_children[0]
        self.assertEqual(first.name, 'div')
        self.assertIn('remove-messages-container', first.get('class', []))

        message_node = soup.select_one('div.js-system-message')
        assert message_node is not None, 'per-message subtree missing'
        _assert_per_message_shape(self, message_node, 'hello')
