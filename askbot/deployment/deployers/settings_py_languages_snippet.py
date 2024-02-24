"""Deployer for the languages snippet of the settings.py file"""
from askbot.deployment.deployers.file_deployer import FileDeployer

class SettingsPyLanguagesSnippet(FileDeployer): # pylint: disable=missing-class-docstring, too-few-public-methods, abstract-method
    template_path = 'deployment/templates/settings_py_languages_snippet.jinja2'

    def render(self):
        """Renders the languages snippet, allows
        the override with the `language_settings` parameter"""
        if self.params['language_settings']:
            return self.params['language_settings']
        return super().render()
