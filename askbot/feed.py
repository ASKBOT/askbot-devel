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
import itertools

from django.contrib.syndication.feeds import Feed
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext as _
from django.core.exceptions import ObjectDoesNotExist

from askbot.models import Post
from askbot.conf import settings as askbot_settings

class RssIndividualQuestionFeed(Feed):
    """rss feed class for particular questions
    """
    title = askbot_settings.APP_TITLE + _(' - ')+ _('Individual question feed')
    link = askbot_settings.APP_URL
    description = askbot_settings.APP_DESCRIPTION
    copyright = askbot_settings.APP_COPYRIGHT

    def get_object(self, bits):
        if len(bits) != 1:
            raise ObjectDoesNotExist
        return Post.objects.get_questions().get(id__exact = bits[0])
    
    def item_link(self, item):
        """get full url to the item
        """
        return self.link + item.get_absolute_url()

    def item_pubdate(self, item):
        """get date of creation for the item
        """
        return item.added_at

    def items(self, item):
        """get content items for the feed
        ordered as: question, question comments,
        then for each answer - the answer itself, then
        answer comments
        """
        chain_elements = list()
        chain_elements.append([item,])
        chain_elements.append(
            Post.objects.get_comments().filter(parent=item)
        )
        
        answers = Post.objects.get_answers().filter(thread = item.thread)
        for answer in answers:
            chain_elements.append([answer,])
            chain_elements.append(
                Post.objects.get_comments().filter(parent=answer)
            )

        return itertools.chain(*chain_elements)
    
    def item_title(self, item):
        """returns the title for the item
        """
        title = item
        if item.post_type == "question":
            self.title = item
        elif item.post_type == "answer":
            title = "Answer by %s for %s " % (item.author, self.title)
        elif item.post_type == "comment":
            title = "Comment by %s for %s" % (item.author, self.title)
        return title
        
    def item_description(self, item):
        """returns the description for the item
        """
        return item.text


class RssLastestQuestionsFeed(Feed):
    """rss feed class for the latest questions
    """
    title = askbot_settings.APP_TITLE + _(' - ')+ _('latest questions')
    link = askbot_settings.APP_URL
    description = askbot_settings.APP_DESCRIPTION
    #ttl = 10
    copyright = askbot_settings.APP_COPYRIGHT

    def item_link(self, item):
        """get full url to the item
        """
        return self.link + item.get_absolute_url()

    def item_author_name(self, item):
        """get name of author
        """
        return item.author.username

    def item_author_link(self, item):
        """get url of the author's profile
        """
        return item.author.get_profile_url()

    def item_pubdate(self, item):
        """get date of creation for the item
        """
        return item.added_at

    def item_guid(self, item):
        """returns url without the slug
        because the slug can change
        """
        return self.link + item.get_absolute_url(no_slug = True)
        
    def item_description(self, item):
        """returns the desciption for the item
        """
        return item.text

    def items(self, item):
        """get questions for the feed
        """
        #initial filtering
        qs = Post.objects.get_questions().filter(deleted=False)

        #get search string and tags from GET
        query = self.request.GET.get("q", None)
        tags = self.request.GET.getlist("tags")

        if query:
            #if there's a search string, use the
            #question search method
            qs = qs.get_by_text_query(query)

        if tags:
            #if there are tags in GET, filter the
            #questions additionally
            for tag in tags:                
                qs = qs.filter(thread__tags__name = tag)
        
        return qs.order_by('-thread__last_activity_at')[:30]

        

def main():
    """main function for use as a script
    """
    pass

if __name__ == '__main__':
    main()
