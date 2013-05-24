"""defines the method for building slugs
slugification may be disabled with a live setting "USE_ASCII_ONLY_SLUGS"

the setting was added just in case - if people actually
want to see unicode characters in the slug. If this is the choice
slug will be simply equal to the input text
"""
import re
import unicodedata
from unidecode import unidecode

from django.conf import settings
from django.template import defaultfilters
from django.utils.encoding import smart_unicode


# Extra characters outside of alphanumerics that we'll allow.
SLUG_OK = '-_~'


def unicode_slugify(s, ok=SLUG_OK, lower=True, spaces=False):
    """Function copied from https://github.com/mozilla/unicode-slugify
    because the author of the package never published it on pypi.

    Copyright notice below applies just to this function
    Copyright (c) 2011, Mozilla Foundation
    All rights reserved.

    L and N signify letter/number.
    http://www.unicode.org/reports/tr44/tr44-4.html#GC_Values_Table
    """
    rv = []
    for c in unicodedata.normalize('NFKC', smart_unicode(s)):
        cat = unicodedata.category(c)[0]
        if cat in 'LN' or c in ok:
            rv.append(c)
        if cat == 'Z':  # space
            rv.append(' ')
    new = ''.join(rv).strip()
    if not spaces:
        new = re.sub('[-\s]+', '-', new)
    return new.lower() if lower else new


def slugify(input_text, max_length=150):
    """custom slugify function that
    removes diacritic modifiers from the characters
    """
    if input_text == '':
        return input_text

    allow_unicode_slugs = getattr(settings, 'ALLOW_UNICODE_SLUGS', False)
    if isinstance(input_text, unicode) and not allow_unicode_slugs:
        input_text = unidecode(input_text)

    if isinstance(input_text, unicode):
        slug = unicode_slugify(input_text)
    else:
        slug = defaultfilters.slugify(input_text)
    while len(slug) > max_length:
        # try to shorten word by word until len(slug) <= max_length
        temp = slug[:slug.rfind('-')]
        if len(temp) > 0:
            slug = temp
        else:
            #we have nothing left, do not apply the last crop,
            #apply the cut-off directly
            slug = slug[:max_length]
            break
    return slug
