"""methods that make parsing of post inputs possible,
handling of markdown and additional syntax rules - 
such as optional link patterns, video embedding and 
Twitter-style @mentions"""

import re
import logging
from askbot import const
from askbot.conf import settings as askbot_settings
from markdown2 import Markdown
#url taken from http://regexlib.com/REDetails.aspx?regexp_id=501 by Brian Bothwell
URL_RE = re.compile("((?<!(href|.src|data)=['\"])((http|https|ftp)\://([a-zA-Z0-9\.\-]+(\:[a-zA-Z0-9\.&amp;%\$\-]+)*@)*((25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9])\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[0-9])|localhost|([a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+\.(com|edu|gov|int|mil|net|org|biz|arpa|info|name|pro|aero|coop|museum|[a-zA-Z]{2}))(\:[0-9]+)*(/($|[a-zA-Z0-9\.\,\?\'\\\+&amp;%\$#\=~_\-]+))*))")

def get_parser():
    """returns an instance of configured ``markdown2`` parser
    """
    extras = ['link-patterns', 'video']  

    if askbot_settings.ENABLE_MATHJAX or \
        askbot_settings.MARKUP_CODE_FRIENDLY:
        extras.append('code-friendly')

    if askbot_settings.ENABLE_VIDEO_EMBEDDING:
        #note: this requires a forked version of markdown2 module
        #pip uninstall markdown2
        #pip install -e git+git://github.com/andryuha/python-markdown2.git
        extras.append('video')

    link_patterns = [
        (URL_RE, r'\1'),
    ]
    if askbot_settings.ENABLE_AUTO_LINKING:
        pattern_list = askbot_settings.AUTO_LINK_PATTERNS.split('\n')
        url_list = askbot_settings.AUTO_LINK_URLS.split('\n')
        pairs = zip(pattern_list, url_list)#always takes equal number of items 
        for item in pairs:
            if item[0].strip() =='' or item[1].strip() == '':
                continue
            link_patterns.append(
                (
                    re.compile(item[0].strip()),
                    item[1].strip()
                )
            )
        
        #Check whether  we have matching links for all key terms,
        #Other wise we ignore the key terms
        #May be we should do this test in update_callback?
        #looks like this might be a defect of livesettings
        #as there seems to be no way
        #to validate entries that depend on each other
        if len(pattern_list) != len(url_list):
            settings_url = askbot_settings.APP_URL+'/settings/AUTOLINK/'
            logging.critical(
                "Number of autolink patterns didn't match the number "
                "of url templates, fix this by visiting" + settings_url) 
            
    return Markdown(
                html4tags=True,
                extras=extras,
                link_patterns = link_patterns
            )


def format_mention_in_html(mentioned_user):
    """formats mention as url to the user profile"""
    url = mentioned_user.get_profile_url()
    username = mentioned_user.username
    return '<a href="%s">@%s</a>' % (url, username)

def extract_first_matching_mentioned_author(text, anticipated_authors):
    """matches beginning of ``text`` string with the names
    of ``anticipated_authors`` - list of user objects.
    Returns upon first match the first matched user object
    and the remainder of the ``text`` that is left unmatched"""

    if len(text) == 0:
        return None, ''

    for author in anticipated_authors:
        if text.lower().startswith(author.username.lower()):
            ulen = len(author.username)
            if len(text) == ulen:
                text = ''
            elif text[ulen] in const.TWITTER_STYLE_MENTION_TERMINATION_CHARS:
                text = text[ulen:]
            else:
                #near miss, here we could insert a warning that perhaps
                #a termination character is needed
                continue
            return author, text
    return None, text

def extract_mentioned_name_seeds(text):
    """Returns list of strings that
    follow the '@' symbols in the text.
    The strings will be 10 characters long,
    or shorter, if the subsequent character
    is one of the list accepted to be termination
    characters.
    """
    extra_name_seeds = set()
    while '@' in text:
        pos = text.index('@')
        text = text[pos+1:]#chop off prefix
        name_seed = ''
        for char in text:
            if char in const.TWITTER_STYLE_MENTION_TERMINATION_CHARS:
                extra_name_seeds.add(name_seed)
                name_seed = ''
                break
            if len(name_seed) > 10:
                extra_name_seeds.add(name_seed)
                name_seed = ''
                break
            if char == '@':
                if len(name_seed) > 0:
                    extra_name_seeds.add(name_seed)
                    name_seed = ''
                break
            name_seed += char
        if len(name_seed) > 0:
            #in case we run off the end of text
            extra_name_seeds.add(name_seed)

    return extra_name_seeds

def mentionize_text(text, anticipated_authors):
    """Returns a tuple of two items:
    * modified text where @mentions are
      replaced with urls to the corresponding user profiles
    * list of users whose names matched the @mentions
    """
    output = ''
    mentioned_authors = list()
    while '@' in text:
        #the purpose of this loop is to convert any occurance of 
        #'@mention ' syntax
        #to user account links leading space is required unless @ is the first
        #character in whole text, also, either a punctuation or 
        #a ' ' char is required after the name
        pos = text.index('@')

        #save stuff before @mention to the output
        output += text[:pos]#this works for pos == 0 too

        if len(text) == pos + 1:
            #finish up if the found @ is the last symbol
            output += '@'
            text = ''
            break

        if pos > 0:

            if text[pos-1] in const.TWITTER_STYLE_MENTION_TERMINATION_CHARS:
                #if there is a termination character before @mention
                #indeed try to find a matching person
                text = text[pos+1:]
                mentioned_author, text = \
                                    extract_first_matching_mentioned_author(
                                                            text, 
                                                            anticipated_authors
                                                        )
                if mentioned_author:
                    mentioned_authors.append(mentioned_author)
                    output += format_mention_in_html(mentioned_author)
                else:
                    output += '@'

            else:
                #if there isn't, i.e. text goes like something@mention,
                #do not look up people
                output += '@'
                text = text[pos+1:]
        else:
            #do this if @ is the first character
            text = text[1:]
            mentioned_author, text = \
                                extract_first_matching_mentioned_author(
                                                    text, 
                                                    anticipated_authors
                                                )
            if mentioned_author:
                mentioned_authors.append(mentioned_author)
                output += format_mention_in_html(mentioned_author)
            else:
                output += '@'

    #append the rest of text that did not have @ symbols
    output += text
    return mentioned_authors, output
