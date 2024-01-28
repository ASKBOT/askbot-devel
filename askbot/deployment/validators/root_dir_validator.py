"""Validator for root project directory: container of the manage.py
and of the Project directory, which in turn has the settings.py file etc."""
import os
from askbot.deployment import const
from askbot.deployment.utils import dir_clashes_with_python_module
from askbot.deployment.validators.dir_validator import DirValidator

class RootDirValidator(DirValidator):
    """Implements validator for the root directory,
    by providing the .clean method"""

    def __init__(self, console, parser):
        super().__init__(console, parser)
        self.user_prompt = f'Enter {const.ROOT_DIR_HELP}.'
        self.option_name = 'root_dir'
        self.default = './' + const.DEFAULT_PROJECT_NAME


    def clean(self, raw_value):
        """Returns root_dir and error (both are strings).
        If there is error, root_dir may be None.
        """
        root_dir = os.path.abspath(raw_value)
        error = None

        if ' ' in root_dir:
            if self.entered_by_hand:
                error = 'Spaces are not allowed in the project root directory name.'
            else:
                error = 'Value of --root-dir should not have space characters.'
            return None, error

        if dir_clashes_with_python_module(root_dir):
            mod_name = os.path.basename(root_dir)
            if self.entered_by_hand:
                error = f'Value clashes with the `{mod_name}` python module.\n' + \
                        'Try a different value or ' + const.USE_FORCE_PARAMETER + '.'
            else:
                error = f'Value of --root-dir clashes with the `{mod_name}` ' + \
                        'python module.\nTry a different value or ' + \
                        const.USE_FORCE_PARAMETER + '.'

        if os.path.exists(root_dir):
            if self.entered_by_hand:
                error = f'{root_dir} already exists.\nTry a different value or ' + \
                        const.USE_FORCE_PARAMETER + '.'
            else:
                error = f'{root_dir} already exists.\n' + \
                        'Use a different value for the --root-dir parameter or ' + \
                        const.USE_FORCE_PARAMETER + '.'

        return root_dir, error
