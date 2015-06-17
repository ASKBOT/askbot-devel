"""Utilities for loading modules"""
from django.conf import settings as django_settings

def load_module(mod_path):
    """an equivalent of:
    from some.where import module
    import module

    TODO: is this the same as the following?
    try:
        from django.utils.module_loading import import_string
    except ImportError:
        from django.utils.module_loading import import_by_path as import_string
    """
    assert(mod_path[0] != '.')
    path_bits = mod_path.split('.')
    if len(path_bits) > 1:
        mod_name = path_bits.pop()
        mod_prefix = '.'.join(path_bits)
        _mod = __import__(mod_prefix, globals(), locals(), [mod_name,], -1)
        return getattr(_mod, mod_name)
    else:
        return __import__(mod_path, globals(), locals(), [], -1)


def load_plugin(setting_name, default_path):
    """loads custom module/class/function
    provided with setting with the fallback
    to the default module/class/function"""
    python_path = getattr(
                        django_settings,
                        setting_name,
                        default_path
                    )
    return load_module(python_path)
