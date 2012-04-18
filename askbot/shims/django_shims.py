"""shims for django objects of different versions
only functionality that is necessary is implemented"""
import django

class ResolverMatch(object):
    """a shim for the ResolverMatch, implemented
    since django 1.3
    before the match result was a three-tuple
    """
    def __init__(self, resolver_match):
        self.resolver_match = resolver_match

    def _get_func(self):
        """the getter function for the
        ``func`` property
        """
        if django.VERSION[1] < 3:
            return self.resolver_match[0]
        else:
            return self.resolver_match.func

    func = property(_get_func)
