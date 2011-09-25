"""
This file must hold keys for translatable messages
that are used as variables
it is important that a dummy _() function is used here
this way message key will be pulled into django.po
and can still be used as a variable in python files
"""
_ = lambda v:v

#NOTE: all strings must be explicitly put into this dictionary,
#because you don't want to import _ from here with import *
__all__ = []

#messages loaded in the templates via direct _ calls
_('most relevant questions')
_('click to see most relevant questions')
_('by relevance')
_('click to see the oldest questions')
_('by date')
_('click to see the newest questions')
_('click to see the least recently updated questions')
_('by activity')
_('click to see the most recently updated questions')
_('click to see the least answered questions')
_('by answers')
_('click to see the most answered questions')
_('click to see least voted questions')
_('by votes')
_('click to see most voted questions')
