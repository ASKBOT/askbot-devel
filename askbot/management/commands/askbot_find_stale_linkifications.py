"""Audit (and optionally undo) auto-links in stored post HTML that the current
linkify settings would no longer produce.

Changing the linkify livesettings (fuzzy toggle + TLD allowlist) only affects
future renders. Posts saved earlier keep their rendered HTML, so bare-domain
auto-links the settings now drop stay in the database until a post is
re-rendered. This command finds those posts, reports them by default, and
re-renders only the affected ones when run with --fix.

Side effect of --fix: it re-renders the whole post from its source, not just the
offending link. Mentions are recomputed against the current author list, current
markup rules are re-applied, and links that were stripped at save time for a
low-reputation author are re-introduced. This matches askbot_render_posts.
"""
from django.core.management.base import BaseCommand
from bs4 import BeautifulSoup
from askbot.utils.console import get_yes_or_no, ProgressBar
from askbot.models import Post

CONFIRM_MESSAGE = (
    'Affected posts will be re-rendered and their stored HTML replaced. '
    'This also refreshes mentions and re-applies current markup rules. Proceed?'
)


def extract_anchors(html):
    """Returns a set of (visible text, href) pairs for the <a> tags in html."""
    soup = BeautifulSoup(html or '', 'html5lib')
    anchors = set()
    for link in soup.find_all('a'):
        text = ''.join(link.text) or ''
        href = link.get('href', '') or ''
        anchors.add((text, href))
    return anchors


def is_stale_bare_autolink(text, href, source_text):
    """True when an anchor is a bare-domain auto-link that current settings drop.

    Keeps only external links whose scheme was added by linkify. Excludes
    @mentions, internal or relative links, and explicit links whose full href
    is written out in the source.
    """
    if not (href.startswith('http://') or href.startswith('https://')):
        return False
    if text.strip().startswith('@'):
        return False
    if href in source_text:
        return False
    return True


class Command(BaseCommand): #pylint: disable=missing-class-docstring
    help = (
        'Reports posts whose stored HTML contains bare-domain auto-links that '
        'the current linkify settings no longer produce. With --fix, re-renders '
        'only those posts (replacing stored html and summary via a direct '
        'update that fires no signals and does not touch edit-tracking fields). '
        '--fix re-renders the whole post from source, so mentions and other '
        'markup are refreshed too.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix', '--apply', action='store_true', dest='fix',
            help='Re-render and save the affected posts (default: report only).')
        parser.add_argument(
            '--limit', type=int, default=None,
            help='Process at most this many posts.')
        parser.add_argument(
            '--start-id', type=int, default=None, dest='start_id',
            help='Only consider posts with id greater than or equal to this.')
        parser.add_argument(
            '--end-id', type=int, default=None, dest='end_id',
            help='Only consider posts with id less than or equal to this.')

    def handle(self, *args, **kwargs): #pylint: disable=missing-docstring, unused-argument
        fix = kwargs['fix']
        limit = kwargs['limit']
        verbosity = kwargs['verbosity']

        if fix and verbosity > 0:
            if get_yes_or_no(CONFIRM_MESSAGE) == 'no':
                return

        # Only posts with an external link in stored HTML can have a stale
        # auto-link, so skip the rest to avoid re-rendering them. This is a
        # superset filter - the render and diff below stay the source of truth.
        posts = Post.objects.filter(deleted=False, approved=True)\
                            .filter(html__contains='href="http')\
                            .exclude(text__isnull=True)\
                            .exclude(text='')\
                            .order_by('pk')
        if kwargs['start_id'] is not None:
            posts = posts.filter(pk__gte=kwargs['start_id'])
        if kwargs['end_id'] is not None:
            posts = posts.filter(pk__lte=kwargs['end_id'])

        count = posts.count()
        if limit is not None:
            count = min(count, limit)

        # The default report writes findings to stdout, the same stream the
        # progress bar uses, so keep the bar quiet there to avoid corrupting the
        # report. In --fix nothing per-post is printed, so the bar can show.
        silent = (not fix) or verbosity == 0
        message = 'Re-rendering affected posts' if fix else 'Scanning posts'

        affected = 0
        skipped = 0
        processed = 0
        for post in ProgressBar(posts.iterator(), count, message, silent=silent):
            if limit is not None and processed >= limit:
                break
            processed += 1
            try:
                stale, fresh_html = self.find_stale_anchors(post)
                if not stale:
                    continue
                affected += 1
                if fix:
                    # Reuse the render already computed for detection so the
                    # fix stores exactly what flagged the post - and to avoid
                    # rendering the same post a second time.
                    post.html = fresh_html
                    post.summary = post.get_snippet()
                    Post.objects.filter(pk=post.pk).update(
                        html=post.html, summary=post.summary)
                else:
                    self.report_post(post, stale)
            except Exception as error: #pylint: disable=broad-except
                skipped += 1
                print(f'could not process post {post.id}, {error}')

        self.print_summary(fix, affected, skipped)

    def find_stale_anchors(self, post):
        """Returns the offending (text, href) anchors and the fresh render.

        The fresh HTML is returned so --fix can persist it without rendering
        the post a second time.
        """
        fresh_html = post.parse_post_text()['html']
        removed = extract_anchors(post.html) - extract_anchors(fresh_html)
        stale = [(text, href) for (text, href) in removed
                 if is_stale_bare_autolink(text, href, post.text)]
        return stale, fresh_html

    def report_post(self, post, stale):
        """Prints one affected post and its offending anchors."""
        print(f'post {post.id} ({post.post_type}):')
        for text, href in stale:
            print(f'    {text} -> {href}')

    def print_summary(self, fix, affected, skipped):
        """Prints the final counts."""
        if fix:
            print(f'{affected} posts re-rendered')
        else:
            print(f'{affected} posts with stale auto-links')
        if skipped:
            print(f'{skipped} posts skipped as un-renderable')
