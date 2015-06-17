"""utilities that determine versions of packages
that are part of askbot

versions of all packages are normalized to three-tuples
of integers (missing zeroes added)
"""
import coffin
import django

def get_coffin_version():
    """Returns version of Coffin package
    as a three integer value tuple
    """
    version = coffin.__version__
    if len(version) == 2:
        micro_version = 0
    elif len(version) == 3:
        micro_version = version[2]
    else:
        raise ValueError('unsupported version of coffin %s' % '.'.join(version))
    major_version = version[0]
    minor_version = version[1]
    return (major_version, minor_version, micro_version)

def get_django_version():
    """returns three-tuple for the version
    of django"""
    return django.VERSION[:3]
