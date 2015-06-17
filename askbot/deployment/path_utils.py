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
from askbot.utils import console
from askbot.deployment.template_loader import SettingsTemplate


FILES_TO_CREATE = ('__init__.py', 'manage.py', 'urls.py', 'django.wsgi')
BLANK_FILES = ('__init__.py', 'manage.py')
LOG_DIR_NAME = 'log'


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

def clean_directory(directory):
    """Returns normalized absolute path to the directory
    regardless of whether it exists or not
    or ``None`` - if the path is a file or if ``directory``
    parameter is ``None``"""
    if directory is None:
        return None

    directory = os.path.normpath(directory)
    directory = os.path.abspath(directory)

    if os.path.isfile(directory):
        if options.verbosity >= 1 and os.path.isfile(directory):
            print messages.CANT_INSTALL_INTO_FILE % {'path':directory}
        sys.exit(1)

        return None
    return directory


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
        directory = split_at_break_point(directory)[0]
    return directory_is_writable(directory)


IMPORT_RE1 = re.compile(r'from django.*import')
IMPORT_RE2 = re.compile(r'import django')
def has_existing_django_project(directory):
    """returns True is any of the .py files
    in a given directory imports anything from django
    """
    directory = os.path.normpath(directory)
    file_list = glob.glob(directory  + os.path.sep + '*.py')
    for file_name in file_list:
        if file_name.endswith(os.path.sep + 'manage.py'):
            #a hack allowing to install into the distro directory
            continue
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

def deploy_into(directory, new_project = False, verbosity = 1, context = None):
    """will copy necessary files into the directory
    """
    assert(isinstance(new_project, bool))
    if new_project:
        copy_files = FILES_TO_CREATE
        blank_files = BLANK_FILES
        if verbosity >= 1:
            print 'Copying files: '
        for file_name in copy_files:
            src = os.path.join(SOURCE_DIR, 'setup_templates', file_name)
            if os.path.exists(os.path.join(directory, file_name)):
                if file_name in blank_files:
                    continue
                else:
                    if file_name == 'urls.py' and new_project:
                        #overwrite urls.py
                        shutil.copy(src, directory)
                    else:
                        if verbosity >= 1:
                            print '* %s' % file_name,
                            print "- you already have one, please add contents of %s" % src
            else:
                if verbosity >= 1:
                    print '* %s ' % file_name
                shutil.copy(src, directory)
        #copy log directory
        src = os.path.join(SOURCE_DIR, 'setup_templates', LOG_DIR_NAME)
        log_dir = os.path.join(directory, LOG_DIR_NAME)
        create_path(log_dir)
        touch(os.path.join(log_dir, 'askbot.log'))

        #creating settings file from template
        if verbosity >= 1:
            print "Creating settings file"
        settings_contents = SettingsTemplate(context).render()
        settings_path = os.path.join(directory, 'settings.py')
        if os.path.exists(settings_path) and new_project == False:
            if verbosity >= 1:
                print "* you already have a settings file please merge the contents"
        elif new_project == True:
            settings_file = open(settings_path, 'w+')
            settings_file.write(settings_contents)
            #Grab the file!
            if os.path.exists(context['local_settings']):
                local_settings = open(context['local_settings'], 'r').read()
                settings_file.write('\n')
                settings_file.write(local_settings)

            settings_file.close()
            if verbosity >= 1:
                print "settings file created"

    if verbosity >= 1:
        print ''
    app_dir = os.path.join(directory, 'askbot')

    copy_dirs = ('doc', 'cron', 'upfiles')
    dirs_copied = 0
    for dir_name in copy_dirs:
        src = os.path.join(SOURCE_DIR, dir_name)
        dst = os.path.join(app_dir, dir_name)
        if os.path.abspath(src) != os.path.abspath(dst):
            if dirs_copied == 0:
                if verbosity >= 1:
                    print 'copying directories: ',
            if verbosity >= 1:
                print '* ' + dir_name
            if os.path.exists(dst):
                if os.path.isdir(dst):
                    if verbosity >= 1:
                        print 'Directory %s not empty - skipped' % dst
                else:
                    if verbosity >= 1:
                        print 'File %s already exists - skipped' % dst
                continue
            shutil.copytree(src, dst)
            dirs_copied += 1
    if verbosity >= 1:
        print ''

def dir_name_unacceptable_for_django_project(directory):
    dir_name = os.path.basename(directory)
    if re.match(r'[_a-zA-Z][\w-]*$', dir_name):
        return False
    return True

def dir_taken_by_python_module(directory):
    """True if directory is not taken by another python module"""
    dir_name = os.path.basename(directory)
    try:
        imp.find_module(dir_name)
        return True
    except ImportError:
        return False

def get_install_directory(force = False):
    """returns a directory where a new django app/project
    can be installed.
    If ``force`` is ``True`` - will permit
    using a directory with an existing django project.
    """
    from askbot.deployment import messages
    where_to_deploy_msg = messages.WHERE_TO_DEPLOY
    directory = raw_input(where_to_deploy_msg + ' ')

    if directory.strip() == '':
        return None

    directory = clean_directory(directory)

    if directory is None:
        return None

    if can_create_path(directory) == False:
        print messages.format_msg_dir_not_writable(directory)
        return None

    if os.path.exists(directory):
        if path_is_clean_for_django(directory):
            if has_existing_django_project(directory):
                if not force:
                    print messages.CANNOT_OVERWRITE_DJANGO_PROJECT % \
                        {'directory': directory}
                    return None
        else:
            print messages.format_msg_dir_unclean_django(directory)
            return None
    elif force == False:
        message = messages.format_msg_create(directory)
        should_create_new = console.choice_dialog(
                            message,
                            choices = ['yes','no'],
                            invalid_phrase = messages.INVALID_INPUT
                        )
        if should_create_new == 'no':
            return None

    if dir_taken_by_python_module(directory):
        print messages.format_msg_bad_dir_name(directory)
        return None
    if dir_name_unacceptable_for_django_project(directory):
        print """\nDirectory %s is not acceptable for a Django project.
Please use lower case characters, numbers and underscore.
The first character cannot be a number.\n""" % os.path.basename(directory)
        return None

    return directory
