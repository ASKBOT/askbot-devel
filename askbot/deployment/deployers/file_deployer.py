"""Base class for the deployables files"""
import jinja2
from askbot import get_askbot_module_path

class FileDeployer: #pylint: disable=missing-class-docstring
    """Renders a file based on the template and the parameters.
    Subclass must implement/provide at least:
    * .get_file_path() - implement the method
    * .template_path - class variable

    .get_template_parameters() - is needed if the file template needs data
    """
    template_path = None #path relative to the `askbot` module dir

    def __init__(self, params):
        self.params = params

    def get_file_path(self):
        """Subclass should implement this.
        Return target path for the file"""
        raise NotImplementedError

    def get_template_parameters(self): # pylint: disable=no-self-use
        """Subclass might implement this,
        return parameters needed for the template"""
        return self.params

    def get_template(self):
        """Returns string representation of the template"""
        return open(get_askbot_module_path(self.template_path)).read()

    def deploy_file(self, contents):
        """Writes contents into the target file"""
        fout = open(self.get_file_path(), 'w')
        fout.write(contents)
        fout.close()

    def render(self):
        """Returns rendered file content"""
        tpl_params = self.get_template_parameters()
        return jinja2.Template(self.get_template()).render(tpl_params)

    def deploy(self):
        """Renders the template and writes the file at destination"""
        self.deploy_file(self.render())
