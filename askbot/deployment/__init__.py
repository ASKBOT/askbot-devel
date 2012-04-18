"""
module for deploying askbot
"""
import os.path
import sys
from optparse import OptionParser
from askbot.utils import console
from askbot.deployment import messages
from askbot.deployment.messages import print_message
from askbot.deployment import path_utils

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
                dest = "force",
                action = 'store_true',
                help = "Force overwrite settings.py file"
            )

    try:
        options = parser.parse_args()[0]
        #ask
        if options.verbosity >= 1:
            print messages.DEPLOY_PREAMBLE

        directory = path_utils.clean_directory(options.dir_name)
        while directory is None:
            directory = path_utils.get_install_directory(force = options.force)

        deploy_askbot(directory, options)
    except KeyboardInterrupt:
        print "\n\nAborted."
        sys.exit(1)


#separated all the directory creation process to make it more useful

def deploy_askbot(directory, options):
    """function that creates django project files,
    all the neccessary directories for askbot,
    and the log file
    """

    help_file = path_utils.get_path_to_help_file()
    context = {
        'database_name': options.database_name,
        'database_password': options.database_password,
        'database_user': options.database_user,
        'domain_name': options.domain_name,
        'local_settings': options.local_settings,
    }
    if not options.force:
        for key in context.keys():
            if context[key] == None:
                input_message = 'Please enter a value for %s:' \
                    % (key.replace('_', ' '))
                new_value = raw_input(input_message)
                context[key] = new_value

    create_new_project = False
    if os.path.exists(directory):
        if path_utils.has_existing_django_project(directory):
            create_new_project = bool(options.force)
        else:
            create_new_project = True
    else:
        create_new_project = True

    path_utils.create_path(directory)

    path_utils.deploy_into(
        directory,
        new_project = create_new_project,
        verbosity = options.verbosity,
        context = context
    )

    if create_new_project:
        print_message(
            messages.HOW_TO_DEPLOY_NEW % {'help_file': help_file},
            options.verbosity
        )
    else:
        print_message(
            messages.HOW_TO_ADD_ASKBOT_TO_DJANGO % {'help_file': help_file},
            options.verbosity
        )
