import re
import logging
from askbot import const
from askbot.conf import settings as askbot_settings
from markdown2 import Markdown

#url taken from http://regexlib.com/REDetails.aspx?regexp_id=501 by Brian Bothwell
URL_RE = re.compile("((?<!(href|.src|data)=['\"])((http|https|ftp)\://([a-zA-Z0-9\.\-]+(\:[a-zA-Z0-9\.&amp;%\$\-]+)*@)*((25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9])\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[0-9])|localhost|([a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+\.(com|edu|gov|int|mil|net|org|biz|arpa|info|name|pro|aero|coop|museum|[a-zA-Z]{2}))(\:[0-9]+)*(/($|[a-zA-Z0-9\.\,\?\'\\\+&amp;%\$#\=~_\-]+))*))")

LINK_PATTERNS = [
    (URL_RE, r'\1'),
]


def get_parser():
    extras = ['link-patterns', 'video']  
    if askbot_settings.ENABLE_MATHJAX or \
        askbot_settings.MARKUP_CODE_FRIENDLY:
        extras.append('code-friendly')

    if askbot_settings.ENABLE_VIDEO_EMBEDDING:
        #note: this requires a forked version of markdown2 module
        #pip uninstall markdown2
        #pip install -e git+git://github.com/andryuha/python-markdown2.git
        extras.append('video')

    if askbot_settings.ENABLE_AUTO_LINKING:
        pattern_list = askbot_settings.PATTERN.split('\n')
        url_list = askbot_settings.AUTO_LINK_URL.split('\n')
        
        # Check whether  we have matching links for all key terms, Other wise we ignore the key terms
        # May be we should do this test in update_callback?
        if len(pattern_list) == len(url_list):
            for i in range(0,len(pattern_list)):
                LINK_PATTERNS.append((re.compile(pattern_list[i].strip()),url_list[i].strip()))
        else:
            settings_url = askbot_settings.APP_URL+'/settings/AUTOLINK/'
            logging.debug("Number of keyterms didn't match the number of links, fix this by visiting" + settings_url) 
            
            
    return Markdown(
                html4tags=True,
                extras=extras,
                link_patterns = LINK_PATTERNS
            )


def format_mention_in_html(mentioned_user):
    url = mentioned_user.get_profile_url()
    username = mentioned_user.username
    return '<a href="%s">@%s</a>' % (url, username)

def extract_first_matching_mentioned_author(text, anticipated_authors):

    if len(text) == 0:
        return None, ''

    for a in anticipated_authors:
        if text.lower().startswith(a.username.lower()):
            ulen = len(a.username)
            if len(text) == ulen:
                text = ''
            elif text[ulen] in const.TWITTER_STYLE_MENTION_TERMINATION_CHARS:
                text = text[ulen:]
            else:
                #near miss, here we could insert a warning that perhaps
                #a termination character is needed
                continue
            return a, text
    return None, text

def extract_mentioned_name_seeds(text):
    extra_name_seeds = set()
    while '@' in text:
        pos = text.index('@')
        text = text[pos+1:]#chop off prefix
        name_seed = ''
        for c in text:
            if c in const.TWITTER_STYLE_MENTION_TERMINATION_CHARS:
                extra_name_seeds.add(name_seed)
                name_seed = ''
                break
            if len(name_seed) > 10:
                extra_name_seeds.add(name_seed)
                name_seed = ''
                break
            if c == '@':
                if len(name_seed) > 0:
                    extra_name_seeds.add(name_seed)
                    name_seed = ''
                break
            name_seed += c
        if len(name_seed) > 0:
            #in case we run off the end of text
            extra_name_seeds.add(name_seed)

    return extra_name_seeds

def mentionize_text(text, anticipated_authors):
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
