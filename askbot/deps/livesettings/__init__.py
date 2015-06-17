"""Database persistent administrative settings with defaults.

This code is a large fork of the excellent "dbsettings" code found at
http://code.google.com/p/django-values/

The items set here are intended to be changeable during runtime, and do not require a
programmer to test or install.

Appropriate:  Your google code for adwords.
Inappropriate: The keyedcache timeout for the store.

"""

from functions import *
from models import *
from values import *
