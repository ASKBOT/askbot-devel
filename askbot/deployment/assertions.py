"""assertions regarding deployment of askbot
todo: move here stuff from startup_procedures.py

the reason - some assertions need to be run in askbot/__init__
as opposed to startup_procedures.py - which are executed in the
beginning of the models module
"""
from askbot.deployment import package_utils
from askbot.exceptions import DeploymentError

def assert_package_compatibility():
    """raises an exception if any known incompatibilities
    are found
    """
    (django_major, django_minor, django_micro) = \
        package_utils.get_django_version()
    if django_major < 1:
        raise DeploymentError('Django version < 1.0 is not supported by askbot')

    coffin_version = package_utils.get_coffin_version()
    if coffin_version == (0, 3, 0) and django_major == 1 and django_minor > 1:
        raise DeploymentError(
            'Coffin package version 0.3 is not compatible '
            'with the current version of Django, please upgrade '
            'coffin to at least 0.3.3'
        )
