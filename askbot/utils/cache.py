"""Cache utilities"""
from django.core.cache import cache
import functools
import inspect
from django.db.models import Model

def django_repr(obj):
    """repr that reliably identifies instances django db models,
    including "deferred" objects"""
    if isinstance(obj, Model):
        if obj._deferred:
            cls = repr(obj._meta.proxy_for_model)
        else:
            cls = repr(obj.__class__)
        return cls + ',id=' + repr(obj.id)
    return repr(obj)


def get_args_key(*args):
    return ':'.join(map(lambda v: django_repr(v), args))


def get_kwargs_key(**kwargs):
    key = get_args_key(*kwargs.values())
    return key or ''
    #todo: delete above line when args and kwargs resolution is fixed
    items = kwargs.items()
    items = map(lambda v: (django_repr(v[0]), django_repr(v[1])), items)
    items.sort(items)
    return ':'.join(map(lambda v: v[0] + '=' + v[1], items))


def make_cache_key(func, *args, **kwargs):
    """returns cache key for a function and the full set of its arguments"""
    bits = [func.__name__,]
    #todo: make proper resolution of args and kwargs
    #as it is possible to mask kwarg as arg
    args_key = get_args_key(*args)
    if args_key:
        bits.append(args_key)
    kwargs_key = get_kwargs_key(**kwargs)
    if kwargs_key:
        bits.append(kwargs_key)
    return ':'.join(bits).replace(' ', '')


def get_recached(key, func, *args, **kwargs):
    """calculates result of the function, caches the result
    and returns the same result"""
    val = func(*args, **kwargs)
    cache.set(key, val)
    return val


def memoize(func):
    """decorator that will automatically cache
    results of the function call
    """
    @functools.wraps(func)
    def decorated(*args, **kwargs):
        key = make_cache_key(func, *args, **kwargs)
        return cache.get(key) or get_recached(key, func, *args, **kwargs)
    return decorated


def delete_memoized(func, *args, **kwargs):
    """deletes cached result of the function"""
    key = make_cache_key(func, *args, **kwargs)
    cache.delete(key)
