import listeners

VERSION = (0, 4, 0)

def get_version():
    "Returns the version as a human-format string."
    return '.'.join([str(i) for i in VERSION])

