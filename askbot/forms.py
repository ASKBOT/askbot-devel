"""Forms, custom form fields and related utility functions
used in Askbot"""
from collections import OrderedDict
from datetime import timedelta
import logging
import unicodedata
import regex as re #todo: make explicit import
from django import forms
from django.conf import settings as django_settings
from django.core.exceptions import PermissionDenied
from django.forms.utils import ErrorList
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy
from askbot.utils.translation import get_language
from django.utils.text import get_text_list, format_lazy
from django.contrib.auth.models import User
from django_countries import countries
import askbot
from askbot import const
from askbot.const import message_keys, PROFILE_WEBSITE_URL_MAX_LENGTH
from askbot.utils.forms import NextUrlField, UserNameField
from askbot.utils.forms import moderated_email_validator
from askbot.utils.slug import slugify
from askbot.mail import extract_first_email_address
from askbot.conf import settings as askbot_settings
from askbot.conf import get_tag_email_filter_strategy_choices
from askbot.models import UserProfile
from captcha.fields import ReCaptchaField

def split_tags(data):
    split_re = re.compile(const.TAG_SPLIT_REGEX)
    data = data.strip()
    if data:
        return split_re.split(data)
    else:
        return list()


def should_use_recaptcha(user):
    """True if user must use recaptcha"""
    return askbot_settings.USE_RECAPTCHA and \
        (user.is_anonymous or user.is_watched())


def cleanup_dict(dictionary, key, empty_value):
    """deletes key from dictionary if it exists
    and the corresponding value equals the empty_value
    """
    if key in dictionary and dictionary[key] == empty_value:
        del dictionary[key]


def format_form_errors(form):
    """Formats form errors in HTML
    if there is only one error - returns a plain string
    if more than one, returns an unordered list of errors
    in HTML format.
    If there are no errors, returns empty string
    """
    if form.errors:
        errors = list(form.errors.values())
        if len(errors) == 1:
            return errors[0]
        else:
            result = '<ul>'
            for error in errors:
                result += '<li>%s</li>' % error
            result += '</ul>'
            return result
    else:
        return ''


def classify_marked_tagnames(tagnames):
    """splits tagnames into two lists: those that have
    a '*' in the end and those that don't"""
    pure_tags = list()
    wildcards = list()
    for tagname in tagnames:
        if tagname.endswith('*'):
            wildcards.append(tagname)
        else:
            pure_tags.append(tagname)
    return pure_tags, wildcards


def clean_marked_tagnames(tagnames):
    """return two strings - one containing tagnames
    that are straight names of tags, and the second one
    containing names of wildcard tags,
    wildcard tags are those that have an asterisk at the end
    the function does not verify that the tag names are valid
    """
    pure_tags = list()
    wildcards = list()
    for tagname in tagnames:
        if tagname == '':
            continue

        if askbot_settings.USE_WILDCARD_TAGS and '*' in tagname:
            if tagname.count('*') > 1:
                raise forms.ValidationError(_("Wildcard tag must have only one '*' symbol"))
            elif len(tagname) == 1:
                raise forms.ValidationError(_('Wildcard tag must have at least one symbol'))
            elif tagname[-1] == '*':
                base_tag = tagname[:-1]
                cleaned_base_tag = clean_tag(base_tag, look_in_db=False)
                wildcards.append(cleaned_base_tag + '*')
            else:
                raise forms.ValidationError(_("Wildcard tag must end with an '*' symbol"))
        else:
            pure_tags.append(clean_tag(tagname))

    return pure_tags, wildcards


def filter_choices(remove_choices=None, from_choices=None):
    """a utility function that will remove choice tuples
    usable for the forms.ChoicesField from
    ``from_choices``, the removed ones will be those given
    by the ``remove_choice`` list

    there is no error checking, ``from_choices`` tuple must be as expected
    to work with the forms.ChoicesField
    """

    if not isinstance(remove_choices, list):
        raise TypeError('remove_choices must be a list')

    filtered_choices = tuple()
    for choice_to_test in from_choices:
        remove = False
        for choice in remove_choices:
            if choice == choice_to_test[0]:
                remove = True
                break
        if remove is False:
            filtered_choices += (choice_to_test, )

    return filtered_choices


def need_mandatory_tags():
    """true, if list of mandatory tags is not empty"""
    from askbot import models
    return (
        askbot_settings.TAGS_ARE_REQUIRED and
        len(models.tag.get_mandatory_tags()) > 0
    )


def mandatory_tag_missing_in_list(tag_strings):
    """true, if mandatory tag is not present in the list
    of ``tag_strings``"""
    from askbot import models
    mandatory_tags = models.tag.get_mandatory_tags()
    for mandatory_tag in mandatory_tags:
        for tag_string in tag_strings:
            if tag_strings_match(tag_string, mandatory_tag):
                return False
    return True


def tag_strings_match(tag_string, mandatory_tag):
    """true if tag string matches the mandatory tag,
    the comparison is not symmetric if tag_string ends with a
    wildcard (asterisk)
    """
    if mandatory_tag.endswith('*'):
        return tag_string.startswith(mandatory_tag[:-1])
    else:
        return tag_string == mandatory_tag


class CountryField(forms.ChoiceField):
    """this is better placed into the django_coutries app"""

    def __init__(self, *args, **kwargs):
        """sets label and the country choices
        """
        try:
            country_choices = countries.COUNTRIES
        except AttributeError:
            from django_countries import data
            country_choices = list()
            for key, name in list(data.COUNTRIES.items()):
                country_choices.append((key, name))

        country_choices = sorted(country_choices, key=lambda c: c[1])

        country_choices = (('unknown', _('select country')),) + tuple(country_choices)
        kwargs['choices'] = kwargs.pop('choices', country_choices)
        kwargs['label'] = kwargs.pop('label', _('Country'))
        super(CountryField, self).__init__(*args, **kwargs)

    def clean(self, value):
        """Handles case of 'unknown' country selection
        """
        if self.required and value == 'unknown':
            raise forms.ValidationError(_('Country field is required'))
        if value == 'unknown':
            return None
        return value


class CountedWordsField(forms.CharField):
    """a field where a number of words is expected
    to be in a certain range"""

    def __init__(self, min_words=0, max_words=9999, field_name=None,
                 *args, **kwargs):
        self.min_words = min_words
        self.max_words = max_words
        self.field_name = field_name
        super(CountedWordsField, self).__init__(*args, **kwargs)

    def clean(self, value):
        # TODO: this field must be adapted to work with Chinese, etc.
        # for that we'll have to count characters instead of words
        if value is None:
            value = ''

        value = value.strip()
        word_count = len(value.split())
        if word_count < self.min_words:
            msg = ngettext_lazy('must be > %d word', 'must be > %d words',
                                 self.min_words - 1) % (self.min_words - 1)
            # TODO - space is not used in Chinese
            raise forms.ValidationError(
                format_lazy('{} {}', self.field_name, msg)
            )

        if word_count > self.max_words:
            msg = ngettext_lazy('must be < %d word', 'must be < %d words',
                                 self.max_words + 1) % (self.max_words + 1)
            raise forms.ValidationError(
                format_lazy('{} {}', self.field_name, msg))
        return value


class AskbotReCaptchaField(ReCaptchaField):
    """A recaptcha field with preset keys from the livesettings"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('private_key', askbot_settings.RECAPTCHA_SECRET)
        kwargs.setdefault('public_key', askbot_settings.RECAPTCHA_KEY)
        super(AskbotReCaptchaField, self).__init__(*args, **kwargs)


class LanguageField(forms.ChoiceField):

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = django_settings.LANGUAGES
        kwargs['label'] = _('Select language')
        super(LanguageField, self).__init__(*args, **kwargs)


class LanguageForm(forms.Form):
    language = LanguageField()


class LanguagePrefsForm(forms.Form):
    languages = forms.MultipleChoiceField(
                        widget=forms.CheckboxSelectMultiple,
                        choices=django_settings.LANGUAGES,
                        required=False)
    primary_language = forms.ChoiceField(
                        choices=django_settings.LANGUAGES)


class TranslateUrlForm(forms.Form):
    language = LanguageField()
    url = forms.CharField(max_length=2048)


class SuppressEmailField(forms.BooleanField):
    def __init__(self):
        super(SuppressEmailField, self).__init__()
        self.required = False
        self.label = _("minor edit (don't send alerts)")


class DomainNameField(forms.CharField):
    """Field for Internet Domain Names
    todo: maybe there is a standard field for this?
    """
    def clean(self, value):
        # find a better regex, taking into account tlds
        domain_re = re.compile(r'[a-zA-Z\d]+(\.[a-zA-Z\d]+)+')
        if domain_re.match(value):
            return value
        else:
            raise forms.ValidationError(
                '%s is not a valid domain name' % value
            )


class TitleField(forms.CharField):
    """Field receiving question title"""
    def __init__(self, *args, **kwargs):
        super(TitleField, self).__init__(*args, **kwargs)
        self.required = kwargs.get('required', True)
        self.widget = forms.TextInput(
                            attrs={'size': 70, 'autocomplete': 'off'})
        self.max_length = 255
        self.label = askbot_settings.WORDS_PLEASE_ENTER_YOUR_QUESTION
        self.initial = ''

    def clean(self, value):
        """cleans the field for minimum and maximum length
        also is supposed to work for unicode non-ascii characters"""
        if value is None:
            value = ''

        chars = slugify(value).replace('-', '')
        if len(chars) < askbot_settings.MIN_TITLE_LENGTH:
            msg = ngettext_lazy(
                'must have > %d non-punctuation character',
                'must have > %d non-punctuation characters',
                askbot_settings.MIN_TITLE_LENGTH
            ) % askbot_settings.MIN_TITLE_LENGTH
            raise forms.ValidationError(msg)

        encoded_value = value.encode('utf-8')
        if len(value) == len(encoded_value):
            if len(value) > self.max_length:
                raise forms.ValidationError(
                    _(
                        'The input is too long, maximum %(length)d characters is allowed'
                    ) % {'length': self.max_length}
                )
        elif len(encoded_value) > self.max_length:
            raise forms.ValidationError(
                _('The input is too long, maximum %(length)d bytes is allowed'
                ) % {'length': self.max_length}
            )

        return value.strip()  # TODO: test me


class EditorField(forms.CharField):
    """EditorField is subclassed by the
    :class:`QuestionEditorField` and :class:`AnswerEditorField`
    """

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        if user is None:
            raise ValueError('user parameter is required')
        self.user = user

        editor_attrs = kwargs.pop('editor_attrs', {})
        widget_attrs = kwargs.pop('attrs', {})
        widget_attrs.setdefault('id', 'editor')

        super(EditorField, self).__init__(*args, **kwargs)
        self.required = True
        if askbot_settings.EDITOR_TYPE == 'markdown':
            self.widget = forms.Textarea(attrs=widget_attrs)
        self.min_length = 10

    def clean(self, value):
        value = value or ''
        text_length = len(value.strip())

        if text_length < self.min_length:
            msg = ngettext_lazy(
                'enter > %(length)d character',
                'enter > %(length)d characters',
                self.min_length
            ) % {'length': self.min_length}
            raise forms.ValidationError(msg)

        if self.user.is_anonymous:
            # we postpone this validation if user is posting
            # before logging in, up until publishing the post
            return value

        try:
            self.user.assert_can_post_text(value)
        except PermissionDenied as err:
            raise forms.ValidationError(str(err))

        return value


class QuestionEditorField(EditorField):
    """Editor field for the questions"""

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(QuestionEditorField, self).__init__(
                                user=user, *args, **kwargs)
        self.min_length = askbot_settings.MIN_QUESTION_BODY_LENGTH


class AnswerEditorField(EditorField):
    """Editor field for answers"""

    def __init__(self, *args, **kwargs):
        super(AnswerEditorField, self).__init__(*args, **kwargs)
        self.min_length = askbot_settings.MIN_ANSWER_BODY_LENGTH


def clean_tag(tag_name, look_in_db=True):
    """a function that cleans a single tag name"""
    tag_name = unicodedata.normalize('NFC', tag_name)
    tag_length = len(tag_name)
    if tag_length > askbot_settings.MAX_TAG_LENGTH:
        # singular form is odd in english, but required for pluralization
        # in other languages
        msg = ngettext_lazy(
            # odd but added for completeness
            'each tag must be shorter than %(max_chars)d character',
            'each tag must be shorter than %(max_chars)d characters',
            tag_length
        ) % {'max_chars': tag_length}
        raise forms.ValidationError(msg)

    # TODO - this needs to come from settings
    tagname_re = re.compile(const.TAG_REGEX, re.UNICODE)
    if not tagname_re.search(tag_name):
        if tag_name[0] in const.TAG_FORBIDDEN_FIRST_CHARS:
            raise forms.ValidationError(
                _(message_keys.TAG_WRONG_FIRST_CHAR_MESSAGE))
        else:
            raise forms.ValidationError(
                _(message_keys.TAG_WRONG_CHARS_MESSAGE))

    if askbot_settings.FORCE_LOWERCASE_TAGS:
        # a simpler way to handle tags - just lowercase thew all
        return tag_name.lower()
    elif not look_in_db:
        return tag_name
    else:
        from askbot import models
        matching_tags = models.Tag.objects.filter(
                                            name__iexact=tag_name,
                                            language_code=get_language())
        if matching_tags:
            return matching_tags[0].name
        else:
            return tag_name


class TagNamesField(forms.CharField):
    """field that receives AskBot tag names"""

    def __init__(self, *args, **kwargs):
        super(TagNamesField, self).__init__(*args, **kwargs)
        self.required = kwargs.get('required',
                                   askbot_settings.TAGS_ARE_REQUIRED)
        self.widget = forms.TextInput(
            attrs={'size': 50, 'autocomplete': 'off'}
        )
        self.max_length = 255
        self.error_messages['max_length'] = _(
                            'We ran out of space for recording the tags. '
                            'Please shorten or delete some of them.')
        self.label = kwargs.get('label') or _('tags')
        self.help_text = kwargs.get('help_text') or ngettext_lazy(
            'Tags are short keywords, with no spaces within. '
            'Up to %(max_tags)d tag can be used.',
            'Tags are short keywords, with no spaces within. '
            'Up to %(max_tags)d tags can be used.',
            askbot_settings.MAX_TAGS_PER_POST
        ) % {'max_tags': askbot_settings.MAX_TAGS_PER_POST}
        self.initial = ''

    def clean(self, value):
        from askbot import models
        value = super(TagNamesField, self).clean(value)
        data = value.strip(const.TAG_STRIP_CHARS)
        if not data:
            if askbot_settings.TAGS_ARE_REQUIRED:
                raise forms.ValidationError(
                    _(message_keys.TAGS_ARE_REQUIRED_MESSAGE))
            else:
                # don't test for required characters when tags is ''
                return ''
        tag_strings = split_tags(data)
        entered_tags = []
        tag_count = len(tag_strings)
        if tag_count > askbot_settings.MAX_TAGS_PER_POST:
            max_tags = askbot_settings.MAX_TAGS_PER_POST
            msg = ngettext_lazy(
                        'please use %(tag_count)d tag or less',
                        'please use %(tag_count)d tags or less',
                        tag_count) % {'tag_count': max_tags}
            raise forms.ValidationError(msg)

        if need_mandatory_tags():
            if mandatory_tag_missing_in_list(tag_strings):
                msg = _(
                    'At least one of the following tags is required : %(tags)s'
                ) % {'tags': get_text_list(models.tag.get_mandatory_tags())}
                raise forms.ValidationError(msg)

        cleaned_entered_tags = list()
        for tag in tag_strings:
            cleaned_tag = clean_tag(tag)
            if cleaned_tag not in cleaned_entered_tags:
                cleaned_entered_tags.append(clean_tag(tag))

        result = ' '.join(cleaned_entered_tags)

        if len(result) > 125:  # magic number!, the same as max_length in db
            raise forms.ValidationError(self.error_messages['max_length'])

        return ' '.join(cleaned_entered_tags)


class WikiField(forms.BooleanField):
    """Rendered as checkbox turning post into
    "community wiki"
    """

    def __init__(self, *args, **kwargs):
        super(WikiField, self).__init__(*args, **kwargs)
        self.required = False
        self.initial = False
        self.label = _(
            'community wiki (karma is not awarded & '
            'many others can edit wiki post)'
        )

    def clean(self, value):
        return value and askbot_settings.WIKI_ON


class PageField(forms.IntegerField):

    def __init__(self, *args, **kwargs):
        self.required = False
        super(PageField, self).__init__(*args, **kwargs)

    def clean(self, value):
        try:
            value = int(value)
            return value if value > 0 else 1
        except (TypeError, ValueError):
            return 1


class SortField(forms.ChoiceField):
    def __init__(self, *args, **kwargs):
        self.default = kwargs.pop('default', '')
        super(SortField, self).__init__(*args, **kwargs)

    def clean(self, value):
        value = value or self.default
        if value not in list(dict(self.choices).keys()):
            value = self.default
        return value


class SummaryField(forms.CharField):

    def __init__(self, *args, **kwargs):
        super(SummaryField, self).__init__(*args, **kwargs)
        self.required = False
        self.widget = forms.TextInput(
            attrs={'size': 50, 'autocomplete': 'off'})
        self.max_length = 300
        self.label = _('update summary:')
        self.help_text = _(
            'enter a brief summary of your revision (e.g. '
            'fixed spelling, grammar, improved style...), this '
            'field is optional')


class EditorForm(forms.Form):
    """form with one field - `editor`
    the field must be created dynamically, so it's added
    in the __init__() function"""

    def __init__(self, attrs=None, user=None, editor_attrs=None):
        super(EditorForm, self).__init__()
        editor_attrs = editor_attrs or {}
        self.fields['editor'] = EditorField(attrs=attrs,
                                            editor_attrs=editor_attrs,
                                            user=user)


class DumpUploadForm(forms.Form):
    """This form handles importing
    data into the forum. At the moment it only
    supports stackexchange import.
    """
    dump_file = forms.FileField()


class ShowQuestionForm(forms.Form):
    """Cleans data necessary to access answers and comments
    by the respective comment or answer id - necessary
    when comments would be normally wrapped and/or displayed
    on the page other than the first page of answers to a question.
    Same for the answers that are shown on the later pages.
    """
    answer = forms.IntegerField(required=False)
    comment = forms.IntegerField(required=False)
    page = PageField()

    def __init__(self, *args, **kwargs):
        super(ShowQuestionForm, self).__init__(*args, **kwargs)
        # uses livesettings for the default so the 'sort' field
        # must be added in the __init__
        self.fields['sort'] = SortField(
                choices=const.ANSWER_SORT_METHODS,
                default=askbot_settings.DEFAULT_ANSWER_SORT_METHOD)

    def get_pruned_data(self):
        nones = ('answer', 'comment', 'page')
        for key in nones:
            if key in self.cleaned_data:
                if self.cleaned_data[key] is None:
                    del self.cleaned_data[key]
        if 'sort' in self.cleaned_data:
            if self.cleaned_data['sort'] == '':
                del self.cleaned_data['sort']
        return self.cleaned_data

    def clean(self):
        """this form must always be valid
        should use defaults if the data is incomplete
        or invalid"""
        if self._errors:
            # since the form is always valid, clear the errors
            logging.error(str(self._errors))
            self._errors = {}

        in_data = self.get_pruned_data()
        out_data = dict()
        default_answer_sort = askbot_settings.DEFAULT_ANSWER_SORT_METHOD
        if ('answer' in in_data) ^ ('comment' in in_data):
            out_data['show_page'] = None
            out_data['answer_sort_method'] = default_answer_sort
            out_data['show_comment'] = in_data.get('comment', None)
            out_data['show_answer'] = in_data.get('answer', None)
        else:
            out_data['show_page'] = in_data.get('page', 1)
            answer_sort_method = in_data.get('sort', default_answer_sort)
            out_data['answer_sort_method'] = answer_sort_method
            out_data['show_comment'] = None
            out_data['show_answer'] = None
        self.cleaned_data = out_data
        return out_data


class ShowTagsForm(forms.Form):
    page = PageField()
    sort = SortField(choices=const.TAGS_SORT_METHODS,
                     default=const.DEFAULT_TAGS_SORT_METHOD)
    query = forms.CharField(required=False)


class ShowUsersForm(forms.Form):
    page = PageField()
    sort = SortField(choices=const.USER_SORT_METHODS,
                     default=const.DEFAULT_USER_SORT_METHOD)
    query = forms.CharField(required=False)

    def clean_sort(self):
        sort_method = self.cleaned_data['sort']
        if sort_method == 'reputation' and askbot_settings.KARMA_MODE == 'private':
            self.cleaned_data['sort'] = 'newest'
        return self.cleaned_data['sort']


class ChangeUserReputationForm(forms.Form):
    """Form that allows moderators and site administrators
    to adjust reputation of users.

    this form internally verifies that user who claims to
    be a moderator acually is
    """

    user_reputation_delta = forms.IntegerField(
        min_value=1, max_value=32767,
        label=_('Enter number of points'))
    comment = forms.CharField(label=_('Comment'), max_length=128)

    def clean_comment(self):
        if 'comment' in self.cleaned_data:
            comment = self.cleaned_data['comment'].strip()
            if comment == '':
                del self.cleaned_data['comment']
                raise forms.ValidationError('Please enter non-empty comment')
            self.cleaned_data['comment'] = comment
            return comment

MODERATOR_STATUS_CHOICES = (
    ('a', _('approved')),
    ('w', _('watched')),
    ('s', _('suspended')),
    ('b', _('blocked')),
)
ADMINISTRATOR_STATUS_CHOICES = (
    ('d', _('administrator')),
    ('m', _('moderator')),
) + MODERATOR_STATUS_CHOICES


class ChangeUserStatusForm(forms.Form):
    """form that allows moderators to change user's status

    the type of options displayed depend on whether user
    is a moderator or a site administrator as well as
    what is the current status of the moderated user

    for example moderators cannot moderate other moderators
    and admins. Admins can take away admin status, but cannot
    add it (that can be done through the Django Admin interface

    this form is to be displayed in the user profile under
    "moderation" tab
    """

    user_status = forms.ChoiceField(label=_('Change status to'))
    delete_content = forms.CharField(widget=forms.HiddenInput, initial='false')

    def __init__(self, *arg, **kwarg):

        moderator = kwarg.pop('moderator')
        subject = kwarg.pop('subject')

        super(ChangeUserStatusForm, self).__init__(*arg, **kwarg)

        # Select user_status_choices depending on status of the moderator
        if moderator.is_authenticated:
            if moderator.is_administrator():
                user_status_choices = ADMINISTRATOR_STATUS_CHOICES
            elif moderator.is_moderator():
                user_status_choices = MODERATOR_STATUS_CHOICES
                if subject.is_moderator() and subject != moderator:
                    raise ValueError('moderator cannot moderate another moderator')
        else:
            raise ValueError('moderator or admin expected from "moderator"')

        # remove current status of the "subject" user from choices
        user_status_choices = filter_choices(
                                        remove_choices=[subject.status, ],
                                        from_choices=user_status_choices
                                    )

        # add prompt option
        user_status_choices = (
            ('select', _('which one?')),
        ) + user_status_choices

        self.fields['user_status'].choices = user_status_choices

        # set prompt option as default
        self.fields['user_status'].default = 'select'
        self.moderator = moderator
        self.subject = subject

    def clean_delete_content(self):
        delete = self.cleaned_data.get('delete_content', False)
        if delete == 'true':
            delete = True
        else:
            delete = False
        self.cleaned_data['delete_content'] = delete
        return self.cleaned_data['delete_content']

    def clean(self):
        # if moderator is looking at own profile - do not
        # let change status
        if 'user_status' in self.cleaned_data:
            user_status = self.cleaned_data['user_status']
            # does not make sense to change own user status
            # if necessary, this can be done from the Django admin interface
            if self.moderator == self.subject:
                del self.cleaned_data['user_status']
                raise forms.ValidationError(_('Cannot change own status'))

            # do not let moderators turn other users into moderators
            if self.moderator.is_moderator() and user_status == 'moderator':
                del self.cleanded_data['user_status']
                raise forms.ValidationError(
                                _('Cannot turn other user to moderator'))

            # do not allow moderator to change status of other moderators
            if self.moderator.is_moderator() and self.subject.is_moderator():
                del self.cleaned_data['user_status']
                raise forms.ValidationError(
                                _('Cannot change status of another moderator'))

            # do not allow moderator to change to admin
            if self.moderator.is_moderator() and user_status == 'd':
                raise forms.ValidationError(
                                _("Cannot change status to admin"))

            if user_status == 'select':
                del self.cleaned_data['user_status']
                msg = _(
                        'If you wish to change %(username)s\'s status, '
                        'please make a meaningful selection.'
                    ) % {'username': self.subject.username}
                raise forms.ValidationError(msg)

            if user_status not in ('s', 'b'):  # not blocked or suspended
                if self.cleaned_data['delete_content']:
                    self.cleaned_data['delete_content'] = False

        return self.cleaned_data


class SendMessageForm(forms.Form):
    subject_line = forms.CharField(
        label=_('Subject line'), max_length=64,
        widget=forms.TextInput(attrs={'size': 64}))
    body_text = forms.CharField(
        label=_('Message text'), max_length=1600,
        widget=forms.Textarea(attrs={'cols': 64}))


class FeedbackForm(forms.Form):
    name = forms.CharField(label=_('Your name (optional):'), required=False)
    email = forms.EmailField(label=_('Email:'), required=False)
    message = forms.CharField(label=_('Your message:'),
                              widget=forms.Textarea(attrs={'cols': 60}))
    no_email = forms.BooleanField(
        label=_("I don't want to give my email or receive a response:"),
        required=False)
    next = NextUrlField()

    def __init__(self, user=None, *args, **kwargs):
        super(FeedbackForm, self).__init__(*args, **kwargs)
        self.user = user
        if should_use_recaptcha(user):
            self.fields['recaptcha'] = AskbotReCaptchaField()

    def clean_message(self):
        message = self.cleaned_data.get('message', '').strip()
        if not message:
            raise forms.ValidationError(_('Message is required'))
        return message

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            name = _('Anonymous')
        self.cleaned_data['name'] = name
        return name

    def clean(self):
        super(FeedbackForm, self).clean()
        if self.user and self.user.is_anonymous:
            need_email = not bool(self.cleaned_data.get('no_email', False))
            email = self.cleaned_data.get('email', '').strip()
            if need_email and email == '':
                msg = _("""Either provide email address or mark "I don't want to give my email" below""")
                self._errors['email'] = self.error_class([msg])

        return self.cleaned_data


class FormWithHideableFields(object):
    """allows to swap a field widget to HiddenInput() and back"""

    def hide_field(self, name):
        """replace widget with HiddenInput()
        and save the original in the __hidden_fields dictionary
        """
        if not hasattr(self, '__hidden_fields'):
            self.__hidden_fields = dict()
        if name in self.__hidden_fields:
            return
        self.__hidden_fields[name] = self.fields[name].widget
        self.fields[name].widget = forms.HiddenInput()

    def show_field(self, name):
        """restore the original widget on the field
        if it was previously hidden
        """
        if name in self.__hidden_fields:
            self.fields[name] = self.__hidden_fields.pop(name)


class PostPrivatelyForm(forms.Form, FormWithHideableFields):
    """has a single field `post_privately` with
    two related methods"""

    post_privately = forms.BooleanField(
        label=_('keep private within your groups'), required=False)

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        self._user = user
        super(PostPrivatelyForm, self).__init__(*args, **kwargs)
        if self.allows_post_privately() == False:
            self.hide_field('post_privately')

    def allows_post_privately(self):
        user = self._user
        return (
            askbot_settings.GROUPS_ENABLED and
            user and user.is_authenticated and
            user.can_make_group_private_posts()
        )

    def clean_post_privately(self):
        if not self.allows_post_privately():
            self.cleaned_data['post_privately'] = False
        return self.cleaned_data['post_privately']


class DraftQuestionForm(forms.Form):
    """No real validation required for this form"""
    title = forms.CharField(required=False)
    text = forms.CharField(required=False)
    tagnames = forms.CharField(required=False)


class DraftAnswerForm(forms.Form):
    """Only thread_id is required"""
    thread_id = forms.IntegerField()
    text = forms.CharField(required=False)


class PostAsSomeoneForm(forms.Form):
    post_author_username = forms.CharField(
        initial=_('User name:'), required=False,
        help_text=_('Enter name to post on behalf of someone else. '
                    'Can create new accounts.'),
        widget=forms.TextInput(attrs={'class': 'tipped-input blank'}))
    post_author_email = forms.CharField(
        initial=_('Email address:'), required=False,
        widget=forms.TextInput(attrs={'class': 'tipped-input'})
    )

    def get_post_user(self, user):
        """returns user on whose behalf the post or a revision
        is being made
        """
        username = self.cleaned_data['post_author_username']
        email = self.cleaned_data['post_author_email']
        if user.is_administrator() and username and email:
            post_user = user.get_or_create_fake_user(username, email, status='a')
        else:
            post_user = user
        return post_user

    def clean_post_author_username(self):
        """if value is the same as initial, it is reset to
        empty string
        todo: maybe better to have field where initial value is invalid,
        then we would not have to have two almost identical clean functions?
        """
        username = self.cleaned_data.get('post_author_username', '').strip()
        initial_username = str(self.fields['post_author_username'].initial)
        if username and username == initial_username:
            self.cleaned_data['post_author_username'] = ''
        return self.cleaned_data['post_author_username']

    def clean_post_author_email(self):
        """if value is the same as initial, it is reset to
        empty string"""
        email = self.cleaned_data.get('post_author_email', '').strip()
        initial_email = str(self.fields['post_author_email'].initial)
        if email == initial_email:
            email = ''
        if email != '':
            email = forms.EmailField().clean(email)
        self.cleaned_data['post_author_email'] = email
        return email

    def clean(self):
        """requires email address if user name is given"""
        username = self.cleaned_data.get('post_author_username', '')
        email = self.cleaned_data.get('post_author_email', '')
        if username == '' and email:
            username_errors = self._errors.get('post_author_username',
                                               ErrorList())
            username_errors.append(_('User name is required with the email'))
            self._errors['post_author_username'] = username_errors
            raise forms.ValidationError('missing user name')
        elif email == '' and username:
            email_errors = self._errors.get('post_author_email', ErrorList())
            email_errors.append(_('Email is required if user name is added'))
            self._errors['post_author_email'] = email_errors
            raise forms.ValidationError('missing email')

        return self.cleaned_data


class AskForm(PostAsSomeoneForm, PostPrivatelyForm):
    """the form used to askbot questions
    field ask_anonymously is shown to the user if the
    if ALLOW_ASK_ANONYMOUSLY live setting is True
    however, for simplicity, the value will always be present
    in the cleaned data, and will evaluate to False if the
    settings forbids anonymous asking
    """
    wiki = WikiField()
    group_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    openid = forms.CharField(
        required=False, max_length=255,
        widget=forms.TextInput(attrs={'size': 40, 'class': 'openid-input'}))

    def __init__(self, *args, **kwargs):
        user = kwargs.get('user', None)
        self.user = user
        super(AskForm, self).__init__(*args, **kwargs)
        # It's important that this field is set up dynamically
        self.fields['title'] = TitleField()
        self.fields['tags'] = TagNamesField()

        if askbot_settings.MIN_QUESTION_BODY_LENGTH == 0:
            label = _('Add details below (optional)')
        else:
            label = _('Add details below')

        self.fields['text'] = QuestionEditorField(user=user, label=label)

        self.fields['ask_anonymously'] = forms.BooleanField(
            label=_('post anonymously'), required=False)

        if user.is_anonymous or not askbot_settings.ALLOW_ASK_ANONYMOUSLY:
            self.hide_field('ask_anonymously')

        if askbot.is_multilingual():
            self.fields['language'] = LanguageField()

        if should_use_recaptcha(user):
            self.fields['recaptcha'] = AskbotReCaptchaField()

    def clean_ask_anonymously(self):
        """returns false if anonymous asking is not allowed
        """
        if not askbot_settings.ALLOW_ASK_ANONYMOUSLY:
            self.cleaned_data['ask_anonymously'] = False
        return self.cleaned_data['ask_anonymously']

    def clean_tags(self):
        tags = TagNamesField().clean(self.cleaned_data['tags'])
        if not askbot_settings.ADMIN_TAGS_ENABLED:
            return tags

        if self.user and self.user.is_authenticated and self.user.is_admin_or_mod():
            return tags
        admin_tags = set(split_tags(askbot_settings.ADMIN_TAGS))
        bad_tags = set(split_tags(tags)) & admin_tags
        if bad_tags:
            if len(bad_tags) == 1:
                message = _('Only administrators and moderators can add the tag "%s"') % bad_tags.pop()
            else:
                message = _('Only administrators and moderators can add the tags "%s"') % ', '.join(bad_tags)
            raise forms.ValidationError(message)
        return tags

ASK_BY_EMAIL_SUBJECT_HELP = _(
    'Subject line is expected in the format: '
    '[tag1, tag2, tag3,...] question title'
)


# widgetforms
class AskWidgetForm(forms.Form, FormWithHideableFields):
    '''Simple form with just the title to ask a question'''

    ask_anonymously = forms.BooleanField(
        label=_('ask anonymously'), required=False)

    def __init__(self, include_text=True, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(AskWidgetForm, self).__init__(*args, **kwargs)
        self.fields['title'] = TitleField()
        # hide ask_anonymously field
        if user.is_anonymous or not askbot_settings.ALLOW_ASK_ANONYMOUSLY:
            self.hide_field('ask_anonymously')
        self.fields['text'] = QuestionEditorField(user=user)
        if not include_text:
            self.hide_field('text')
            # hack to make it validate
            self.fields['text'].required = False
            self.fields['text'].min_length = 0

        if should_use_recaptcha(user):
            self.fields['recaptcha'] = AskbotReCaptchaField()


class CreateAskWidgetForm(forms.Form, FormWithHideableFields):
    title = forms.CharField(max_length=100)
    include_text_field = forms.BooleanField(required=False)

    inner_style = forms.CharField(widget=forms.Textarea, required=False)
    outer_style = forms.CharField(widget=forms.Textarea, required=False)

    def __init__(self, *args, **kwargs):
        from askbot.models import Group, Tag
        super(CreateAskWidgetForm, self).__init__(*args, **kwargs)
        self.fields['group'] = forms.ModelChoiceField(
            queryset=Group.objects.exclude_personal(), required=False)
        self.fields['tag'] = forms.ModelChoiceField(
            queryset=Tag.objects.get_content_tags(), required=False)
        if not askbot_settings.GROUPS_ENABLED:
            self.hide_field('group')


class CreateQuestionWidgetForm(forms.Form, FormWithHideableFields):
    title = forms.CharField(max_length=100)
    question_number = forms.CharField(initial='7')
    tagnames = forms.CharField(label=_('tags'), max_length=50)
    search_query = forms.CharField(max_length=50, required=False)
    order_by = forms.ChoiceField(choices=const.SEARCH_ORDER_BY,
                                 initial='-added_at')
    style = forms.CharField(widget=forms.Textarea, required=False,
                            initial=const.DEFAULT_QUESTION_WIDGET_STYLE)

    def __init__(self, *args, **kwargs):
        from askbot.models import Group
        super(CreateQuestionWidgetForm, self).__init__(*args, **kwargs)
        self.fields['tagnames'] = TagNamesField()
        self.fields['group'] = forms.ModelChoiceField(
            queryset=Group.objects.exclude(name__startswith='_internal'),
            required=False)


class AskByEmailForm(forms.Form):
    """:class:`~askbot.forms.AskByEmailForm`
    validates question data, where question was posted
    by email.

    It is ivoked by the management command
    :mod:`~askbot.management.commands.post_emailed_questions`

    Input is text data with attributes:

    * :attr:`~askbot.forms.AskByEmailForm.sender` - unparsed "from" data
    * :attr:`~askbot.forms.AskByEmailForm.subject` - subject line
    * :attr:`~askbot.forms.AskByEmailForm.body_text` - body text of the email

    Cleaned values are:
    * ``email`` - email address
    * ``title`` - question title
    * ``tagnames`` - tag names all in one string
    * ``body_text`` - body of question text -
      a pass-through, no extra validation
    """
    sender = forms.CharField(max_length=255)
    subject = forms.CharField(
        max_length=255, error_messages={
            'required': ASK_BY_EMAIL_SUBJECT_HELP
        })

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(AskByEmailForm, self).__init__(*args, **kwargs)
        self.fields['body_text'] = QuestionEditorField(user=user)

    def clean_sender(self):
        """Cleans the :attr:`~askbot.forms.AskByEmail.sender` attribute

        If the field is valid, cleaned data will receive value ``email``
        """
        raw_email = self.cleaned_data['sender']
        email = extract_first_email_address(raw_email)
        if email is None:
            raise forms.ValidationError('Could not extract email address')
        self.cleaned_data['email'] = email
        return self.cleaned_data['sender']

    def clean_subject(self):
        """Cleans the :attr:`~askbot.forms.AskByEmail.subject` attribute

        If the field is valid, cleaned data will receive values
        ``tagnames`` and ``title``
        """
        raw_subject = self.cleaned_data['subject'].strip()
        if askbot_settings.TAGS_ARE_REQUIRED:
            subject_re = re.compile(r'^\[([^]]+)\](.*)$')
        else:
            subject_re = re.compile(r'^(?:\[([^]]+)\])?(.*)$')
        match = subject_re.match(raw_subject)
        if match:
            # make raw tags comma-separated
            if match.group(1) is None:  # no tags
                self.cleaned_data['tagnames'] = ''
            else:
                tagnames = match.group(1).replace(';', ',')

                # pre-process tags
                tag_list = [tag.strip() for tag in tagnames.split(',')]
                tag_list = [re.sub(r'\s+', ' ', tag) for tag in tag_list]

                if askbot_settings.REPLACE_SPACE_WITH_DASH_IN_EMAILED_TAGS:
                    tag_list = [tag.replace(' ', '-') for tag in tag_list]
                # TODO: use tag separator char here
                tagnames = ' '.join(tag_list)

                # clean tags - may raise ValidationError
                self.cleaned_data['tagnames'] = TagNamesField().clean(tagnames)

            # clean title - may raise ValidationError
            title = match.group(2).strip()
            self.cleaned_data['title'] = TitleField().clean(title)
        else:
            raise forms.ValidationError(ASK_BY_EMAIL_SUBJECT_HELP)
        return self.cleaned_data['subject']


class AnswerForm(PostAsSomeoneForm, PostPrivatelyForm):
    wiki = WikiField()
    openid = forms.CharField(
        required=False, max_length=255,
        widget=forms.TextInput(attrs={'size': 40, 'class': 'openid-input'}))

    def __init__(self, *args, **kwargs):
        super(AnswerForm, self).__init__(*args, **kwargs)
        user = kwargs['user']
        # empty label on purpose
        self.fields['text'] = AnswerEditorField(label='', user=user)

        if should_use_recaptcha(user):
            self.fields['recaptcha'] = AskbotReCaptchaField()

    def save(self, question, user, ip_addr=None):
        wiki = self.cleaned_data['wiki']
        text = self.cleaned_data['text']
        is_private = self.cleaned_data['post_privately']

        return user.post_answer(
            question=question, body_text=text, wiki=wiki,
            is_private=is_private, timestamp=timezone.now(),
            ip_addr=ip_addr)


class VoteForm(forms.Form):
    """form used in ajax vote view (only comment_upvote so far)
    """
    post_id = forms.IntegerField()
    # char because it is 'true' or 'false' as string
    cancel_vote = forms.CharField()

    def clean_cancel_vote(self):
        val = self.cleaned_data['cancel_vote']
        if val == 'true':
            result = True
        elif val == 'false':
            result = False
        else:
            del self.cleaned_data['cancel_vote']
            raise forms.ValidationError(
                    'either "true" or "false" strings expected')
        self.cleaned_data['cancel_vote'] = result
        return self.cleaned_data['cancel_vote']


class CloseForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super(CloseForm, self).__init__(*args, **kwargs)
        reasons = askbot_settings.QUESTION_CLOSE_REASONS
        close_choices = tuple([tuple([reason, reason]) for reason in reasons])
        self.fields['reason'] = forms.ChoiceField(choices=close_choices)


class RetagQuestionForm(forms.Form):

    def __init__(self, question, *args, **kwargs):
        """initialize the default values"""
        super(RetagQuestionForm, self).__init__(*args, **kwargs)
        self.fields['tags'] = TagNamesField()
        self.fields['tags'].initial = question.thread.tagnames


class RevisionForm(forms.Form):
    """
    Lists revisions of a Question or Answer
    """
    revision = forms.ChoiceField(widget=forms.Select())

    def __init__(self, post, latest_revision, *args, **kwargs):
        super(RevisionForm, self).__init__(*args, **kwargs)
        revisions = post.revisions.values_list(
            'revision', 'author__username', 'revised_at', 'summary'
        )
        date_format = '%c'
        rev_choices = list()
        for r in revisions:
            rev_details = '%s - %s (%s) %s' % (
                r[0], r[1], r[2].strftime(date_format), r[3])
            rev_choices.append((r[0], rev_details))

        self.fields['revision'].choices = rev_choices
        self.fields['revision'].initial = latest_revision.revision


class EditAnswerForm(PostAsSomeoneForm, PostPrivatelyForm):
    summary = SummaryField()
    wiki = WikiField()
    suppress_email = SuppressEmailField()

    def __init__(self, answer, revision, *args, **kwargs):
        self.answer = answer
        user = kwargs.get('user', None)
        super(EditAnswerForm, self).__init__(*args, **kwargs)
        # it is important to add this field dynamically
        # label is empty on purpose
        self.fields['text'] = AnswerEditorField(label='', user=user)
        self.fields['text'].initial = revision.text
        self.fields['wiki'].initial = answer.wiki

        if should_use_recaptcha(user):
            self.fields['recaptcha'] = AskbotReCaptchaField()

    def has_changed(self):
        if super(EditAnswerForm, self).has_changed():
            return True
        if askbot_settings.GROUPS_ENABLED:
            return self.answer.is_private() \
                != self.cleaned_data['post_privately']
        else:
            return False


class EditTagWikiForm(forms.Form):
    text = forms.CharField(required=False)
    tag_id = forms.IntegerField()


class EditUserForm(forms.Form):
    email = forms.EmailField(
        label='Email', required=False, max_length=255,
        widget=forms.TextInput(attrs={'size': 35}))

    realname = forms.CharField(
        label=_('Real name'), required=False, max_length=255,
        widget=forms.TextInput(attrs={'size': 35}))

    website = forms.URLField(
        label=_('Website'), required=False, max_length=PROFILE_WEBSITE_URL_MAX_LENGTH,
        widget=forms.TextInput(attrs={'size': 35}))

    city = forms.CharField(
        label=_('City'), required=False, max_length=255,
        widget=forms.TextInput(attrs={'size': 35}))

    country = CountryField(required=False)

    show_country = forms.BooleanField(label=_('Show country'), required=False)

    show_marked_tags = forms.BooleanField(
        label=_('Show tag choices'), required=False)

    birthday = forms.DateField(
        label=_('Date of birth'), required=False,
        help_text=_(
            'will not be shown, used to calculate '
            'age, format: YYYY-MM-DD'
            ),
        widget=forms.TextInput(attrs={'size': 35}))

    def __init__(self, user, *args, **kwargs):
        super(EditUserForm, self).__init__(*args, **kwargs)

        logging.debug('initializing the form')
        if askbot_settings.EDITABLE_SCREEN_NAME:
            self.fields['username'] = UserNameField(label=_('Screen name'))
            self.fields['username'].initial = user.username
            self.fields['username'].user_instance = user
        self.fields['email'].initial = user.email
        self.fields['realname'].initial = user.real_name
        self.fields['website'].initial = user.website
        self.fields['city'].initial = user.location
        if user.country is None:
            country = 'unknown'
        else:
            country = user.country.code
        self.fields['country'].initial = country
        self.fields['show_country'].initial = user.show_country
        self.fields['show_marked_tags'].initial = user.show_marked_tags

        if user.date_of_birth is not None:
            self.fields['birthday'].initial = user.date_of_birth

        self.user = user

    def clean_email(self):
        """For security reason one unique email in database"""
        email = self.cleaned_data.get('email', '').strip()
        if email == '' and askbot_settings.BLANK_EMAIL_ALLOWED:
            self.cleaned_data['email'] = ''
            return self.cleaned_data['email']

        if not askbot_settings.EDITABLE_EMAIL:
            self.cleaned_data['email'] = self.user.email
            return self.cleaned_data['email']

        moderated_email_validator(email)

        if email != self.user.email:
            # TODO dry it, there is a similar thing in openidauth
            try:
                User.objects.get(email=email)
            except User.DoesNotExist:
                return self.cleaned_data['email']
            except User.MultipleObjectsReturned:
                raise forms.ValidationError(_(
                    'this email has already been registered, '
                    'please use another one'))
            raise forms.ValidationError(_(
                'this email has already been registered, '
                'please use another one'))
        return self.cleaned_data['email']


class TagFilterSelectionForm(forms.ModelForm):
    email_tag_filter_strategy = forms.ChoiceField(
        initial=const.EXCLUDE_IGNORED,
        label=_('Choose email tag filter'),
        widget=forms.RadioSelect)

    def __init__(self, *args, **kwargs):
        super(TagFilterSelectionForm, self).__init__(*args, **kwargs)
        choices = get_tag_email_filter_strategy_choices()
        self.fields['email_tag_filter_strategy'].choices = choices

    class Meta:
        model = UserProfile
        fields = ('email_tag_filter_strategy',)

    def save(self):
        before = self.instance.email_tag_filter_strategy
        super(TagFilterSelectionForm, self).save()
        after = self.instance.email_tag_filter_strategy
        return before != after


class EmailFeedSettingField(forms.ChoiceField):
    def __init__(self, *arg, **kwarg):
        kwarg['choices'] = kwarg.get('choices', const.NOTIFICATION_DELIVERY_SCHEDULE_CHOICES)
        kwarg['widget'] = forms.RadioSelect
        super(EmailFeedSettingField, self).__init__(*arg, **kwarg)


class EditUserEmailFeedsForm(forms.Form):
    FORM_TO_MODEL_MAP = {
        'all_questions': 'q_all',
        'asked_by_me': 'q_ask',
        'answered_by_me': 'q_ans',
        'individually_selected': 'q_sel',
        'mentions_and_comments': 'm_and_c',
        'unanswered_questions': 'q_noans'
    }
    NO_EMAIL_INITIAL = {
        'all_questions': 'n',
        'asked_by_me': 'n',
        'answered_by_me': 'n',
        'individually_selected': 'n',
        'unanswered_questions': 'n',
        'mentions_and_comments': 'n',
    }
    INSTANT_EMAIL_INITIAL = {
        'all_questions': 'i',
        'asked_by_me': 'i',
        'answered_by_me': 'i',
        'individually_selected': 'i',
        'unanswered_questions': 'd',
        'mentions_and_comments': 'i',
    }

    def __init__(self, *args, **kwargs):
        super(EditUserEmailFeedsForm, self).__init__(*args, **kwargs)
        self.fields = OrderedDict((
            ('asked_by_me', EmailFeedSettingField(label=askbot_settings.WORDS_ASKED_BY_ME)),
            ('answered_by_me', EmailFeedSettingField(label=askbot_settings.WORDS_ANSWERED_BY_ME)),
            ('individually_selected', EmailFeedSettingField(label=_('Individually selected'))),
            ('unanswered_questions',
                EmailFeedSettingField(
                    label=_('Unanswered questions'),
                    choices=const.NOTIFICATION_DELIVERY_SCHEDULE_CHOICES_Q_NOANS
                )
            ),
            ('all_questions', EmailFeedSettingField(label=_('Entire forum (tag filtered)'))),
            ('mentions_and_comments', EmailFeedSettingField(label=_('Comments and posts mentioning me'))),
        ))

    def set_initial_values(self, user=None):
        from askbot import models
        KEY_MAP = dict([(v, k) for k, v in self.FORM_TO_MODEL_MAP.items()])
        if user is not None:
            settings = models.EmailFeedSetting.objects.filter(subscriber=user)
            initial_values = {}
            for setting in settings:
                feed_type = setting.feed_type
                form_field = KEY_MAP[feed_type]
                frequency = setting.frequency
                initial_values[form_field] = frequency
            self.initial = initial_values
        return self

    def reset(self):
        """equivalent to set_frequency('n')
        but also returns self due to some legacy requirement
        """
        # TODO: clean up use of this function
        if self.is_bound:
            self.cleaned_data = self.NO_EMAIL_INITIAL
        self.initial = self.NO_EMAIL_INITIAL
        return self

    def get_db_model_subscription_type_names(self):
        """
        returns list of values acceptable in
        ``attr::models.user.EmailFeedSetting.feed_type``
        """
        # TODO: refactor this - too hacky
        # should probably use model form instead

        return list(self.FORM_TO_MODEL_MAP.values())

    def set_frequency(self, frequency='n'):
        data = {
            'all_questions': frequency,
            'unanswered_questions': frequency,
            'asked_by_me': frequency,
            'answered_by_me': frequency,
            'individually_selected': frequency,
            'mentions_and_comments': frequency
        }
        if self.is_bound:
            self.cleaned_data = data
        self.initial = data

    def save(self, user, save_unbound=False):
        """with save_unbound==True will bypass form
        validation and save initial values
        """
        from askbot import models
        changed = False
        for form_field, feed_type in list(self.FORM_TO_MODEL_MAP.items()):
            s, created = models.EmailFeedSetting.objects.get_or_create(
                    subscriber=user, feed_type=feed_type)
            if save_unbound:
                # just save initial values instead
                if form_field in self.initial:
                    new_value = self.initial[form_field]
                else:
                    new_value = self.fields[form_field].initial
            else:
                new_value = self.cleaned_data[form_field]
            if s.frequency != new_value:
                s.frequency = new_value
                s.save()
                changed = True
            else:
                if created:
                    s.save()
            if form_field == 'individually_selected':
                user.followed_threads.clear()
        return changed


class SubscribeForEmailUpdatesField(forms.ChoiceField):
    """a simple yes or no field to subscribe for email or not"""
    def __init__(self, **kwargs):
        kwargs['widget'] = forms.widgets.RadioSelect
        kwargs['error_messages'] = {
            'required': _('please choose one of the options above')
        }
        kwargs['choices'] = (
            ('y', _('okay, let\'s try!')),
            ('n', _('no %(sitename)s email please, thanks')
             % {'sitename': askbot_settings.APP_SHORT_NAME})
        )
        super(SubscribeForEmailUpdatesField, self).__init__(**kwargs)


class SimpleEmailSubscribeForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(SimpleEmailSubscribeForm, self).__init__(*args, **kwargs)
        self.fields['subscribe'] = SubscribeForEmailUpdatesField()

    def save(self, user=None):
        EFF = EditUserEmailFeedsForm
        # here we have kind of an anomaly - the value 'y' is redundant
        # with the frequency variable - needs to be fixed
        if self.is_bound and self.cleaned_data['subscribe'] == 'y':
            email_settings_form = EFF()
            email_settings_form.set_initial_values(user)
            logging.debug('%s wants to subscribe' % user.username)
        else:
            email_settings_form = EFF(initial=EFF.NO_EMAIL_INITIAL)
        email_settings_form.save(user, save_unbound=True)


class UnsubscribeForm(forms.Form):
    key = forms.CharField(widget=forms.HiddenInput)
    email = forms.EmailField(widget=forms.HiddenInput)

    def clean_key(self):
        key = self.cleaned_data['key']
        if not re.match('[\da-z].*', key):
            raise forms.ValidationError(_('Invalid key'))
        return key

class GroupLogoURLForm(forms.Form):
    """form for saving group logo url"""
    group_id = forms.IntegerField()
    image_url = forms.CharField()


class EditGroupMembershipForm(forms.Form):
    """a form for adding or removing users
    to and from user groups"""
    user_id = forms.IntegerField()
    group_name = forms.CharField()
    action = forms.CharField()

    def clean_action(self):
        """allowed actions are 'add' and 'remove'"""
        action = self.cleaned_data['action']
        if action not in ('add', 'remove'):
            del self.cleaned_data['action']
            raise forms.ValidationError('invalid action')
        return action


class EditRejectReasonForm(forms.Form):
    reason_id = forms.IntegerField(required=False)
    title = CountedWordsField(min_words=1, max_words=4, field_name=_('Title'))
    details = CountedWordsField(min_words=6, field_name=_('Description'))

class ModerateTagForm(forms.Form):
    tag_id = forms.IntegerField()
    thread_id = forms.IntegerField(required=False)
    action = forms.CharField()

    def clean_action(self):
        action = self.cleaned_data['action']
        assert(action in ('accept', 'reject'))
        return action


class ShareQuestionForm(forms.Form):
    thread_id = forms.IntegerField()
    recipient_name = forms.CharField()


class BulkTagSubscriptionForm(forms.Form):
    date_added = forms.DateField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        from askbot.models import BulkTagSubscription, Tag, Group
        super(BulkTagSubscriptionForm, self).__init__(*args, **kwargs)
        self.fields['users'] = forms.ModelMultipleChoiceField(queryset=User.objects.all())
        self.fields['tags'] = TagNamesField(label=_("Tags"), help_text=' ')
        if askbot_settings.GROUPS_ENABLED:
            self.fields['groups'] = forms.ModelMultipleChoiceField(queryset=Group.objects.exclude_personal())


class GetDataForPostForm(forms.Form):
    post_id = forms.IntegerField()


class SetPostBodyForm(forms.Form):
    post_id = forms.IntegerField()
    body_text = forms.CharField()
    suppress_email = SuppressEmailField()


class SearchPostsForm(forms.Form):
    post_id = forms.IntegerField()
    q = forms.CharField()
    post_ord = forms.IntegerField()

    def clean_post_ord(self):
        post_ord = self.cleaned_data.get('post_ord')
        if post_ord and post_ord > 0:
            return post_ord
        return None

    def clean_post_id(self):
        post_id = self.cleaned_data.get('post_id')
        if post_id and post_id > 0:
            return post_id
        return None

    def clean(self):
        """cannot have both post_id and post_ord"""
        post_ord = self.cleaned_data.get('post_ord')
        post_id = self.cleaned_data.get('post_id')
        if post_ord and post_id:
            self.cleaned_data['post_ord'] = None
        return self.cleaned_data


class GetCommentDataForPostForm(GetDataForPostForm):
    avatar_size = forms.IntegerField()


class GetUserItemsForm(forms.Form):
    page_size = forms.IntegerField(required=False)
    page_number = forms.IntegerField(min_value=1)
    user_id = forms.IntegerField()


class UserForm(forms.Form):
    user_id = forms.IntegerField()


class UserDescriptionForm(forms.Form):
    user_id = forms.IntegerField()
    description = forms.CharField(required=False)


class NewCommentForm(forms.Form):
    comment = forms.CharField()
    post_id = forms.IntegerField()
    avatar_size = forms.IntegerField()

    def __init__(self, *args, **kwargs):
        super(NewCommentForm, self).__init__(*args, **kwargs)
        self.fields['comment'] = forms.CharField(
            max_length=askbot_settings.MAX_COMMENT_LENGTH)


class EditCommentForm(forms.Form):
    comment_id = forms.IntegerField()
    comment = forms.CharField()
    avatar_size = forms.IntegerField()
    suppress_email = SuppressEmailField()


class ProcessCommentForm(forms.Form):
    comment_id = forms.IntegerField()
    avatar_size = forms.IntegerField()


class ConvertCommentForm(forms.Form):
    comment_id = forms.IntegerField()


class ReorderBadgesForm(forms.Form):
    badge_id = forms.IntegerField()
    position = forms.IntegerField()


class AnalyticsUsersSegmentField(forms.CharField):
    """
    A field that accepts a string that is a valid users segment.
    Valid segments are:
    - 'all'
    - the default segment
    - group:<group_id>
    - user:<user_id>
    - named segments
    """
    def clean(self, users_segment):
        default_segment_slug = django_settings.ASKBOT_ANALYTICS_DEFAULT_SEGMENT['slug']
        named_segment_slugs = [segment['slug'] for segment in django_settings.ASKBOT_ANALYTICS_NAMED_SEGMENTS]
        allowed_segment_slugs = ['all-users', default_segment_slug] + named_segment_slugs
        if users_segment in allowed_segment_slugs:
            return users_segment

        if re.match(r'group:\d+', users_segment):
            return users_segment

        if re.match(r'user:\d+', users_segment):
            return users_segment

        raise forms.ValidationError('Invalid users segment')


class AnalyticsDatesField(forms.CharField):
    """
    A field that accepts a string that is a valid date range.
    Valid date ranges are:
    - last-7-days
    - last-30-days
    - this-month
    - last-month
    - last-3-months
    - this-year
    - last-year
    - all-time
    """
    def __init__(self, earliest_date, *args, **kwargs):
        super(AnalyticsDatesField, self).__init__(*args, **kwargs)
        self.earliest_date = earliest_date

    def clean(self, dates):
        if dates == 'last-7-days':
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=6)
            return start_date, end_date
        if dates == 'last-30-days':
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=29)
            return start_date, end_date
        if dates == 'this-month':
            end_date = timezone.now().date()
            start_date = end_date.replace(day=1)
            return start_date, end_date
        if dates == 'last-month':
            now = timezone.now().date()
            this_month_start = now.replace(day=1)
            last_month_end = this_month_start - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            return last_month_start, last_month_end
        if dates == 'last-3-months':
            now = timezone.now().date()
            this_month_start = now.replace(day=1)
            last_month_end = this_month_start - timedelta(days=1)
            three_months_ago_approx_end = last_month_end - timedelta(days=62)
            three_months_ago_start = three_months_ago_approx_end.replace(day=1)
            return three_months_ago_start, last_month_end
        if dates == 'last-6-months':
            now = timezone.now().date()
            this_month_start = now.replace(day=1)
            last_month_end = this_month_start - timedelta(days=1)
            six_months_ago_approx_end = last_month_end - timedelta(days=155)
            six_months_ago_start = six_months_ago_approx_end.replace(day=1)
            return six_months_ago_start, last_month_end
        if dates == 'this-year':
            now = timezone.now().date()
            this_year_start = now.replace(month=1, day=1)
            return this_year_start, now
        if dates == 'last-year':
            now = timezone.now().date()
            last_year_start = now.replace(year=now.year - 1, month=1, day=1)
            last_year_end = last_year_start.replace(year=now.year - 1, month=12, day=31)
            return last_year_start, last_year_end

        if dates == 'all-time':
            return self.earliest_date, timezone.now().date()

        raise forms.ValidationError('Invalid date range')


class AnalyticsActivityField(forms.CharField):
    """
    A field that accepts a string that is a valid activity segment.
    After validation, the field returns list of event types as defined in the Events model
    """
    ALL_ACTIVITY = 'all-activity'
    REGISTERED = 'registered'
    LOGGED_IN = 'logged-in'
    LOGGED_OUT = 'logged-out'
    QUESTION_VIEWED = 'question-viewed'
    ANSWER_VIEWED = 'answer-viewed'
    CONTENT_VOTED = 'content-voted'
    CONTENT_UPVOTED = 'content-upvoted'
    CONTENT_DOWNVOTED = 'content-downvoted'
    QUESTION_POSTED = 'question-posted'
    ANSWER_POSTED = 'answer-posted'
    QUESTION_COMMENTED = 'question-commented'
    ANSWER_COMMENTED = 'answer-commented'
    CONTENT_COMMENTED = 'content-commented'
    QUESTION_RETAGGED = 'question-retagged'
    ANY_CONTENT_POSTED = 'any-content-posted'

    def clean(self, activity_segment):
        from askbot.models.analytics import Event
        if activity_segment == self.ALL_ACTIVITY:
            return [Event.EVENT_TYPE_USER_REGISTERED,
                    Event.EVENT_TYPE_LOGGED_IN,
                    Event.EVENT_TYPE_LOGGED_OUT,
                    Event.EVENT_TYPE_QUESTION_VIEWED,
                    Event.EVENT_TYPE_ANSWER_VIEWED,
                    Event.EVENT_TYPE_UPVOTED,
                    Event.EVENT_TYPE_DOWNVOTED,
                    Event.EVENT_TYPE_VOTE_CANCELED,
                    Event.EVENT_TYPE_ASKED,
                    Event.EVENT_TYPE_ANSWERED,
                    Event.EVENT_TYPE_QUESTION_COMMENTED,
                    Event.EVENT_TYPE_ANSWER_COMMENTED,
                    Event.EVENT_TYPE_QUESTION_RETAGGED]
        if activity_segment == self.REGISTERED:
            return [Event.EVENT_TYPE_USER_REGISTERED]
        if activity_segment == self.LOGGED_IN:
            return [Event.EVENT_TYPE_LOGGED_IN]
        if activity_segment == self.LOGGED_OUT:
            return [Event.EVENT_TYPE_LOGGED_OUT]
        if activity_segment == self.QUESTION_VIEWED:
            return [Event.EVENT_TYPE_QUESTION_VIEWED]
        if activity_segment == self.ANSWER_VIEWED:
            return [Event.EVENT_TYPE_ANSWER_VIEWED]
        if activity_segment == self.CONTENT_VOTED:
            return [Event.EVENT_TYPE_UPVOTED, Event.EVENT_TYPE_DOWNVOTED, Event.EVENT_TYPE_VOTE_CANCELED]
        if activity_segment == self.CONTENT_UPVOTED:
            return [Event.EVENT_TYPE_UPVOTED]
        if activity_segment == self.CONTENT_DOWNVOTED:
            return [Event.EVENT_TYPE_DOWNVOTED]
        if activity_segment == self.QUESTION_POSTED:
            return [Event.EVENT_TYPE_ASKED]
        if activity_segment == self.ANSWER_POSTED:
            return [Event.EVENT_TYPE_ANSWERED]
        if activity_segment == self.QUESTION_COMMENTED:
            return [Event.EVENT_TYPE_QUESTION_COMMENTED]
        if activity_segment == self.CONTENT_COMMENTED:
            return [Event.EVENT_TYPE_ANSWER_COMMENTED, Event.EVENT_TYPE_QUESTION_COMMENTED]
        if activity_segment == self.ANSWER_COMMENTED:
            return [Event.EVENT_TYPE_ANSWER_COMMENTED]
        if activity_segment == self.QUESTION_RETAGGED:
            return [Event.EVENT_TYPE_QUESTION_RETAGGED]
        if activity_segment == self.ANY_CONTENT_POSTED:
            return [Event.EVENT_TYPE_ASKED, Event.EVENT_TYPE_ANSWERED, Event.EVENT_TYPE_QUESTION_COMMENTED, Event.EVENT_TYPE_ANSWER_COMMENTED]
        raise forms.ValidationError('Invalid activity segment')

    @classmethod
    def get_field_display(cls, activity_segment):
        if activity_segment == cls.ALL_ACTIVITY:
            return _('All Events')
        if activity_segment == cls.REGISTERED:
            return _('User Registered')
        if activity_segment == cls.LOGGED_IN:
            return _('User Logged In')
        if activity_segment == cls.LOGGED_OUT:
            return _('User Logged Out')
        if activity_segment == cls.QUESTION_VIEWED:
            return _('Question Viewed')
        if activity_segment == cls.ANSWER_VIEWED:
            return _('Answer Viewed')
        if activity_segment == cls.CONTENT_VOTED:
            return _('Content Voted')
        if activity_segment == cls.CONTENT_UPVOTED:
            return _('Content Upvoted')
        if activity_segment == cls.CONTENT_DOWNVOTED:
            return _('Content Downvoted')
        if activity_segment == cls.QUESTION_POSTED:
            return _('Question Posted')
        if activity_segment == cls.ANSWER_POSTED:
            return _('Answer Posted')
        if activity_segment == cls.QUESTION_COMMENTED:
            return _('Question Commented')
        if activity_segment == cls.ANSWER_COMMENTED:
            return _('Answer Commented')
        if activity_segment == cls.QUESTION_RETAGGED:
            return _('Question Retagged')
        if activity_segment == cls.ANY_CONTENT_POSTED:
            return _('Any Content Posted')
        raise ValueError('Invalid activity segment')


class AnalyticsContentField(forms.CharField):
    """
    A field that accepts a string that is a valid content segment.
    If the field is valid, just returns the value.
    Otherwise, raises a validation error.
    """
    def clean(self, content_segment):
        if re.match('thread:\d+', content_segment):
            return content_segment
        if re.match('post:\d+', content_segment):
            return content_segment
        if content_segment == 'all-content':
            return content_segment
        # it will be very hard to filter events by the post type,
        # because the post relation from the event is generic
        raise forms.ValidationError('Invalid content segment')

    @staticmethod
    def get_field_display(content_segment):
        if re.match('thread:\d+', content_segment):
            return _('Selected Thread')
        if re.match('post:\d+', content_segment):
            return _('Selected Post')
        if content_segment == 'all-content':
            return _('All Content')
        raise ValueError('Invalid content segment')


class AnalyticsUsersForm(forms.Form):
    """dates is a string that accepts a list of pre-approved values
    Such as last-7-days, this-year, etc., as defined in the analytics dates
    selector dropdown template.
    """
    users_segment = AnalyticsUsersSegmentField()
    query = forms.CharField(required=False)
    sort_by = forms.CharField(required=False)
    sort_order = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        earliest_possible_date = kwargs.pop('earliest_possible_date')
        super(AnalyticsUsersForm, self).__init__(*args, **kwargs)
        self.fields['dates'] = AnalyticsDatesField(earliest_date=earliest_possible_date)

    def clean_sort_order(self):
        sort_order = self.cleaned_data.get('sort_order', 'desc')
        if sort_order not in ('asc', 'desc'):
            return 'desc'
        return sort_order

    def clean_sort_by(self):
        sort_by = self.cleaned_data.get('sort_by', 'time_on_site')
        if sort_by  not in ('username',
                            'orgname',
                            'num_questions',
                            'num_answers',
                            'num_upvotes',
                            'num_downvotes',
                            'num_users_added',
                            'time_on_site'):
            return 'time_on_site'
        return sort_by

    def clean(self):
        sort_order = self.cleaned_data.get('sort_order', 'desc')
        sort_by = self.cleaned_data.get('sort_by', 'time_on_site')
        if sort_order == 'desc':
            order_by = '-' + sort_by
        else:
            order_by = sort_by
        self.cleaned_data['order_by'] = order_by
        return self.cleaned_data


class AnalyticsActivityForm(forms.Form):
    activity_segment = AnalyticsActivityField()
    content_segment = AnalyticsContentField()
    users_segment = AnalyticsUsersSegmentField()

    def __init__(self, *args, **kwargs):
        earliest_possible_date = kwargs.pop('earliest_possible_date')
        super(AnalyticsActivityForm, self).__init__(*args, **kwargs)
        self.fields['dates'] = AnalyticsDatesField(earliest_date=earliest_possible_date)

class PaginationForm(forms.Form):
    page = PageField()