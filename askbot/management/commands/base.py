from askbot.models import Message
from askbot.models import User
from askbot.models import ImportedObjectInfo
from askbot.models import ImportRun
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings as django_settings
from bs4 import BeautifulSoup
from collections import defaultdict
from django.core import serializers
from django.utils.encoding import smart_str
from django.utils.translation import activate as activate_language
from optparse import make_option
import os
import sys
from tempfile import mkstemp

class BaseImportXMLCommand(BaseCommand):
    help = 'Base command for adding XML data from other forums to Askbot'

    option_list = BaseCommand.option_list + (
            make_option('--redirect-format',
                action = 'store',
                dest = 'redirect_format',
                default = 'none',
                help = 'Format for the redirect files (apache|nginx|none)'
            ),
    )

    def handle(self, *args, **kwargs):

        activate_language(django_settings.LANGUAGE_CODE)

        #init the redirects file format table
        self.redirect_format = self.get_redirect_format(kwargs['redirect_format'])

        self.setup_run()
        self.read_xml_file(args[0])

        self.remember_message_ids()
        self.handle_import()
        self.delete_new_messages()

    def handle_import(self):
        """this method should contain the actual work of importing data

        If necessary, create redirect files using methods
        redirects_file = self.open_unique_file('user_redirects')
        self.write_redirect(old_url, new_url, redirects_file)
        redirects_file.close()
        where old_url and new_url are urls of the corresponding objects
        before and after importation
        """
        raise NotImplementedError('Implement this method to import data')


    def get_redirect_format(self, format_setting):
        format_table = {
            'nginx': 'rewrite ^%s$ %s break;\n',
            'apache': 'Redirect permanent %s %s\n',
        }
        format_table = defaultdict(lambda: '%s %s\n', format_table)
        return format_table[format_setting]

    def setup_run(self):
        """remembers the run information,
        for the logging purposes
        """
        command = ' '.join(sys.argv)
        run = ImportRun.objects.create(command=command)
        self.run = run

    def read_xml_file(self, filename):
        """reads xml data int BeautifulSoup instance"""
        if not os.path.isfile(filename):
            raise CommandError('File %s does not exist') % filename
        xml = open(filename, 'r').read()
        self.soup = BeautifulSoup(xml, ['lxml', 'xml'])

    def remember_message_ids(self):
        """remembers messages ids of existing messages - we use these
        to delete any messages added automatically during the import"""
        self.message_ids = list(Message.objects.values_list('id', flat=True))

    def log_action_with_old_id(self, from_object_id, to_object, extra_info=None):
        info = ImportedObjectInfo()
        info.old_id = from_object_id
        info.new_id = to_object.id
        info.model = str(to_object._meta)
        info.run = self.run
        info.extra_info = extra_info or dict()
        info.save()

    def log_action(self, from_object, to_object, extra_info=None):
        self.log_action_with_old_id(from_object.id, to_object, extra_info=extra_info)

    def get_imported_object_id_by_old_id(self, model_class, old_id):
        """Returts id of imported object by old id"""
        if old_id is None:
            return None
        try:
            log = ImportedObjectInfo.objects.get(
                                        model=str(model_class._meta),
                                        old_id=old_id,
                                        run=self.run
                                    )
            return log.new_id
        except ImportedObjectInfo.DoesNotExist:
            return None

    def get_imported_object_by_old_id(self, model_class, old_id):
        """Returns new imported object by id of corresponding old object"""
        new_id = self.get_imported_object_id_by_old_id(model_class, old_id)
        if new_id:
            return model_class.objects.get(id=new_id)
        return None

    def get_objects_for_model(self, model_name):
        """returns iterator of objects from the django
        xml dump by name"""
        object_soup = self.soup.find_all('object', {'model': model_name})
        for datum in object_soup:
            yield self.get_deserialized_object(datum)

    def delete_new_messages(self):
        """deletes any messages that were added by askbot during the import process"""
        Message.objects.exclude(id__in=self.message_ids).delete()

    def open_unique_file(self, name_hint):
        """return a file using name_hint as the hint
        for the file name, if file with that name exists,
        create a unique file name containing hint as part of
        the name"""
        if os.path.exists(name_hint):
            info = mkstemp(dir=os.getcwd(), prefix=name_hint + '_')
            name_hint = info[1]
        print 'saving file: %s' % name_hint
        return open(name_hint, 'w')

    def write_redirect(self, from_url, to_url, redirects_file):
        """writes redirect clause to a file in format
        chosen earlier in the `handle` function"""
        if from_url != to_url:
            redirects_file.write(self.redirect_format % (from_url, to_url))

    def get_safe_username(self, username):
        """get unique username similar to `username`
        to avoid the uniqueness clash"""
        existing_names = User.objects.filter(
                        username__istartswith=username
                    ).values_list('username', flat=True)

        if len(existing_names) == 0:
            return username

        num = 1
        while True:
            new_name = username + str(num)
            if new_name in existing_names:
                num += 1
            else:
                return new_name

    def get_deserialized_object(self, xml_soup):
        """returns deserialized django object for xml soup with one item"""
        item_xml = smart_str(xml_soup)
        #below call assumes a single item within
        obj = serializers.deserialize('xml', item_xml).next().object
        obj._source_xml = item_xml
        return obj

    def get_m2m_ids_for_field(self, obj, field_name):
        xml = obj._source_xml
        soup = BeautifulSoup(xml)
        ids = list()
        for field in soup.findAll('field', attrs={'name': field_name}):
            objs = field.findAll('object')
            for obj in objs:
                ids.append(obj.attrs['pk'])
        return ids

    def copy_string_parameter(self, from_obj, to_obj, from_param_name, to_param_name=None):
        """copy value of string parameter from old to new object"""

        to_param_name = to_param_name or from_param_name

        from_par = getattr(from_obj, from_param_name)
        to_par = getattr(to_obj, to_param_name)
        if from_par is None and to_par is None:
            return
        from_par = from_par or ''
        to_par = to_par or ''
        if from_par.strip() == '' and to_par.strip() != '':
            setattr(to_obj, to_param_name, from_par)

    def copy_bool_parameter(self, from_obj, to_obj, from_param_name, to_param_name=None, operator='or'):
        """copy value of boolean parameter from old to new object"""

        to_param_name = to_param_name or from_param_name

        from_par = getattr(from_obj, from_param_name)
        to_par = getattr(to_obj, to_param_name)
        if operator == 'or':
            value = from_par or to_par
        elif operator == 'and':
            value = from_par and to_par
        else:
            raise ValueError('unsupported operator "%s"' % operator)
        setattr(to_obj, to_param_name, value)

    def merge_words_parameter(self, from_obj, to_obj, from_param_name, to_param_name=None):
        """merge unique words from the two objects and assign to the new object"""

        to_param_name = to_param_name or from_param_name

        from_words = getattr(from_obj, from_param_name).split()
        to_words = getattr(to_obj, to_param_name).split()
        value = ' '.join(set(from_words)|set(to_words))
        setattr(to_obj, to_param_name, value)

    def copy_numeric_parameter(self, from_obj, to_obj, from_param_name, to_param_name=None, operator='max'):

        to_param_name = to_param_name or from_param_name

        from_par = getattr(from_obj, from_param_name)
        to_par = getattr(to_obj, to_param_name)

        if from_par is None:
            return to_par
        elif to_par is None:
            return from_par

        if operator == 'max':
            value = max(from_par, to_par)
        elif operator == 'min':
            value = min(from_par, to_par)
        elif operator == 'sum':
            value =  from_par + to_par
        else:
            raise ValueError('unsupported operator "%s"' % operator)
        setattr(to_obj, to_param_name, value)
