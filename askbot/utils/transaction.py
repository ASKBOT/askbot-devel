"""Utilities for working with database transactions"""
from django.conf import settings as django_settings
#from django.core.signals import request_finished

class DummyTransaction:
    """Dummy transaction class
    that can be imported instead of the django
    transaction management and debug issues
    inside the code running inside the transaction blocks
    """
    @classmethod
    def commit(cls):
        pass


#a utility instance to use instead of the normal transaction object
dummy_transaction = DummyTransaction()
