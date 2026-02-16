"""Directory test utilities."""
import os
import os.path
import re
import glob
import importlib


IMPORT_RE1 = re.compile(r'from django.*import')
IMPORT_RE2 = re.compile(r'import django')
def dir_has_django_project(directory):
    """`True` if  any of the .py files in the directory
    imports code from django"""
    directory = os.path.normpath(directory)
    file_list = glob.glob(directory  + os.path.sep + '*.py')
    for file_name in file_list:
        if file_name.endswith(os.path.sep + 'manage.py'):
            #a hack allowing to install into the project directory
            continue
        with open(file_name, 'r') as py_file:
            for line in py_file:
                if IMPORT_RE1.match(line) or IMPORT_RE2.match(line):
                    return True
    return False

# Only used in get_install_directory
def is_dir_python_module(directory):
    """True if directory is not taken by another python module"""
    dir_name = os.path.basename(directory)
    try:
        importlib.find_module(dir_name)
        return True
    except ImportError:
        return False
