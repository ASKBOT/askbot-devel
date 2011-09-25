"""utilities in addition to os.path
that 
* help to test existing paths on usability for the installation
* create necessary directories
* install deployment files
"""
import os
import os.path
import tempfile
import re
import glob
import shutil
import imp

def split_at_break_point(directory):
    """splits directory path into two pieces
    first that exists and secon - that does not
    by determining a point at which path breaks

    exception will be raised if directory in fact exists
    """
    assert(os.path.exists(directory) == False)

    head = directory
    tail_bits = list()
    while os.path.exists(head) == False:
        head, tail = os.path.split(head)
        tail_bits.insert(0, tail)
    return head, os.path.join(*tail_bits)


def directory_is_writable(directory):
    """returns True if directory exists
    and is writable, False otherwise
    """
    tempfile.tempdir = directory
    try:
        #run writability test
        temp_path = tempfile.mktemp()
        assert(os.path.dirname(temp_path) == directory)
        temp_file = open(temp_path, 'w')
        temp_file.close()
        os.unlink(temp_path)
        return True
    except IOError:
        return False


def can_create_path(directory):
    """returns True if user can write file into 
    directory even if it does not exist yet
    and False otherwise
    """
    if os.path.exists(directory):
        if not os.path.isdir(directory):
            return False
    else:
        directory, junk = split_at_break_point(directory)
    return directory_is_writable(directory)


IMPORT_RE1 = re.compile(r'from django.*import')
IMPORT_RE2 = re.compile(r'import django')
def has_existing_django_project(directory):
    """returns True is any of the .py files
    in a given directory imports anything from django
    """
    file_list = glob.glob(directory  + '*.py')
    for file_name in file_list:
        py_file = open(file_name)
        for line in py_file:
            if IMPORT_RE1.match(line) or IMPORT_RE2.match(line):
                py_file.close()
                return True
        py_file.close()
    return False


def find_parent_dir_with_django(directory):
    """returns path to Django project anywhere
    above the directory
    if nothing is found returns None
    """
    parent_dir = os.path.dirname(directory)
    while parent_dir != directory:
        if has_existing_django_project(parent_dir):
            return parent_dir
        else:
            directory = parent_dir
            parent_dir = os.path.dirname(directory)
    return None


def path_is_clean_for_django(directory):
    """returns False if any of the parent directories
    contains a Django project, otherwise True
    does not check the current directory
    """
    django_dir = find_parent_dir_with_django(directory)
    return (django_dir is None)


def create_path(directory):
    """equivalent to mkdir -p"""
    if os.path.isdir(directory):
        return
    elif os.path.exists(directory):
        raise ValueError('expect directory or a non-existing path')
    else:
        os.makedirs(directory)

def touch(file_path, times = None):
    """implementation of unix ``touch`` in python"""
    #http://stackoverflow.com/questions/1158076/implement-touch-using-python
    fhandle = file(file_path, 'a')
    try:
        os.utime(file_path, times)
    finally:
        fhandle.close()

SOURCE_DIR = os.path.dirname(os.path.dirname(__file__))
def get_path_to_help_file():
    """returns path to the main plain text help file"""
    return os.path.join(SOURCE_DIR, 'doc', 'INSTALL')

def deploy_into(directory, new_project = None):
    """will copy necessary files into the directory
    """
    assert(new_project is not None)
    if new_project:
        copy_files = ('__init__.py', 'settings.py', 'manage.py', 'urls.py')
        blank_files = ('__init__.py', 'manage.py')
        print 'Copying files: '
        for file_name in copy_files:
            src = os.path.join(SOURCE_DIR, 'setup_templates', file_name)
            if os.path.exists(os.path.join(directory, file_name)):
                if file_name in blank_files:
                    continue
                else:
                    print '* %s' % file_name,
                    print "- you already have one, please add contents of %s" % src
            else:
                print '* %s ' % file_name
                shutil.copy(src, directory)
        #copy log directory
        src = os.path.join(SOURCE_DIR, 'setup_templates', 'log')
        log_dir = os.path.join(directory, 'log')
        create_path(log_dir)
        touch(os.path.join(log_dir, 'askbot.log'))

    print ''
    app_dir = os.path.join(directory, 'askbot')

    copy_dirs = ('doc', 'cron', 'upfiles')
    dirs_copied = 0
    for dir_name in copy_dirs:
        src = os.path.join(SOURCE_DIR, dir_name)
        dst = os.path.join(app_dir, dir_name)
        if os.path.abspath(src) != os.path.abspath(dst):
            if dirs_copied == 0:
                print 'copying directories: ',
            print '* ' + dir_name
            if os.path.exists(dst):
                if os.path.isdir(dst):
                    print 'Directory %s not empty - skipped' % dst
                else:
                    print 'File %s already exists - skipped' % dst
                continue
            shutil.copytree(src, dst)
            dirs_copied += 1
    print ''

def dir_name_acceptable(directory):
    """True if directory is not taken by another python module"""
    dir_name = os.path.basename(directory)
    try:
        imp.find_module(dir_name)
        return False
    except ImportError:
        return True
