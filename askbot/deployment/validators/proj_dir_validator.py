"""Validator for the project directory: container of the settings.py"""
import os
from askbot.deployment import const
from askbot.deployment.utils import dir_clashes_with_python_module
from askbot.deployment.validators.dir_validator import DirValidator

class ProjDirValidator(DirValidator):
    """Implements the .clean method for the proj_name parameter"""

    def __init__(self, console, parser, root_dir):
        super().__init__(console, parser)
        self.user_prompt = f'Enter {const.PROJ_NAME_HELP}.'
        self.option_name = 'proj_name'
        self.root_dir = root_dir
        self.default = os.path.basename(root_dir)


    def clean(self, raw_value):
        """Returns proj_dir and error (both are strings).
        If there is error, proj_dir may be None.
        """
        error = None
        if ' ' in raw_value:
            if self.entered_by_hand:
                error = 'Spaces are not allowed in the project name.'
            else:
                error = 'Value of --proj-name should not have space characters.'
            return None, error

        if os.path.sep in raw_value:
            if self.entered_by_hand:
                error = f'Project name cannot have {os.path.sep} symbols'
            else:
                error = f'Value of --proj-name should not have {os.path.sep} symbols'
            return None, error

        proj_dir = os.path.abspath(os.path.join(self.root_dir, raw_value))
        if dir_clashes_with_python_module(proj_dir):
            if self.entered_by_hand:
                error = f'Value clashes with the `{raw_value}` python module.\n' + \
                        'Enter a different value or ' + const.USE_FORCE_PARAMETER + '.'
            else:
                error = f'Value of --proj-name clashes with the `{raw_value}` ' + \
                        'python module.\n' + \
                        'Try a different value or ' + \
                        const.USE_FORCE_PARAMETER + '.'

        if os.path.exists(proj_dir):
            if self.entered_by_hand:
                error = f'{proj_dir} already exists.\n' + \
                        'Enter a different value or ' + \
                        const.USE_FORCE_PARAMETER + '.'
            else:
                error = f'{proj_dir} already exists.\n' + \
                        'Use a different value for the --proj-name parameter or ' + \
                        const.USE_FORCE_PARAMETER + '.'

        return proj_dir, error
