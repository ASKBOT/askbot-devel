"""Taken and modified from the dbsettings project.

http://code.google.com/p/django-values/
"""
from decimal import Decimal
from django import forms
from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import simplejson
from django.utils.datastructures import SortedDict
from django.utils.encoding import smart_str
from django.utils.translation import gettext, ugettext_lazy as _
from django.core.files import storage
from askbot.deps.livesettings.models import find_setting, LongSetting, Setting, SettingNotSet
from askbot.deps.livesettings.overrides import get_overrides
from askbot.deps.livesettings.utils import load_module, is_string_like, is_list_or_tuple
from askbot.deps.livesettings.widgets import ImageInput
import datetime
import logging
import signals
import os

__all__ = ['BASE_GROUP', 'BASE_SUPER_GROUP', 'ConfigurationGroup', 'Value', 'BooleanValue', 
      'DecimalValue', 'DurationValue',
      'FloatValue', 'IntegerValue', 'ModuleValue', 'PercentValue', 'PositiveIntegerValue', 'SortedDotDict',
      'StringValue', 'SuperGroup', 'ImageValue', 'LongStringValue', 'MultipleStringValue', 'URLValue']

_WARN = {}

log = logging.getLogger('configuration')

NOTSET = object()

class SortedDotDict(SortedDict):

    def __getattr__(self, key):
        try:
            return self[key]
        except:
            raise AttributeError, key

    def __iter__(self):
        vals = self.values()
        for k in vals:
            yield k

    def values(self):
        vals = super(SortedDotDict, self).values()
        vals = [v for v in vals if isinstance(v, (ConfigurationGroup, Value))]
        vals.sort()
        return vals

class SuperGroup(object):
    """Aggregates ConfigurationGroup's into super-groups
    that are used only for the presentation in the UI"""
    def __init__(self, name, ordering = 0):
        self.name = name
        self.ordering = ordering
        self.groups = list()

    def append(self, group):
        """adds instance of :class:`ConfigurationGroup`
        to the super group
        """
        if group not in self.groups:
            self.groups.append(group)


BASE_SUPER_GROUP = SuperGroup(_('Main'))

class ConfigurationGroup(SortedDotDict):
    """A simple wrapper for a group of configuration values"""
    def __init__(self, key, name, *args, **kwargs):
        """Create a new ConfigurationGroup.

        Arguments:
        - key
        - group name - for display to user

        Named Arguments:
        - ordering: integer, optional, defaults to 1.
        - requires: See `Value` requires.  The default `requires` all member values will have if not overridden.
        - requiresvalue: See `Values` requires_value.  The default `requires_value` if not overridden on the `Value` objects.
        """
        self.key = key
        self.name = name
        self.ordering = kwargs.pop('ordering', 1)
        self.requires = kwargs.pop('requires', None)
        self.super_group = kwargs.pop('super_group', BASE_SUPER_GROUP)
        self.super_group.append(self)
        if self.requires:
            reqval = kwargs.pop('requiresvalue', key)
            if not is_list_or_tuple(reqval):
                reqval = (reqval, reqval)

            self.requires_value = reqval[0]
            self.requires.add_choice(reqval)

        super(ConfigurationGroup, self).__init__(*args, **kwargs)

    def __cmp__(self, other):
        return cmp((self.ordering, self.name), (other.ordering, other.name))

    def __eq__(self, other):
        return (type(self) == type(other)
                and self.ordering == other.ordering
                and self.name == other.name)

    def __ne__(self, other):
        return not self == other

    def dict_values(self, load_modules=True):
        vals = {}
        keys = super(ConfigurationGroup, self).keys()
        for key in keys:
            v = self[key]
            if isinstance(v, Value):
                value = v.value
            else:
                value = v
            vals[key] = value
        return vals

    def values(self):
        vals = super(ConfigurationGroup, self).values()
        return [v for v in vals if v.enabled()]

BASE_GROUP = ConfigurationGroup('BASE', _('Base Settings'), ordering=0)

class Value(object):

    creation_counter = 0

    def __init__(self, group, key, **kwargs):
        """
        Create a new Value object for configuration.

        Args:
            - `ConfigurationGroup`
            - key - a string key

        Named arguments:
            - `description` - Will be passed to the field for form usage.  Should be a translation proxy.  Ex: _('example')
            - `help_text` - Will be passed to the field for form usage.
            - `choices` - If given, then the form field will use a select box
            - `ordering` - Defaults to alphabetical by key if not given.
            - `requires` - If given as a `Value`, then this field will only be rendered if that Value evaluates true (for Boolean requires) or the proper key is in the associated value.
            - `requiresvalue` - If set, then this field will only be rendered if that value is in the list returned by self.value. Defaults to self.key.
            - `hidden` - If true, then render a hidden field.
            - `default` - If given, then this Value will return that default whenever it has no assocated `Setting`.
            - `update_callback` - if given, then this value will call the callback whenever updated
        """
        self.group = group
        self.key = key
        self.description = kwargs.get('description', None)
        self.help_text = kwargs.get('help_text')
        self.choices = kwargs.get('choices',[])
        self.ordering = kwargs.pop('ordering', 0)
        self.hidden = kwargs.pop('hidden', False)
        self.update_callback = kwargs.pop('update_callback', None)
        self.requires = kwargs.pop('requires', None)
        if self.requires:
            reqval = kwargs.pop('requiresvalue', key)
            if not is_list_or_tuple(reqval):
                reqval = (reqval, reqval)

            self.requires_value = reqval[0]
            self.requires.add_choice(reqval)

        elif group.requires:
            self.requires = group.requires
            self.requires_value = group.requires_value

        if kwargs.has_key('default'):
            self.default = kwargs.pop('default')
            self.use_default = True
        else:
            self.use_default = False

        self.creation_counter = Value.creation_counter
        Value.creation_counter += 1

    def __cmp__(self, other):
        return cmp((self.ordering, self.description, self.creation_counter), (other.ordering, other.description, other.creation_counter))

    def __eq__(self, other):
        if type(self) == type(other):
            return self.value == other.value
        else:
            return self.value == other

    def __iter__(self):
        return iter(self.value)

    def __unicode__(self):
        return unicode(self.value)

    def __str__(self):
        return str(self.value)

    def add_choice(self, choice):
        """Add a choice if it doesn't already exist."""
        if not is_list_or_tuple(choice):
            choice = (choice, choice)
        skip = False
        for k, v in self.choices:
            if k == choice[0]:
                skip = True
                break
        if not skip:
            self.choices += (choice, )

    def choice_field(self, **kwargs):
        if self.hidden:
            kwargs['widget'] = forms.MultipleHiddenInput()
        return forms.ChoiceField(choices=self.choices, **kwargs)

    def _choice_values(self):
        choices = self.choices
        vals = self.value
        return [x for x in choices if x[0] in vals]

    choice_values = property(fget=_choice_values)

    def copy(self):
        new_value = self.__class__(self.key)
        new_value.__dict__ = self.__dict__.copy()
        return new_value

    def _default_text(self):
        if not self.use_default:
            note = ""
        else:
            if self.default == "":
                note = _('Default value: ""')

            elif self.choices:
                work = []
                for x in self.choices:
                    if x[0] in self.default:
                        work.append(smart_str(x[1]))
                note = gettext('Default value: ') + ", ".join(work)

            else:
                note = _("Default value: %s") % unicode(self.default)

        return note

    default_text = property(fget=_default_text)

    def enabled(self):
        enabled = False
        try:
            if not self.requires:
                enabled = True
            else:
                v = self.requires.value
                if self.requires.choices:
                    enabled = self.requires_value == v or self.requires_value in v
                elif v:
                    enabled = True
        except SettingNotSet:
            pass
        return enabled

    def make_field(self, **kwargs):
        if self.choices:
            if self.hidden:
                kwargs['widget'] = forms.MultipleHiddenInput()
            field = self.choice_field(**kwargs)
        else:
            if self.hidden:
                kwargs['widget'] = forms.HiddenInput()
            field = self.field(**kwargs)

        field.group = self.group
        field.default_text = self.default_text
        return field

    def make_setting(self, db_value):
        log.debug('new setting %s.%s', self.group.key, self.key)
        return Setting(group=self.group.key, key=self.key, value=db_value)

    def _setting(self):
        return find_setting(self.group.key, self.key)

    setting = property(fget = _setting)

    def _value(self):
        use_db, overrides = get_overrides()

        if not use_db:
            try:
                val = overrides[self.group.key][self.key]
            except KeyError:
                if self.use_default:
                    val = self.default
                else:
                    raise SettingNotSet('%s.%s is not in your LIVESETTINGS_OPTIONS' % (self.group.key, self.key))

        else:
            try:
                val = self.setting.value

            except SettingNotSet, sns:
                if self.use_default:
                    val = self.default
                    if overrides:
                        # maybe override the default
                        grp = overrides.get(self.group.key, {})
                        if grp.has_key(self.key):
                            val = grp[self.key]
                else:
                    val = NOTSET

            except AttributeError, ae:
                log.error("Attribute error: %s", ae)
                log.error("%s: Could not get _value of %s", self.key, self.setting)
                raise(ae)

            except Exception, e:
                global _WARN
                log.error(e)
                if str(e).find("configuration_setting") > -1:
                    if not _WARN.has_key('configuration_setting'):
                        log.warn('Error loading setting %s.%s from table, OK if you are in syncdb', self.group.key, self.key)
                        _WARN['configuration_setting'] = True

                    if self.use_default:
                        val = self.default
                    else:
                        raise ImproperlyConfigured("All settings used in startup must have defaults, %s.%s does not", self.group.key, self.key)
                else:
                    import traceback
                    traceback.print_exc()
                    log.warn("Problem finding settings %s.%s, %s", self.group.key, self.key, e)
                    raise SettingNotSet("Startup error, couldn't load %s.%s" %(self.group.key, self.key))
        return val

    def update(self, value):
        use_db, overrides = get_overrides()

        if use_db:
            current_value = self.value

            new_value = self.to_python(value)
            if current_value != new_value:
                if self.update_callback:
                    new_value = apply(self.update_callback, (current_value, new_value))

                db_value = self.get_db_prep_save(new_value)

                try:
                    s = self.setting
                    s.value = db_value

                except SettingNotSet:
                    s = self.make_setting(db_value)

                if self.use_default and self.default == new_value:
                    if s.id:
                        log.info("Deleted setting %s.%s", self.group.key, self.key)
                        s.delete()
                else:
                    log.info("Updated setting %s.%s = %s", self.group.key, self.key, value)
                    s.save()

                signals.configuration_value_changed.send(self, old_value=current_value, new_value=new_value, setting=self)

                return True
        else:
            log.debug('not updating setting %s.%s - askbot.deps.livesettings db is disabled',self.group.key, self.key)

        return False

    @property
    def value(self):
        val = self._value()
        return self.to_python(val)

    @property
    def editor_value(self):
        val = self._value()
        return self.to_editor(val)

    # Subclasses should override the following methods where applicable

    def to_python(self, value):
        "Returns a native Python object suitable for immediate use"
        if value == NOTSET:
            value = None
        return value

    def get_db_prep_save(self, value):
        "Returns a value suitable for storage into a CharField"
        if value == NOTSET:
            value = ""
        return unicode(value)

    def to_editor(self, value):
        "Returns a value suitable for display in a form widget"
        if value == NOTSET:
            return NOTSET
        return unicode(value)

###############
# VALUE TYPES #
###############

class BooleanValue(Value):

    class field(forms.BooleanField):

        def __init__(self, *args, **kwargs):
            kwargs['required'] = False
            forms.BooleanField.__init__(self, *args, **kwargs)

    def add_choice(self, choice):
        # ignore choice adding for boolean types
        pass

    def to_python(self, value):
        if value in (True, 't', 'True', 1, '1'):
            return True
        return False

    to_editor = to_python

class DecimalValue(Value):
    class field(forms.DecimalField):

           def __init__(self, *args, **kwargs):
               kwargs['required'] = False
               forms.DecimalField.__init__(self, *args, **kwargs)

    def to_python(self, value):
        if value==NOTSET:
            return Decimal("0")

        try:
            return Decimal(value)
        except TypeError, te:
            log.warning("Can't convert %s to Decimal for settings %s.%s", value, self.group.key, self.key)
            raise TypeError(te)

    def to_editor(self, value):
        if value == NOTSET:
            return "0"
        else:
            return unicode(value)

# DurationValue has a lot of duplication and ugliness because of issue #2443
# Until DurationField is sorted out, this has to do some extra work
class DurationValue(Value):

    class field(forms.CharField):
        def clean(self, value):
            try:
                return datetime.timedelta(seconds=float(value))
            except (ValueError, TypeError):
                raise forms.ValidationError('This value must be a real number.')
            except OverflowError:
                raise forms.ValidationError('The maximum allowed value is %s' % datetime.timedelta.max)

    def to_python(self, value):
        if value == NOTSET:
            value = 0
        if isinstance(value, datetime.timedelta):
            return value
        try:
            return datetime.timedelta(seconds=float(value))
        except (ValueError, TypeError):
            raise forms.ValidationError('This value must be a real number.')
        except OverflowError:
            raise forms.ValidationError('The maximum allowed value is %s' % datetime.timedelta.max)

    def get_db_prep_save(self, value):
        if value == NOTSET:
            return NOTSET
        else:
            return unicode(value.days * 24 * 3600 + value.seconds + float(value.microseconds) / 1000000)

class FloatValue(Value):

    class field(forms.FloatField):

        def __init__(self, *args, **kwargs):
            kwargs['required'] = False
            forms.FloatField.__init__(self, *args, **kwargs)

    def to_python(self, value):
        if value == NOTSET:
            value = 0
        return float(value)

    def to_editor(self, value):
        if value == NOTSET:
            return "0"
        else:
            return unicode(value)

class IntegerValue(Value):
    class field(forms.IntegerField):

        def __init__(self, *args, **kwargs):
            kwargs['required'] = False
            forms.IntegerField.__init__(self, *args, **kwargs)

    def to_python(self, value):
        if value == NOTSET:
            value = 0
        return int(value)

    def to_editor(self, value):
        if value == NOTSET:
            return "0"
        else:
            return unicode(value)


class PercentValue(Value):

    class field(forms.DecimalField):

        def __init__(self, *args, **kwargs):
            kwargs['required'] = False
            forms.DecimalField.__init__(self, 100, 0, 5, 2, *args, **kwargs)

        class widget(forms.TextInput):
            def render(self, *args, **kwargs):
                # Place a percent sign after a smaller text field
                attrs = kwargs.pop('attrs', {})
                attrs['size'] = attrs['max_length'] = 6
                return forms.TextInput.render(self, attrs=attrs, *args, **kwargs) + '%'

    def to_python(self, value):
        if value == NOTSET:
            value = 0
        return Decimal(value) / 100

    def to_editor(self, value):
        if value == NOTSET:
            return "0"
        else:
            return unicode(value)

class PositiveIntegerValue(IntegerValue):

    class field(forms.IntegerField):

        def __init__(self, *args, **kwargs):
            kwargs['min_value'] = 0
            forms.IntegerField.__init__(self, *args, **kwargs)


class StringValue(Value):

    class field(forms.CharField):
        def __init__(self, *args, **kwargs):
            kwargs['required'] = False
            forms.CharField.__init__(self, *args, **kwargs)

    def to_python(self, value):
        if value == NOTSET:
            value = ""
        return unicode(value)

    to_editor = to_python

class URLValue(Value):

    class field(forms.URLField):

        def __init__(self, *args, **kwargs):
            kwargs['required'] = False
            forms.URLField.__init__(self, *args, **kwargs)

class LongStringValue(Value):

    class field(forms.CharField):
        def __init__(self, *args, **kwargs):
            kwargs['required'] = False
            kwargs['widget'] = forms.Textarea()
            forms.CharField.__init__(self, *args, **kwargs)

    def make_setting(self, db_value):
        log.debug('new long setting %s.%s', self.group.key, self.key)
        return LongSetting(group=self.group.key, key=self.key, value=db_value)

    def to_python(self, value):
        if value == NOTSET:
            value = ""
        return unicode(value)

    to_editor = to_python

class ImageValue(StringValue):

    def __init__(self, *args, **kwargs):
        self.allowed_file_extensions = kwargs.pop(
            'allowed_file_extensions',
            ('jpg', 'gif', 'png')
        )
        self.upload_directory = kwargs.pop(
                                    'upload_directory',
                                    django_settings.MEDIA_ROOT
                                )
        self.upload_url = kwargs.pop(
                                    'upload_url',
                                    django_settings.MEDIA_URL
                                )
        self.url_resolver = kwargs.pop('url_resolver', None)
        super(ImageValue, self).__init__(*args, **kwargs)

    class field(forms.FileField):
        def __init__(self, *args, **kwargs):
            kwargs['required'] = False
            self.allowed_file_extensions = kwargs.pop('allowed_file_extensions')
            url_resolver = kwargs.pop('url_resolver')
            kwargs['widget'] = ImageInput(url_resolver = url_resolver)
            forms.FileField.__init__(self, *args, **kwargs)

        def clean(self, file_data, initial=None):
            if not file_data and initial:
                return initial
            (base_name, ext) = os.path.splitext(file_data.name)
            #first character in ext is .
            if ext[1:].lower() not in self.allowed_file_extensions:
                error_message = _('Allowed image file types are %(types)s') \
                        % {'types': ', '.join(self.allowed_file_extensions)}
                raise forms.ValidationError(error_message)

    def make_field(self, **kwargs):
        kwargs['url_resolver'] = self.url_resolver
        kwargs['allowed_file_extensions'] = self.allowed_file_extensions
        return super(StringValue, self).make_field(**kwargs)

    def update(self, uploaded_file):
        """uploaded_file is an instance of
        django UploadedFile object
        """
        #0) initialize file storage
        file_storage_class = storage.get_storage_class()

        storage_settings = {}
        if django_settings.DEFAULT_FILE_STORAGE == \
            'django.core.files.storage.FileSystemStorage':
            storage_settings = {
                'location': self.upload_directory,
                'base_url': self.upload_url
            }

        file_storage = file_storage_class(**storage_settings)

        #1) come up with a file name
        #todo: need better function here to calc name
        file_name = file_storage.get_available_name(uploaded_file.name)
        file_storage.save(file_name, uploaded_file)
        url = file_storage.url(file_name)

        old_file = self.value
        old_file = old_file.replace(self.upload_url, '', 1)
        old_file_path = os.path.join(self.upload_directory, old_file)
        if os.path.isfile(old_file_path):
            os.unlink(old_file_path)

        #saved file path is relative to the upload_directory
        #so that things could be easily relocated
        super(ImageValue, self).update(url)

class MultipleStringValue(Value):

    class field(forms.CharField):

        def __init__(self, *args, **kwargs):
            kwargs['required'] = False
            forms.CharField.__init__(self, *args, **kwargs)

    def choice_field(self, **kwargs):
        kwargs['required'] = False
        return forms.MultipleChoiceField(choices=self.choices, **kwargs)

    def get_db_prep_save(self, value):
        if is_string_like(value):
            value = [value]
        return simplejson.dumps(value)

    def to_python(self, value):
        if not value or value == NOTSET:
            return []
        if is_list_or_tuple(value):
            return value
        else:
            try:
                return simplejson.loads(value)
            except:
                if is_string_like(value):
                    return [value]
                else:
                    log.warning('Could not decode returning empty list: %s', value)
                    return []


    to_editor = to_python

class ModuleValue(Value):
    """Handles setting modules, storing them as strings in the db."""

    class field(forms.CharField):

        def __init__(self, *args, **kwargs):
            kwargs['required'] = False
            forms.CharField.__init__(self, *args, **kwargs)

    def load_module(self, module):
        """Load a child module"""
        value = self._value()
        if value == NOTSET:
            raise SettingNotSet("%s.%s", self.group.key, self.key)
        else:
            return load_module("%s.%s" % (value, module))

    def to_python(self, value):
        if value == NOTSET:
            v = {}
        else:
            v = load_module(value)
        return v

    def to_editor(self, value):
        if value == NOTSET:
            value = ""
        return value

