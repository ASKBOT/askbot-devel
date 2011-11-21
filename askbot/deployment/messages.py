"""Messages used in the procedure of deploying Askbot
"""
import os.path
from askbot.deployment import path_utils

DEPLOY_PREAMBLE = """
Deploying Askbot - Django Q&A forum application
Problems installing? -> please email admin@askbot.org

To CANCEL - hit Ctr-C at any time"""

WHERE_TO_DEPLOY = 'In which directory to deploy the forum?'

WHERE_TO_DEPLOY_QUIT = 'Where deploy the forum (directory)? Ctrl-C to quit.'

CANT_INSTALL_INTO_FILE = '%(path)s is a file\ncannot install there'

SHOULD_ADD_APP_HERE = 'Directory %(path)s?\nalready has a Django ' \
                    + 'project - do you want to add askbot app to that project?'

HOW_TO_DEPLOY_NEW = 'Done. Please find further instructions in the file below:'\
                    + '\n%(help_file)s'

HOW_TO_ADD_ASKBOT_TO_DJANGO = HOW_TO_DEPLOY_NEW

DIR_IS_NOT_WRITABLE = 'Directory %(dir)s is not writable'

PARENT_DIR_IS_NOT_WRITABLE = """To create directory %(target_dir)s
we need to add %(non_existing_tail)s to %(existing_prefix)s
but %(existing_prefix)s is not writable"""

CONFIRM_DIR_CREATION = """Adding new directories:\n%(existing_prefix)s <-/%(non_existing_tail)s
Accept?"""

CANNOT_OVERWRITE_DJANGO_PROJECT = """Directory %(directory)s
already has a django project. If you want to overwrite
settings.py and urls.py files, use parameter --force"""

INVALID_INPUT = 'Please type one of: %(opt_string)s ' \
                + '(or hit Ctrl-C to quit)'

DIR_NAME_TAKEN_BY_PYTHON = """Directory '%(dir)s' is aready used by other Python module.
Please choose some other name for your django project"""

DIR_NAME_TAKEN_BY_ASKBOT = """Please do not name your entire Django project 'askbot',
because this name is already used by the askbot app itself"""

def format_msg_dir_not_writable(directory):
    """returns a meaningful message explaining why directory 
    is not writable by the user
    """
    if os.path.exists(directory):
        if path_utils.directory_is_writable(directory):
            return ''
        else:
            return DIR_IS_NOT_WRITABLE % {'dir': directory}
    else:
        prefix, tail = path_utils.split_at_break_point(directory)
        data = {
                'existing_prefix': prefix,
                'non_existing_tail': tail,
                'target_dir': directory
            }
        return PARENT_DIR_IS_NOT_WRITABLE % data

def format_msg_create(directory):
    """returns a message explaining wha directories
    are about to be created and asks user if they want to proceed
    """
    if os.path.exists(directory):
        raise Exception('directory %s aready exists' % directory)
    else:
        prefix, tail = path_utils.split_at_break_point(directory)
        data = {
                'existing_prefix': prefix,
                'non_existing_tail': tail,
            }
        return CONFIRM_DIR_CREATION % data

def format_msg_dir_unclean_django(directory):
    """retuns a message telling which of the parent
    directories contains a django project
    so that users don't create nested projects
    """
    return path_utils.find_parent_dir_with_django(directory)

def format_msg_bad_dir_name(directory):
    """directory name must be bad - i.e. taken by other python module
    on PYTHONPATH
    """
    dir_name = os.path.basename(directory)
    if dir_name == 'askbot':
        return DIR_NAME_TAKEN_BY_ASKBOT
    else:
        return DIR_NAME_TAKEN_BY_PYTHON % {'dir': dir_name}

def print_message(message, verbosity):
    if verbosity >= 1:
        print message
