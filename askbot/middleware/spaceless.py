"""
Middleware that strips whitespace between html tags
copied from David Cramer's blog
http://www.davidcramer.net/code/369/spaceless-html-in-django.html
"""
import re
from django.utils.functional import allow_lazy
from django.utils.encoding import force_unicode

def reduce_spaces_between_tags(value):
    """Returns the given HTML with all spaces between tags removed.
    ,but one. One space is left so that consecutive links and other things
    do not appear glued together
    slight mod of django.utils.html import strip_spaces_between_tags
    """
    return re.sub(r'>\s+<', '> <', force_unicode(value))
reduce_spaces_between_tags = allow_lazy(reduce_spaces_between_tags, unicode)

class SpacelessMiddleware(object):
    def process_response(self, request, response):
        """strips whitespace from all documents
        whose content type is text/html
        """
        if 'text/html' in response['Content-Type']:
            response.content = reduce_spaces_between_tags(response.content)
            response['Content-Length'] = str(len(response.content))
        return response
