"""Search state manager object"""
import re
import urllib
import copy

from django.core import urlresolvers
from django.utils.http import urlencode
from django.utils.encoding import smart_str

import askbot
import askbot.conf
from askbot.conf import settings as askbot_settings
from askbot import const
from askbot.utils.functions import strip_plus


def extract_matching_token(text, regexes):
    """if text matches any of the regexes,
    * the entire match is removed from text
    * repeating spaces in the remaining string are replaced with one
    * returned is a tuple of: first group from the regex, remaining text
    """
    for regex in regexes:
        m = regex.search(text)
        if m:
            text = regex.sub('', text)
            extracted_match = m.group(1)
            return (strip_plus(extracted_match), strip_plus(text))
    return ('', text.strip())

def extract_all_matching_tokens(text, regexes):
    """the same as the ``extract_matching_token``
    but returns a tuple of: list of first group matches from the regexes
    and the remains of the input text
    """
    matching_tokens = set()
    for regex in regexes:
        matches = regex.findall(text)
        if len(matches) > 0:
            text = regex.sub('', text)
            matching_tokens.update([match.strip() for match in matches])
    return ([strip_plus(token) for token in matching_tokens], strip_plus(text))


def parse_query(query):
    """takes hand-typed search query string as an argument
    returns a dictionary with keys (and values in parens):
    * stripped_query (query with the items below stripped)
    * query_tags (list of tag names)
    * query_users (list of user names, not validated)
    * query_title (question title)
    Note: the stripped_query is the actual string
    against which global search will be performed
    the original query will still all be shown in the search
    query input box
    """
    title_re1 = re.compile(r'\[title:(.+?)\]')
    title_re2 = re.compile(r'title:"([^"]+?)"')
    title_re3 = re.compile(r"title:'([^']+?)'")
    title_regexes = (title_re1, title_re2, title_re3)
    (query_title, query) = extract_matching_token(query, title_regexes)

    tag_re1 = re.compile(r'\[([^:]+?)\]')
    tag_re2 = re.compile(r'\[tag:\s*([\S]+)\s*]')
    tag_re3 = re.compile(r'#(\S+)')
    tag_regexes = (tag_re1, tag_re2, tag_re3)
    (query_tags, query) = extract_all_matching_tokens(query, tag_regexes)

    user_re1 = re.compile(r'\[user:([^\]]+?)\]')
    user_re2 = re.compile(r'user:"([^"]+?)"')
    user_re3 = re.compile(r"user:'([^']+?)'")
    user_re4 = re.compile(r"""@([^'"\s]+)""")
    user_re5 = re.compile(r'@"([^"]+)"')
    user_re6 = re.compile(r"@'([^']+)'")
    user_regexes = (user_re1, user_re2, user_re3, user_re4, user_re5, user_re6)
    (query_users, stripped_query) = extract_all_matching_tokens(query, user_regexes)

    return {
        'stripped_query': stripped_query,
        'query_title': query_title,
        'query_tags': query_tags,
        'query_users': query_users
    }

class SearchState(object):

    @classmethod
    def get_empty(cls):
        return cls(scope=None, sort=None, query=None, tags=None, author=None, page=None, page_size=None, user_logged_in=None)

    def __init__(self,
        scope=None, sort=None, query=None, tags=None,
        author=None, page=None, page_size=None, user_logged_in=False
    ):
        # INFO: zip(*[('a', 1), ('b', 2)])[0] == ('a', 'b')
        if (scope not in zip(*const.POST_SCOPE_LIST)[0]) or (scope == 'followed' and not user_logged_in):
            if user_logged_in:
                self.scope = askbot_settings.DEFAULT_SCOPE_AUTHENTICATED
            else:
                self.scope = askbot_settings.DEFAULT_SCOPE_ANONYMOUS
        else:
            self.scope = scope

        self.query = query.strip() if query else None

        if self.query:
            #pull out values of [title:xxx], [user:some one]
            #[tag: sometag], title:'xxx', title:"xxx", @user, @'some user',
            #and  #tag - (hash symbol to delineate the tag
            query_bits = parse_query(self.query)
            self.stripped_query = query_bits['stripped_query']
            self.query_tags = query_bits['query_tags']
            self.query_users = query_bits['query_users']
            self.query_title = query_bits['query_title']
        else:
            self.stripped_query = None
            self.query_tags = None
            self.query_users = None
            self.query_title = None

        if (sort not in zip(*const.POST_SORT_METHODS)[0]) or (sort == 'relevance-desc' and (not self.query or not askbot.conf.should_show_sort_by_relevance())):
            self.sort = const.DEFAULT_POST_SORT_METHOD
        else:
            self.sort = sort

        #patch for empty stripped query, relevance sorting is useless then
        if self.stripped_query in (None, '') and sort == 'relevance-desc':
            self.sort = const.DEFAULT_POST_SORT_METHOD

        self.tags = []
        if tags:
            for t in tags.split(const.TAG_SEP):
                tag = t.strip()
                if tag not in self.tags:
                    self.tags.append(tag)

        self.author = int(author) if author else None
        self.page = int(page) if page else 1
        if self.page == 0:  # in case someone likes jokes :)
            self.page = 1

        default_page_size = int(askbot_settings.DEFAULT_QUESTIONS_PAGE_SIZE)
        self.page_size = int(page_size) if page_size else default_page_size

        self._questions_url = urlresolvers.reverse('questions')

    def __str__(self):
        return self.query_string()

    def full_url(self):
        return self._questions_url + self.query_string()

    def ask_query_string(self): # TODO: test me
        """returns string to prepopulate title field on the "Ask your question" page"""
        ask_title = self.stripped_query or self.query or ''
        if not ask_title:
            return ''
        return '?' + urlencode({'title': ask_title})

    def full_ask_url(self):
        return urlresolvers.reverse('ask') + self.ask_query_string()

    def unified_tags(self):
        "Returns tags both from tag selector and extracted from query"
        return (self.query_tags or []) + (self.tags or [])

    #
    # Safe characters in urlquote() according to http://www.ietf.org/rfc/rfc1738.txt:
    #
    #    Thus, only alphanumerics, the special characters "$-_.+!*'(),", and
    #    reserved characters used for their reserved purposes may be used
    #    unencoded within a URL.
    #
    # Tag separator (const.TAG_SEP) remains unencoded to clearly mark tag boundaries
    # _+.- stay unencoded to keep tags in URL as verbose as possible
    #      (note that urllib.quote() in Python 2.7 treats _.- as safe chars, but let's be explicit)
    # Hash (#) is not safe and has to be encodeded, as it's used as URL has delimiter
    #
    SAFE_CHARS = const.TAG_SEP + '_+.-'

    def query_string(self):
        """returns part of the url to the main page,
        responsible to display the full text search results,
        taking into account sort method, selected scope
        and search tags"""

        lst = [
            'scope:' + self.scope,
            'sort:' + self.sort
        ]

        """
            ATTN: a copy from urls.py
            r'(%s)?' % r'/scope:(?P<scope>\w+)' +
            r'(%s)?' % r'/sort:(?P<sort>[\w\-]+)' +
            r'(%s)?' % r'/tags:(?P<tags>[\w+.#,-]+)' + # Should match: const.TAG_CHARS + ','; TODO: Is `#` char decoded by the time URLs are processed ??
            r'(%s)?' % r'/author:(?P<author>\d+)' +
            r'(%s)?' % r'/page:(?P<page>\d+)' +
            r'(%s)?' % r'/query:(?P<query>.+)' +  # INFO: query is last, b/c it can contain slash!!!
        """

        #order of items is important!!!
        if self.tags:
            lst.append('tags:' + urllib.quote(smart_str(const.TAG_SEP.join(self.tags)), safe=self.SAFE_CHARS))
        if self.author:
            lst.append('author:' + str(self.author))
        if self.page:
            lst.append('page:' + str(self.page))
        if self.query:
            lst.append('query:' + urllib.quote(smart_str(self.query), safe=self.SAFE_CHARS))
        return '/'.join(lst) + '/'

    def deepcopy(self): # TODO: test me
        "Used to contruct a new SearchState for manipulation, e.g. for adding/removing tags"
        ss = copy.copy(self) #SearchState.get_empty()

        #ss.scope = self.scope
        #ss.sort = self.sort
        #ss.query = self.query
        if ss.tags is not None: # it's important to test against None, because empty lists should also be cloned!
            ss.tags = ss.tags[:]  # create a copy
        #ss.author = self.author
        #ss.page = self.page

        #ss.stripped_query = self.stripped_query
        if ss.query_tags: # Here we don't have empty lists, only None
            ss.query_tags = ss.query_tags[:]
        if ss.query_users:
            ss.query_users = ss.query_users[:]
        #ss.query_title = self.query_title

        #ss._questions_url = self._questions_url

        return ss

    def add_tag(self, tag):
        ss = self.deepcopy()
        if tag not in ss.tags:
            ss.tags.append(tag)
            ss.page = 1 # state change causes page reset
        return ss

    def remove_author(self):
        ss = self.deepcopy()
        ss.author = None
        ss.page = 1
        return ss

    def remove_tags(self, tags = None):
        ss = self.deepcopy()
        if tags:
            ss.tags = list(
                set(ss.tags) - set(tags)
            )
        else:
            ss.tags = []
        ss.page = 1
        return ss

    def change_scope(self, new_scope):
        ss = self.deepcopy()
        ss.scope = new_scope
        ss.page = 1
        return ss

    def change_sort(self, new_sort):
        ss = self.deepcopy()
        ss.sort = new_sort
        ss.page = 1
        return ss

    def change_page(self, new_page):
        ss = self.deepcopy()
        ss.page = new_page
        return ss


class DummySearchState(object): # Used for caching question/thread summaries

    def add_tag(self, tag):
        self.tag = tag
        return self

    def change_scope(self, new_scope):
        return self

    def full_url(self):
        return '<<<%s>>>' % self.tag
