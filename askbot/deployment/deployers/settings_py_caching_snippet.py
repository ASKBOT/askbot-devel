"""Deyloer for the caching snippet in the settings.py file"""
from askbot.deployment.deployers.file_deployer import FileDeployer

class SettingsPyCachingSnippet(FileDeployer): # pylint: disable=missing-class-docstring,abstract-method
    template_path = 'deployment/templates/settings_py_caching_snippet.jinja2'

    def render(self):
        if self.params['caching_settings']:
            return self.params['caching_settings']
        return super().render()
