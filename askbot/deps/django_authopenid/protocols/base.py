class BaseProtocol:
    """Base class for all authentication protocols"""

    def __iter__(self):
        """makes objects iterable and enables the 'in' operator'"""
        attrs = dir(self)
        prop_names = tuple()
        for attr in attrs:
            item = getattr(self, attr)
            if hasattr(item, '__call__'):
                continue
            prop_names += (attr,)
        return iter(prop_names)

    def __getitem__(self, key):
        """Method necessary to access parameters
        as dictionary keys.
        It is necessary to make the "old-style" 
        providers defined in the dictionary work.
        todo: remove after all providers
        are migrated to class-based
        """
        if key == 'type':
            return self.protocol_type
        return getattr(self, key)

    def __setitem__(self, key, value):
        """Method necessary to access parameters
        as dictionary keys.
        It is necessary to make the "old-style" providers.
        todo: remove after all providers
        are migrated to class-based
        """
        setattr(self, key, value)
