"""Deployer for the databases snippet of the settings.py file"""
from askbot.deployment.deployers.file_deployer import FileDeployer

class SettingsPyDatabasesSnippet(FileDeployer): # pylint: disable=missing-class-docstring
    #pylint: disable=too-few-public-methods,abstract-method
    template_path = 'deployment/templates/settings_py_databases_snippet.jinja2'

    def render(self):
        """Renders the snippet, allows override by the
        `database_settings` parameter"""
        if self.params['database_settings']:
            return self.params['database_settings']
        return super().render()
