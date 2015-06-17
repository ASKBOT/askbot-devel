"""module for monkey patching that is
necessary for interoperability of different
versions of various components used in askbot
"""
import django
from askbot.patches import django_patches
from askbot.deployment import package_utils

def patch_django():
    """earlier versions of Django do not have
    csrf token and function called import_library
    (the latter is needed by coffin)
    """
    (major, minor, micro) = package_utils.get_django_version()
    if major == 1 and minor < 2:
        django_patches.add_import_library_function()
        django_patches.add_csrf_protection()
        django_patches.add_available_attrs_decorator()

    if major == 1 and minor <=2:
        django_patches.add_render_shortcut()

    if major == 1 and minor > 4:
        # This shouldn't be required with django < 1.4.x
        # And not after kee_lazy lands in django.utils.functional
        try:
            from django.utils.functional import keep_lazy
        except ImportError:
            django_patches.fix_lazy_double_escape()

def patch_coffin():
    """coffin before version 0.3.4
    does not have csrf_token template tag.
    This patch must be applied after the django patches
    """
    from askbot.patches import coffin_patches

    (major, minor, micro) = package_utils.get_coffin_version()
    if major == 0 and minor == 3 and micro < 4:
        coffin_patches.add_csrf_token_tag()
