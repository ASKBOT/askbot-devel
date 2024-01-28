from django_jinja.base import dict_from_context
import django.template.backends.jinja2
from django.template.backends.jinja2 import Template as OriginalJinja2Template
from django.template.context import BaseContext

class Template(OriginalJinja2Template):
    # backend parameter was added with Django 1.11
    def __init__(self, template, backend=None):
        super().__init__(template, backend)

    def render(self, context=None, request=None):
        # dict from_context is from django_jinja and I am not sure if we still
        # need this; it is the last reason for this object and file to exist
        if isinstance(context,BaseContext):
            context = dict_from_context(context)

        return super().render(context, request)

django.template.backends.jinja2.Template = Template
