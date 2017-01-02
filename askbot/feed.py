"""
#-------------------------------------------------------------------------------
# Name:        Syndication feed class for subscription
# Purpose:
#
# Author:      Mike
#
# Created:     29/01/2009
# Copyright:   (c) CNPROG.COM 2009
# Licence:     GPL V2
#-------------------------------------------------------------------------------
"""
#!/usr/bin/env python
#encoding:utf-8
from django.contrib.syndication.views import Feed

import itertools
import askbot.utils.timezone

from django.conf import settings as django_settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.http import Http404
from django.utils.translation import ugettext as _

from askbot.utils.translation import get_language
from askbot.conf import settings as askbot_settings
from askbot.models import Post
from askbot.utils.html import site_url


class RssIndividualQuestionFeed(Feed):
    """rss feed class for particular questions
    """

    def title(self):
        return askbot_settings.APP_TITLE + _(' - ') + _('RSS feed')

    def feed_copyright(self):
        return askbot_settings.APP_COPYRIGHT

    def description(self):
        return askbot_settings.APP_DESCRIPTION

    def get_object(self, request, pk):
        if not askbot_settings.RSS_ENABLED:
            raise Http404
        # hack to get the request object into the Feed class
        self.request = request
        return Post.objects.get_questions().get(id__exact=pk)

    def item_link(self, item):
        """get full url to the item
        """
        return site_url(item.get_absolute_url())

    def link(self):
        return site_url(reverse('questions'))

    def item_pubdate(self, item):
        """get date of creation for the item
        """
        return askbot.utils.timezone.make_aware(item.added_at)

    def items(self, item):
        """get content items for the feed
        ordered as: question, question comments,
        then for each answer - the answer itself, then
        answer comments
        """
        chain_elements = list()
        chain_elements.append([item])

        comments_filter = {'parent': item}
        if askbot_settings.CONTENT_MODERATION_MODE == 'premoderation':
            comments_filter['approved'] = True

        chain_elements.append(
            Post.objects.get_comments().filter(**comments_filter)
        )

        answers_filter = {'thread': item.thread}
        if askbot_settings.CONTENT_MODERATION_MODE == 'premoderation':
            answers_filter['approved'] = True

        answers = Post.objects.get_answers().filter(**answers_filter)

        for answer in answers:
            chain_elements.append([answer])

            comments_filter = {'parent': answer}
            if askbot_settings.CONTENT_MODERATION_MODE == 'premoderation':
                comments_filter['approved'] = True

            chain_elements.append(
                Post.objects.get_comments().filter(**comments_filter))

        return itertools.chain(*chain_elements)

    def item_title(self, item):
        """returns the title for the item
        """
        if item.post_type == "question":
            title = item.thread.title
        elif item.post_type == "answer":
            title = u'Answer by %s for %s ' % (item.author, item.thread._question_post().summary)
        elif item.post_type == "comment":
            title = u'Comment by %s for %s' % (item.author, item.parent.summary)
        return title

    def item_description(self, item):
        """returns the description for the item
        """
        return item.text


class RssLastestQuestionsFeed(Feed):
    """rss feed class for the latest questions
    """

    def title(self):
        return askbot_settings.APP_TITLE + _(' - ') + _('RSS feed')

    def feed_copyright(self):
        return askbot_settings.APP_COPYRIGHT

    def description(self):
        return askbot_settings.APP_DESCRIPTION

    def item_link(self, item):
        """get full url to the item
        """
        return site_url(item.get_absolute_url())

    def link(self):
        return site_url(reverse('questions'))

    def item_author_name(self, item):
        """get name of author
        """
        return item.author.username

    def item_author_link(self, item):
        """get url of the author's profile
        """
        return site_url(item.author.get_profile_url())

    def item_pubdate(self, item):
        """get date of creation for the item
        """
        return askbot.utils.timezone.make_aware(item.added_at)

    def item_guid(self, item):
        """returns url without the slug
        because the slug can change
        """
        return site_url(item.get_absolute_url(no_slug=True))

    def item_title(self, item):
        return item.thread.title

    def item_description(self, item):
        """returns the description for the item
        """
        return item.text

    def items(self, item):
        """get questions for the feed
        """
        if not askbot_settings.RSS_ENABLED:
            raise Http404

        # initial filtering
        filters = {'deleted': False}
        filters['language_code'] = get_language()
        if askbot_settings.CONTENT_MODERATION_MODE == 'premoderation':
            filters['approved'] = True

        qs = Post.objects.get_questions().filter(**filters)

        # get search string and tags from GET
        query = self.request.GET.get("q", None)
        tags = self.request.GET.getlist("tags")

        if query:
            # if there's a search string, use the
            # question search method
            qs = qs.get_by_text_query(query)

        if tags:
            # if there are tags in GET, filter the
            # questions additionally
            for tag in tags:
                qs = qs.filter(thread__tags__name=tag)

        return qs.order_by('-thread__last_activity_at')[:30]

    # hack to get the request object into the Feed class
    def get_feed(self, obj, request):
        self.request = request
        return super(RssLastestQuestionsFeed, self).get_feed(obj, request)
