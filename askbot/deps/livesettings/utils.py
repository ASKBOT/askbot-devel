import sys
import types
import os

def can_loop_over(maybe):
    """Test value to see if it is list like"""
    try:
        iter(maybe)
    except:
        return 0
    else:
        return 1

def is_list_or_tuple(maybe):
    return isinstance(maybe, (types.TupleType, types.ListType))


def is_scalar(maybe):
    """Test to see value is a string, an int, or some other scalar type"""
    return is_string_like(maybe) or not can_loop_over(maybe)

def is_string_like(maybe):
    """Test value to see if it acts like a string"""
    try:
        maybe+""
    except TypeError:
        return 0
    else:
        return 1


def flatten_list(sequence, scalarp=is_scalar, result=None):
    """flatten out a list by putting sublist entries in the main list"""
    if result is None:
        result = []

    for item in sequence:
        if scalarp(item):
            result.append(item)
        else:
            flatten_list(item, scalarp, result)

def load_module(module):
    """Load a named python module."""
    try:
        module = sys.modules[module]
    except KeyError:
        __import__(module)
        module = sys.modules[module]
    return module

def get_flat_list(sequence):
    """flatten out a list and return the flat list"""
    flat = []
    flatten_list(sequence, result=flat)
    return flat

def url_join(*args):
    """Join any arbitrary strings into a forward-slash delimited string.
    Do not strip leading / from first element, nor trailing / from last element.

    This function can take lists as arguments, flattening them appropriately.

    example:
    url_join('one','two',['three','four'],'five') => 'one/two/three/four/five'
    """
    if len(args) == 0:
        return ""

    args = get_flat_list(args)

    if len(args) == 1:
        return str(args[0])

    else:
        args = [str(arg).replace("\\", "/") for arg in args]

        work = [args[0]]
        for arg in args[1:]:
            if arg.startswith("/"):
                work.append(arg[1:])
            else:
                work.append(arg)

        joined = reduce(os.path.join, work)

    return joined.replace("\\", "/")
