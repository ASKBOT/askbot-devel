"""Deployer for the admins snippet of the settings.py file"""
from askbot.deployment.deployers.file_deployer import FileDeployer

class SettingsPyAdminsSnippet(FileDeployer): # pylint: disable=missing-class-docstring
    # pylint: disable=abstract-method
    template_path = 'deployment/templates/settings_py_admins_snippet.jinja2'

    def render(self):
        """--admin-settings override the default"""
        if self.params['admin_settings']:
            return self.params['admin_settings']
        return super().render()
