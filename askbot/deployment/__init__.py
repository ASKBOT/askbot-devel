"""
module for deploying askbot
"""
import os.path
import sys
import django
from optparse import OptionParser
from askbot.deployment import messages
from askbot.deployment.messages import print_message
from askbot.deployment import path_utils
from askbot.utils import console
from askbot.utils.functions import generate_random_key

DATABASE_ENGINE_CHOICES = ('1', '2', '3', '4')

def askbot_setup():
    """basic deployment procedure
    asks user several questions, then either creates
    new deployment (in the case of new installation)
    or gives hints on how to add askbot to an existing
    Django project
    """
    parser = OptionParser(usage = "%prog [options]")

    parser.add_option(
                "-v", "--verbose",
                dest = "verbosity",
                type = "int",
                default = 1,
                help = "verbosity level available values 0, 1, 2."
            )

    parser.add_option(
                "-n", "--dir-name",
                dest = "dir_name",
                default = None,
                help = "Directory where you want to install."
            )

    parser.add_option(
                '-e', '--db-engine',
                dest='database_engine',
                action='store',
                type='choice',
                choices=DATABASE_ENGINE_CHOICES,
                default=None,
                help='Database engine, type 1 for postgresql, 2 for sqlite, 3 for mysql'
            )

    parser.add_option(
                "-d", "--db-name",
                dest = "database_name",
                default = None,
                help = "The database name"
            )

    parser.add_option(
                "-u", "--db-user",
                dest = "database_user",
                default = None,
                help = "The database user"
            )

    parser.add_option(
                "-p", "--db-password",
                dest = "database_password",
                default = None,
                help = "the database password"
            )

    parser.add_option(
                "--domain",
                dest = "domain_name",
                default = None,
                help = "the domain name of the instance"
            )

    parser.add_option(
                "--append-settings",
                dest = "local_settings",
                default = '',
                help = "Extra settings file to append custom settings"
            )

    parser.add_option(
                "--force",
                dest="force",
                action='store_true',
                default=False,
                help = "Force overwrite settings.py file"
            )

    try:
        options = parser.parse_args()[0]

        #ask users to give missing parameters
        #todo: make this more explicit here
        if options.verbosity >= 1:
            print messages.DEPLOY_PREAMBLE

        directory = path_utils.clean_directory(options.dir_name)
        while directory is None:
            directory = path_utils.get_install_directory(force=options.force)
        options.dir_name = directory

        if options.database_engine not in DATABASE_ENGINE_CHOICES:
            options.database_engine = console.choice_dialog(
                'Please select database engine:\n1 - for postgresql, '
                '2 - for sqlite, 3 - for mysql, 4 - oracle',
                choices=DATABASE_ENGINE_CHOICES
            )

        options_dict = vars(options)
        if options.force is False:
            options_dict = collect_missing_options(options_dict)

        database_engine_codes = {
            '1': 'postgresql_psycopg2',
            '2': 'sqlite3',
            '3': 'mysql',
            '4': 'oracle'
        }
        database_engine = database_engine_codes[options.database_engine]
        options_dict['database_engine'] = database_engine

        deploy_askbot(options_dict)

        if database_engine == 'postgresql_psycopg2':
            try:
                import psycopg2
            except ImportError:
                print '\nNEXT STEPS: install python binding for postgresql'
                print 'pip install psycopg2\n'
        elif database_engine == 'mysql':
            try:
                import _mysql
            except ImportError:
                print '\nNEXT STEP: install python binding for mysql'
                print 'pip install mysql-python\n'

    except KeyboardInterrupt:
        print "\n\nAborted."
        sys.exit(1)


#separated all the directory creation process to make it more useful
def deploy_askbot(options):
    """function that creates django project files,
    all the neccessary directories for askbot,
    and the log file
    """
    create_new_project = False
    if os.path.exists(options['dir_name']):
        if path_utils.has_existing_django_project(options['dir_name']):
            create_new_project = bool(options.force)
        else:
            create_new_project = True
    else:
        create_new_project = True

    path_utils.create_path(options['dir_name'])

    if django.VERSION[0] > 1:
        raise Exception(
            'Django framework with major version > 1 is not supported'
        )

    if django.VERSION[1] < 3:
        #force people install the django-staticfiles app
        options['staticfiles_app'] = ''
    else:
        options['staticfiles_app'] = "'django.contrib.staticfiles',"

    if django.VERSION[1] <=3:
        auth_context_processor = 'django.core.context_processors.auth'
    else:
        auth_context_processor = 'django.contrib.auth.context_processors.auth'
    options['auth_context_processor'] = auth_context_processor

    verbosity = options['verbosity']

    path_utils.deploy_into(
        options['dir_name'],
        new_project=create_new_project,
        verbosity=verbosity,
        context=options
    )

    help_file = path_utils.get_path_to_help_file()

    if create_new_project:
        print_message(
            messages.HOW_TO_DEPLOY_NEW % {'help_file': help_file},
            verbosity
        )
    else:
        print_message(
            messages.HOW_TO_ADD_ASKBOT_TO_DJANGO % {'help_file': help_file},
            verbosity
        )

def collect_missing_options(options_dict):
    options_dict['secret_key'] = generate_random_key()
    if options_dict['database_engine'] == '2':#sqlite
        while True:
            value = console.simple_dialog(
                            'Please enter database file name'
                        )
            database_file_name = None
            if os.path.isfile(value):
                message = 'file %s exists, use it anyway?' % value
                if console.get_yes_or_no(message) == 'yes':
                    database_file_name = value
            elif os.path.isdir(value):
                print '%s is a directory, choose another name' % value
            elif value in path_utils.FILES_TO_CREATE:
                print 'name %s cannot be used for the database name' % value
            elif value == path_utils.LOG_DIR_NAME:
                print 'name %s cannot be used for the database name' % value
            else:
                database_file_name = value

            if database_file_name:
                options_dict['database_name'] = database_file_name
                return options_dict

    else:#others
        for key in ('database_name', 'database_user', 'database_password'): 
            if options_dict[key] is None:
                key_name = key.replace('_', ' ')
                value = console.simple_dialog(
                    '\nPlease enter %s' % key_name,
                    required=True
                )
                options_dict[key] = value
        return options_dict
