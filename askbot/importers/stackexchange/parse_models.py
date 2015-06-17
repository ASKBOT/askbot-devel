from xml.etree import ElementTree as et
import sys
import re
import os
if __name__ != '__main__':#hack do not import models if run as script
    from django.db import models
from datetime import datetime

table_prefix = ''#StackExchange or something, if needed
date_time_format = '%Y-%m-%dT%H:%M:%S' #note that fractional part of second is lost
time_re = re.compile(r'(\.[\d]+)?$')
loader_app_name = os.path.dirname(__file__)

types = {
   'unsignedByte':'models.IntegerField',
   'FK':'models.ForeignKey',
   'PK':'models.IntegerField',
   'string':'models.CharField',
   'text':'models.TextField',
   'int':'models.IntegerField',
   'boolean':'models.NullBooleanField',
   'dateTime':'models.DateTimeField',
   'base64Binary':'models.TextField',
   'double':'models.IntegerField',
}

def camel_to_python(camel):
    """http://stackoverflow.com/questions/1175208/
    """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def singular(word):
    if word.endswith('s'):
        return word[:-1]
    else:
        return word

def get_table_name(name):
    """Determine db table name
    from the basename of the .xml file
    """
    out = table_prefix
    if name.find('2') == -1:
        out += singular(name)
    else:
        bits = name.split('2')
        bits = map(singular, bits)
        out += '2'.join(bits)
    return out

class DjangoModel(object):
    def __init__(self, name):
        self.name = get_table_name(name)
        self.fields = []
    def add_field(self,field):
        field.table = self
        self.fields.append(field)
    def __str__(self):
        out = 'class %s(models.Model):\n' % self.name
        for f in self.fields:
            out += '    %s\n' % str(f)
        return out

class DjangoField(object):
    def __init__(self, name, type, restriction = None):
        self.name = camel_to_python(name)
        if self.name == 'class':
            self.name = 'class_type'#work around python keyword
        self.type = type
        self.table = None
        self.restriction = restriction
        self.relation = None

    def __str__(self):
        out  = '%s = %s(' % (self.name, types[self.type])
        if self.type == 'FK':
            out += "'%s'" % self.relation
            out += ", related_name='%s_by_%s_set'" % (self.table.name, self.name)
            out += ', null=True'#nullable to make life easier
        elif self.type == 'PK':
            out += 'primary_key=True'
        elif self.restriction != -1:
            if self.type == 'string':
                out += 'max_length=%s' % self.restriction
                out += ', null=True'
            else:
                raise Exception('restriction (max_length) supported only for string type')
        else:
            out += 'null=True'
        out += ')'
        return out

    def get_type(self):
        return self.type

class DjangoPK(DjangoField):
    def __init__(self):
        self.name = 'id'
        self.type = 'PK'

class DjangoFK(DjangoField):
    def __init__(self, source_name):
        bits = source_name.split('Id')
        if len(bits) == 2 and bits[1] == '':
            name = bits[0]
        super(DjangoFK, self).__init__(name, 'FK')
        self.set_relation(name)

    def set_relation(self, name):
        """some relations need to be mapped
        to actual tables
        """
        self.relation = table_prefix
        if name.endswith('User'):
            self.relation += 'User'
        elif name.endswith('Post'):
            self.relation += 'Post'
        elif name in ('AcceptedAnswer','Parent'):
            self.relation = 'self' #self-referential Post model
        else:
            self.relation += name
    def get_relation(self):
        return self.relation

def get_col_type(col):
    type = col.get('type')
    restriction = -1
    if type == None:
        type_e = col.find('.//simpleType/restriction')
        type = type_e.get('base')
        try:
            restriction = int(type_e.getchildren()[0].get('value'))
        except:
            restriction = -1
        if restriction > 400:
            type = 'text'
            restriction = -1
    return type, restriction

def make_field_from_xml_tree(xml_element):
    """used by the model parser
    here we need to be detailed about field types
    because this defines the database schema
    """
    name = xml_element.get('name')
    if name == 'LinkedVoteId':#not used
        return None
    if name == 'Id':
        field = DjangoPK()
    elif name.endswith('Id') and name not in ('OpenId','PasswordId'):
        field = DjangoFK(name)
    elif name.endswith('GUID'):
        field = DjangoField(name, 'string', 64)
    else:
        type, restriction = get_col_type(xml_element)
        field = DjangoField(name, type, restriction)
    return field

def parse_field_name(input):
    """used by the data reader

    The problem is that I've scattered
    code for determination of field name over three classes:
    DjangoField, DjangoPK and DjangoFK
    so the function actually cretes fake field objects
    many time over
    """
    if input == 'Id':
        return DjangoPK().name
    elif input in ('OpenId', 'PasswordId'):
        return DjangoField(input, 'string', 7).name#happy fake field
    elif input.endswith('Id'):
        return DjangoFK(input).name#real FK field
    else:
        return DjangoField(input, 'string', 7).name#happy fake field

def parse_value(input, field_object):
    if isinstance(field_object, models.ForeignKey):
        try:
            id = int(input)
        except:
            raise Exception('non-numeric foreign key %s' % input)
        related_model = field_object.rel.to
        try:
            return related_model.objects.get(id=id)
        except related_model.DoesNotExist:
            obj = related_model(id=id)
            obj.save()#save fake empty object
            return obj
    elif isinstance(field_object, models.IntegerField):
        try:
            return int(input)
        except:
            raise Exception('expected integer, found %s' % input)
    elif isinstance(field_object, models.CharField):
        return input
    elif isinstance(field_object, models.TextField):
        return input
    elif isinstance(field_object, models.BooleanField):
        try:
            return bool(input)
        except:
            raise Exception('boolean value expected %s found' % input)
    elif isinstance(field_object, models.DateTimeField):
        input = time_re.sub('', input)
        try:
            return datetime.strptime(input, date_time_format)
        except:
            raise Exception('datetime expected "%s" found' % input)

print 'from django.db import models'
for file in sys.argv:
    if '.xsd' in file:
        tname = os.path.basename(file).replace('.xsd','')
        tree = et.parse(file)

        model = DjangoModel(tname)

        row = tree.find('.//sequence')
        for col in row.getchildren():
            field = make_field_from_xml_tree(col)
            if field:
                model.add_field(field)
        print model
