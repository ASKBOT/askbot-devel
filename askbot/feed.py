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
from django.urls import reverse
from django.http import Http404
from django.utils.translation import gettext as _

from askbot.utils.translation import get_language
from askbot.conf import settings as askbot_settings
from askbot.models import Post
from askbot.utils.html import site_url

def get_content_filter():
    if askbot_settings.CONTENT_MODERATION_MODE == 'premoderation':
        return {'approved': True}
    return {}

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
        question = Post.objects.get_questions().get(id__exact = pk)
        if askbot_settings.CONTENT_MODERATION_MODE == 'premoderation':
            if question.approved == False:
                raise Http404
        return question

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
        base_filter = get_content_filter()
        comment_filter = base_filter.copy()
        comment_filter['parent'] = item
        chain_elements.append(Post.objects.get_comments().filter(**comment_filter))

        answer_filter = base_filter.copy()
        answer_filter['thread'] = item.thread
        answer_filter['deleted'] = False
        answers = Post.objects.get_answers().filter(**answer_filter)

        for answer in answers:
            chain_elements.append([answer,])
            comment_filter = base_filter.copy()
            comment_filter['parent'] = answer
            chain_elements.append(Post.objects.get_comments().filter(**comment_filter))

        return itertools.chain(*chain_elements)

    def item_title(self, item):
        """returns the title for the item
        """
        if item.post_type == "question":
            title = item.thread.title
        elif item.post_type == "answer":
            title = f'Answer by {item.author} for {item.thread._question_post().summary} '
        elif item.post_type == "comment":
            title = f'Comment by {item.author} for {item.parent.summary}'
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

        #initial filtering
        filters = get_content_filter()
        filters['deleted'] = False
        filters['language_code'] = get_language()

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
        return super().get_feed(obj, request)
