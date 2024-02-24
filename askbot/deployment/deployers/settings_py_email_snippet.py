"""Deployer for the email snippet of the settings.py file."""
from askbot.deployment.deployers.file_deployer import FileDeployer

class SettingsPyEmailSnippet(FileDeployer): # pylint: disable=missing-class-docstring
    # pylint: disable=abstract-method,too-few-public-methods
    template_path = 'deployment/templates/settings_py_email_snippet.jinja2'

    def render(self):
        """Renders the email settings snippet,
        allows override via the --email-settings
        parameter"""
        if self.params['email_settings']:
            return self.params['email_settings']
        return super().render()
