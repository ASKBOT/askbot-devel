"""Deployer for the logging snippet of the settings.py file"""
from askbot.deployment.deployers.file_deployer import FileDeployer

class SettingsPyLoggingSnippet(FileDeployer): # pylint: disable=missing-class-docstring,abstract-method
    template_path = 'deployment/templates/settings_py_logging_snippet.jinja2'

    def render(self):
        """Renders the logging snippet
        allows override with the --logging-settings parameter"""
        if self.params['logging_settings']:
            return self.params['logging_settings']
        return super().render()
