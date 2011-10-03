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
from django.contrib.syndication.feeds import Feed
from django.utils.translation import ugettext as _
from django.core.exceptions import ObjectDoesNotExist
from askbot.models import Question, Answer, Comment
from askbot.conf import settings as askbot_settings
import itertools

class RssParticularQuestionFeed(Feed):
    """rss feed class for particular questions
    """
    title = askbot_settings.APP_TITLE + _(' - ')+ _('Particular Question')
    link = askbot_settings.APP_URL
    description = askbot_settings.APP_DESCRIPTION
    copyright = askbot_settings.APP_COPYRIGHT

    def get_object(self, bits):
        if len(bits) != 1:
            raise ObjectDoesNotExist
        return Question.objects.get(id__exact = bits[0])
    
    def item_link(self, item):
        """get full url to the item
        """
        return self.link + item.get_absolute_url()

    def item_pubdate(self, item):
        """get date of creation for the item
        """
        return item.added_at

    def items(self, item):
        """get questions for the feed
	"""
        results = itertools.chain(
                              Question.objects.filter(id = item.id),
                              Answer.objects.filter(question = item.id),
                              Comment.objects.filter(question = item.id),
                              )
        return results
    
    def item_title(self, item):
	"""returns the title for the item
	"""
        title = item
        if item.__class__.__name__ == "Question":
            self.title = item
        elif item.__class__.__name__ == "Answer":
            title = "Answer by %s for %s " %(item.author,self.title)
        elif item.__class__.__name__ == "Comment":
            title = "Comment by %s for %s" %(item.user,self.title)
        return title
        
    def item_description(self,item):
	"""returns the description for the item
	"""
	if item.__class__.__name__ == "Question":
            return item.text
        if item.__class__.__name__ == "Answer":
            return item.text
        elif item.__class__.__name__ == "Comment":
            return item.comment

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
        return Question.objects.filter(
                                    deleted=False
                                ).order_by(
                                    '-last_activity_at'
                                )[:30]

def main():
    """main function for use as a script
    """
    pass

if __name__ == '__main__':
    main()
