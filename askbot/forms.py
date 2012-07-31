"""Forms, custom form fields and related utility functions
used in AskBot"""
import re
from django import forms
from askbot import const
from django.forms.util import ErrorList
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ungettext_lazy, string_concat
from django.utils.text import get_text_list
from django.contrib.auth.models import User
from django_countries import countries
from askbot.utils.forms import NextUrlField, UserNameField
from askbot.mail import extract_first_email_address
from recaptcha_works.fields import RecaptchaField
from askbot.conf import settings as askbot_settings
import logging


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
        errors = form.errors.values()
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


def clean_marked_tagnames(tagnames):
    """return two strings - one containing tagnames
    that are straight names of tags, and the second one
    containing names of wildcard tags,
    wildcard tags are those that have an asterisk at the end
    the function does not verify that the tag names are valid
    """
    if askbot_settings.USE_WILDCARD_TAGS is False:
        return tagnames, list()

    pure_tags = list()
    wildcards = list()
    for tagname in tagnames:
        if tagname == '':
            continue
        if tagname.endswith('*'):
            if tagname.count('*') > 1:
                continue
            else:
                wildcards.append(tagname)
        else:
            pure_tags.append(tagname)

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
        askbot_settings.TAGS_ARE_REQUIRED
        and len(models.tag.get_mandatory_tags()) > 0
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



COUNTRY_CHOICES = (('unknown', _('select country')),) + countries.COUNTRIES


class CountryField(forms.ChoiceField):
    """this is better placed into the django_coutries app"""

    def __init__(self, *args, **kwargs):
        """sets label and the country choices
        """
        kwargs['choices'] = kwargs.pop('choices', COUNTRY_CHOICES)
        kwargs['label'] = kwargs.pop('label', _('Country'))
        super(CountryField, self).__init__(*args, **kwargs)

    def clean(self, value):
        """Handles case of 'unknown' country selection
        """
        if self.required:
            if value == 'unknown':
                raise forms.ValidationError(_('Country field is required'))
        if value == 'unknown':
            return None
        return value


class CountedWordsField(forms.CharField):
    """a field where a number of words is expected
    to be in a certain range"""

    def __init__(
        self, min_words=0, max_words=9999, field_name=None,
        *args, **kwargs
    ):
        self.min_words = min_words
        self.max_words = max_words
        self.field_name = field_name
        super(CountedWordsField, self).__init__(*args, **kwargs)

    def clean(self, value):
        #todo: this field must be adapted to work with Chinese, etc.
        #for that we'll have to count characters instead of words
        if value is None:
            value = ''

        value = value.strip()

        word_count = len(value.split())
        if word_count < self.min_words:
            msg = ungettext_lazy(
                'must be > %d word',
                'must be > %d words',
                self.min_words - 1
            ) % (self.min_words - 1)
            #todo - space is not used in Chinese
            raise forms.ValidationError(
                string_concat(self.field_name, ' ', msg)
            )

        if word_count > self.max_words:
            msg = ungettext_lazy(
                'must be < %d word',
                'must be < %d words',
                self.max_words + 1
            ) % (self.max_words + 1)
            raise forms.ValidationError(
                string_concat(self.field_name, ' ', msg)
            )
        return value


class DomainNameField(forms.CharField):
    """Field for Internet Domain Names
    todo: maybe there is a standard field for this?
    """
    def clean(self, value):
        #find a better regex, taking into account tlds
        domain_re = re.compile(r'[a-zA-Z\d]+(\.[a-zA-Z\d]+)+')
        if domain_re.match(value):
            return value
        else:
            raise forms.ValidationError(
                '%s is not a valid domain name' % value
            )


class TitleField(forms.CharField):
    """Fild receiving question title"""
    def __init__(self, *args, **kwargs):
        super(TitleField, self).__init__(*args, **kwargs)
        self.required = True
        self.widget = forms.TextInput(
                            attrs={'size': 70, 'autocomplete': 'off'}
                        )
        self.max_length = 255
        self.label = _('title')
        self.help_text = _(
            'please enter a descriptive title for your question'
        )
        self.initial = ''

    def clean(self, value):
        """cleans the field for minimum and maximum length
        also is supposed to work for unicode non-ascii characters"""
        if value is None:
            value = ''
        if len(value) < askbot_settings.MIN_TITLE_LENGTH:
            msg = ungettext_lazy(
                'title must be > %d character',
                'title must be > %d characters',
                askbot_settings.MIN_TITLE_LENGTH
            ) % askbot_settings.MIN_TITLE_LENGTH
            raise forms.ValidationError(msg)
        encoded_value = value.encode('utf-8')
        if len(value) == len(encoded_value):
            if len(value) > self.max_length:
                raise forms.ValidationError(
                    _(
                        'The title is too long, maximum allowed size is '
                        '%d characters'
                    ) % self.max_length
                )
        elif len(encoded_value) > self.max_length:
            raise forms.ValidationError(
                _(
                    'The title is too long, maximum allowed size is '
                    '%d bytes'
                ) % self.max_length
            )

        return value.strip()  # TODO: test me


class EditorField(forms.CharField):
    """EditorField is subclassed by the
    :class:`QuestionEditorField` and :class:`AnswerEditorField`
    """
    length_error_template_singular = 'post content must be > %d character',
    length_error_template_plural = 'post content must be > %d characters',
    min_length = 10  # sentinel default value

    def __init__(self, *args, **kwargs):
        super(EditorField, self).__init__(*args, **kwargs)
        self.required = True
        self.widget = forms.Textarea(attrs={'id': 'editor'})
        self.label = _('content')
        self.help_text = u''
        self.initial = ''

    def clean(self, value):
        if value is None:
            value = ''
        if len(value) < self.min_length:
            msg = ungettext_lazy(
                self.length_error_template_singular,
                self.length_error_template_plural,
                self.min_length
            ) % self.min_length
            raise forms.ValidationError(msg)
        return value


class QuestionEditorField(EditorField):
    """Editor field for the questions"""

    def __init__(self, *args, **kwargs):
        super(QuestionEditorField, self).__init__(*args, **kwargs)
        self.length_error_template_singular = \
            'question body must be > %d character'
        self.length_error_template_plural = \
            'question body must be > %d characters'
        self.min_length = askbot_settings.MIN_QUESTION_BODY_LENGTH


class AnswerEditorField(EditorField):
    """Editor field for answers"""

    def __init__(self, *args, **kwargs):
        super(AnswerEditorField, self).__init__(*args, **kwargs)
        self.length_error_template_singular = 'answer must be > %d character'
        self.length_error_template_plural = 'answer must be > %d characters'
        self.min_length = askbot_settings.MIN_ANSWER_BODY_LENGTH


class TagNamesField(forms.CharField):
    """field that receives AskBot tag names"""

    def __init__(self, *args, **kwargs):
        super(TagNamesField, self).__init__(*args, **kwargs)
        self.required = askbot_settings.TAGS_ARE_REQUIRED
        self.widget = forms.TextInput(
            attrs={'size': 50, 'autocomplete': 'off'}
        )
        self.max_length = 255
        self.label = _('tags')
        self.help_text = ungettext_lazy(
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
        data = value.strip()
        if len(data) < 1:
            if askbot_settings.TAGS_ARE_REQUIRED:
                raise forms.ValidationError(_('tags are required'))
            else:
                #don't test for required characters when tags is ''
                return ''
        split_re = re.compile(const.TAG_SPLIT_REGEX)
        tag_strings = split_re.split(data)
        entered_tags = []
        tag_count = len(tag_strings)
        if tag_count > askbot_settings.MAX_TAGS_PER_POST:
            max_tags = askbot_settings.MAX_TAGS_PER_POST
            msg = ungettext_lazy(
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

        for tag in tag_strings:
            tag_length = len(tag)
            if tag_length > askbot_settings.MAX_TAG_LENGTH:
                #singular form is odd in english, but
                #required for pluralization
                #in other languages, odd but added for completeness
                msg = ungettext_lazy(
                    'each tag must be shorter than %(max_chars)d character',
                    'each tag must be shorter than %(max_chars)d characters',
                    tag_length
                ) % {'max_chars': tag_length}
                raise forms.ValidationError(msg)

            #todo - this needs to come from settings
            tagname_re = re.compile(const.TAG_REGEX, re.UNICODE)
            if not tagname_re.search(tag):
                raise forms.ValidationError(_(
                    'In tags, please use letters, '
                    'numbers and characters "-+.#"'
                ))
            #only keep unique tags
            if tag not in entered_tags:
                entered_tags.append(tag)

        #normalize character case of tags
        cleaned_entered_tags = list()
        if askbot_settings.FORCE_LOWERCASE_TAGS:
            #a simpler way to handle tags - just lowercase thew all
            for name in entered_tags:
                lowercased_name = name.lower()
                if lowercased_name not in cleaned_entered_tags:
                    cleaned_entered_tags.append(lowercased_name)
        else:
            #make names of tags in the input to agree with the database
            for entered_tag in entered_tags:
                try:
                    #looks like we have to load tags one-by one
                    #because we need tag name cases to be the same
                    #as those stored in the database
                    stored_tag = models.Tag.objects.get(
                                            name__iexact=entered_tag
                                        )
                    if stored_tag.name not in cleaned_entered_tags:
                        cleaned_entered_tags.append(stored_tag.name)
                except models.Tag.DoesNotExist:
                    cleaned_entered_tags.append(entered_tag)

        return u' '.join(cleaned_entered_tags)


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
        self.help_text = _(
            'if you choose community wiki option, the question '
            'and answer do not generate points and name of '
            'author will not be shown'
        )

    def clean(self, value):
        return value and askbot_settings.WIKI_ON


class EmailNotifyField(forms.BooleanField):
    """Rendered as checkbox which turns on
    email notifications on the post"""
    def __init__(self, *args, **kwargs):
        super(EmailNotifyField, self).__init__(*args, **kwargs)
        self.required = False
        self.widget.attrs['class'] = 'nomargin'


class SummaryField(forms.CharField):

    def __init__(self, *args, **kwargs):
        super(SummaryField, self).__init__(*args, **kwargs)
        self.required = False
        self.widget = forms.TextInput(
            attrs={'size': 50, 'autocomplete': 'off'}
        )
        self.max_length = 300
        self.label = _('update summary:')
        self.help_text = _(
            'enter a brief summary of your revision (e.g. '
            'fixed spelling, grammar, improved style, this '
            'field is optional)'
        )


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
    page = forms.IntegerField(required=False)
    sort = forms.CharField(required=False)

    def __init__(self, data, default_sort_method):
        super(ShowQuestionForm, self).__init__(data)
        self.default_sort_method = default_sort_method

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
            #since the form is always valid, clear the errors
            logging.error(unicode(self._errors))
            self._errors = {}

        in_data = self.get_pruned_data()
        out_data = dict()
        if ('answer' in in_data) ^ ('comment' in in_data):
            out_data['show_page'] = None
            out_data['answer_sort_method'] = 'votes'
            out_data['show_comment'] = in_data.get('comment', None)
            out_data['show_answer'] = in_data.get('answer', None)
        else:
            out_data['show_page'] = in_data.get('page', 1)
            out_data['answer_sort_method'] = in_data.get(
                                                    'sort',
                                                    self.default_sort_method
                                                )
            out_data['show_comment'] = None
            out_data['show_answer'] = None
        self.cleaned_data = out_data
        return out_data


class ChangeUserReputationForm(forms.Form):
    """Form that allows moderators and site administrators
    to adjust reputation of users.

    this form internally verifies that user who claims to
    be a moderator acually is
    """

    user_reputation_delta = forms.IntegerField(
                            min_value=1,
                            label=_(
                                'Enter number of points to add or subtract'
                            )
                        )
    comment = forms.CharField(max_length=128)

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
ADMINISTRATOR_STATUS_CHOICES = (('d', _('administrator')),
                               ('m', _('moderator')), ) \
                               + MODERATOR_STATUS_CHOICES


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

    def __init__(self, *arg, **kwarg):

        moderator = kwarg.pop('moderator')
        subject = kwarg.pop('subject')

        super(ChangeUserStatusForm, self).__init__(*arg, **kwarg)

        #select user_status_choices depending on status of the moderator
        if moderator.is_administrator():
            user_status_choices = ADMINISTRATOR_STATUS_CHOICES
        elif moderator.is_moderator():
            user_status_choices = MODERATOR_STATUS_CHOICES
            if subject.is_moderator() and subject != moderator:
                raise ValueError('moderator cannot moderate another moderator')
        else:
            raise ValueError('moderator or admin expected from "moderator"')

        #remove current status of the "subject" user from choices
        user_status_choices = filter_choices(
                                        remove_choices=[subject.status, ],
                                        from_choices=user_status_choices
                                    )

        #add prompt option
        user_status_choices = (('select', _('which one?')), ) \
                                + user_status_choices

        self.fields['user_status'].choices = user_status_choices

        #set prompt option as default
        self.fields['user_status'].default = 'select'
        self.moderator = moderator
        self.subject = subject

    def clean(self):
        #if moderator is looking at own profile - do not
        #let change status
        if 'user_status' in self.cleaned_data:

            user_status = self.cleaned_data['user_status']

            #does not make sense to change own user status
            #if necessary, this can be done from the Django admin interface
            if self.moderator == self.subject:
                del self.cleaned_data['user_status']
                raise forms.ValidationError(_('Cannot change own status'))

            #do not let moderators turn other users into moderators
            if self.moderator.is_moderator() and user_status == 'moderator':
                del self.cleanded_data['user_status']
                raise forms.ValidationError(
                                _('Cannot turn other user to moderator')
                            )

            #do not allow moderator to change status of other moderators
            if self.moderator.is_moderator() and self.subject.is_moderator():
                del self.cleaned_data['user_status']
                raise forms.ValidationError(
                                _('Cannot change status of another moderator')
                            )

            #do not allow moderator to change to admin
            if self.moderator.is_moderator() and user_status == 'd':
                raise forms.ValidationError(
                                _("Cannot change status to admin")
                                )

            if user_status == 'select':
                del self.cleaned_data['user_status']
                msg = _(
                        'If you wish to change %(username)s\'s status, '
                        'please make a meaningful selection.'
                    ) % {'username': self.subject.username}
                raise forms.ValidationError(msg)

        return self.cleaned_data


class SendMessageForm(forms.Form):
    subject_line = forms.CharField(
                        label=_('Subject line'),
                        max_length=64,
                        widget=forms.TextInput(attrs={'size': 64}, )
                    )
    body_text = forms.CharField(
                            label=_('Message text'),
                            max_length=1600,
                            widget=forms.Textarea(attrs={'cols': 64})
                        )


class NotARobotForm(forms.Form):
    recaptcha = RecaptchaField(
                    private_key=askbot_settings.RECAPTCHA_SECRET,
                    public_key=askbot_settings.RECAPTCHA_KEY
                )


class FeedbackForm(forms.Form):
    name = forms.CharField(label=_('Your name (optional):'), required=False)
    email = forms.EmailField(label=_('Email:'), required=False)
    message = forms.CharField(
        label=_('Your message:'),
        max_length=800,
        widget=forms.Textarea(attrs={'cols': 60})
    )
    no_email = forms.BooleanField(
        label=_("I don't want to give my email or receive a response:"),
        required=False
    )
    next = NextUrlField()

    def __init__(self, is_auth=False, *args, **kwargs):
        super(FeedbackForm, self).__init__(*args, **kwargs)
        self.is_auth = is_auth
        if not is_auth:
            if askbot_settings.USE_RECAPTCHA:
                self._add_recaptcha_field()

    def _add_recaptcha_field(self):
        self.fields['recaptcha'] = RecaptchaField(
                            private_key=askbot_settings.RECAPTCHA_SECRET,
                            public_key=askbot_settings.RECAPTCHA_KEY
                        )

    def clean(self):
        super(FeedbackForm, self).clean()
        if not self.is_auth:
            if not self.cleaned_data['no_email'] \
                and not self.cleaned_data['email']:
                msg = _('Please mark "I dont want to give my mail" field.')
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


class PostAsSomeoneForm(forms.Form):
    post_author_username = forms.CharField(
        initial=_('User name:'),
        help_text=_(
            'Enter name to post on behalf of someone else. '
            'Can create new accounts.'
        ),
        required=False,
        widget=forms.TextInput(attrs={'class': 'tipped-input'})
    )
    post_author_email = forms.CharField(
        initial=_('Email address:'),
        required=False,
        widget=forms.TextInput(attrs={'class': 'tipped-input'})
    )

    def get_post_user(self, user):
        """returns user on whose behalf the post or a revision
        is being made
        """
        username = self.cleaned_data['post_author_username']
        email= self.cleaned_data['post_author_email']
        if user.is_administrator() and username and email:
            post_user = user.get_or_create_fake_user(username, email)
        else:
            post_user = user
        return post_user

    def clean_post_author_username(self):
        """if value is the same as initial, it is reset to
        empty string
        todo: maybe better to have field where initial value is invalid,
        then we would not have to have two almost identical clean functions?
        """
        username = self.cleaned_data.get('post_author_username', '')
        initial_username = unicode(self.fields['post_author_username'].initial)
        if username == initial_username:
            self.cleaned_data['post_author_username'] = ''
        return self.cleaned_data['post_author_username']

    def clean_post_author_email(self):
        """if value is the same as initial, it is reset to
        empty string"""
        email = self.cleaned_data.get('post_author_email', '')
        initial_email = unicode(self.fields['post_author_email'].initial)
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
            username_errors = self._errors.get(
                                    'post_author_username',
                                    ErrorList()
                                )
            username_errors.append(_('User name is required with the email'))
            self._errors['post_author_username'] = username_errors
            raise forms.ValidationError('missing user name')
        elif email == '' and username:
            email_errors = self._errors.get('post_author_email', ErrorList())
            email_errors.append(_('Email is required if user name is added'))
            self._errors['post_author_email'] = email_errors
            raise forms.ValidationError('missing email')

        return self.cleaned_data


class AskForm(PostAsSomeoneForm, FormWithHideableFields):
    """the form used to askbot questions
    field ask_anonymously is shown to the user if the
    if ALLOW_ASK_ANONYMOUSLY live setting is True
    however, for simplicity, the value will always be present
    in the cleaned data, and will evaluate to False if the
    settings forbids anonymous asking
    """
    title = TitleField()
    text = QuestionEditorField()
    tags = TagNamesField()
    wiki = WikiField()
    ask_anonymously = forms.BooleanField(
        label=_('ask anonymously'),
        help_text=_(
            'Check if you do not want to reveal your name '
            'when asking this question'
        ),
        required=False,
    )
    openid = forms.CharField(
        required=False, max_length=255,
        widget=forms.TextInput(attrs={'size': 40, 'class': 'openid-input'})
    )

    def __init__(self, *args, **kwargs):
        super(AskForm, self).__init__(*args, **kwargs)
        #hide ask_anonymously field
        if askbot_settings.ALLOW_ASK_ANONYMOUSLY is False:
            self.hide_field('ask_anonymously')

    def clean_ask_anonymously(self):
        """returns false if anonymous asking is not allowed
        """
        if askbot_settings.ALLOW_ASK_ANONYMOUSLY is False:
            self.cleaned_data['ask_anonymously'] = False
        return self.cleaned_data['ask_anonymously']


ASK_BY_EMAIL_SUBJECT_HELP = _(
    'Subject line is expected in the format: '
    '[tag1, tag2, tag3,...] question title'
)


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
        max_length=255,
        error_messages={
            'required': ASK_BY_EMAIL_SUBJECT_HELP
        }
    )
    body_text = QuestionEditorField()

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
            #make raw tags comma-separated
            if match.group(1) is None:  # no tags
                self.cleaned_data['tagnames'] = ''
            else:
                tagnames = match.group(1).replace(';', ',')

                #pre-process tags
                tag_list = [tag.strip() for tag in tagnames.split(',')]
                tag_list = [re.sub(r'\s+', ' ', tag) for tag in tag_list]

                if askbot_settings.REPLACE_SPACE_WITH_DASH_IN_EMAILED_TAGS:
                    tag_list = [tag.replace(' ', '-') for tag in tag_list]
                #todo: use tag separator char here
                tagnames = ' '.join(tag_list)

                #clean tags - may raise ValidationError
                self.cleaned_data['tagnames'] = TagNamesField().clean(tagnames)

            #clean title - may raise ValidationError
            title = match.group(2).strip()
            self.cleaned_data['title'] = TitleField().clean(title)
        else:
            raise forms.ValidationError(ASK_BY_EMAIL_SUBJECT_HELP)
        return self.cleaned_data['subject']


class AnswerForm(PostAsSomeoneForm):
    text = AnswerEditorField()
    wiki = WikiField()
    openid = forms.CharField(
        required=False, max_length=255,
        widget=forms.TextInput(attrs={'size': 40, 'class': 'openid-input'})
    )
    email_notify = EmailNotifyField(initial=False)

    def __init__(self, *args, **kwargs):
        super(AnswerForm, self).__init__(*args, **kwargs)
        self.fields['email_notify'].widget.attrs['id'] = \
                                    'question-subscribe-updates'


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
                    'either "true" or "false" strings expected'
                )
        self.cleaned_data['cancel_vote'] = result
        return self.cleaned_data['cancel_vote']


class CloseForm(forms.Form):
    reason = forms.ChoiceField(choices=const.CLOSE_REASONS)


class RetagQuestionForm(forms.Form):
    tags = TagNamesField()

    def __init__(self, question, *args, **kwargs):
        """initialize the default values"""
        super(RetagQuestionForm, self).__init__(*args, **kwargs)
        self.fields['tags'].initial = question.thread.tagnames


class RevisionForm(forms.Form):
    """
    Lists revisions of a Question or Answer
    """
    revision = forms.ChoiceField(
                    widget=forms.Select(
                        attrs={'style': 'width:520px'}
                    )
                )

    def __init__(self, post, latest_revision, *args, **kwargs):
        super(RevisionForm, self).__init__(*args, **kwargs)
        revisions = post.revisions.values_list(
            'revision', 'author__username', 'revised_at', 'summary'
        )
        date_format = '%c'
        rev_choices = list()
        for r in revisions:
            rev_details = u'%s - %s (%s) %s' % (
                r[0], r[1], r[2].strftime(date_format), r[3]
            )
            rev_choices.append((r[0], rev_details))

        self.fields['revision'].choices = rev_choices
        self.fields['revision'].initial = latest_revision.revision


class EditQuestionForm(PostAsSomeoneForm, FormWithHideableFields):
    title = TitleField()
    text = QuestionEditorField()
    tags = TagNamesField()
    summary = SummaryField()
    wiki = WikiField()
    reveal_identity = forms.BooleanField(
        help_text=_(
            'You have asked this question anonymously, '
            'if you decide to reveal your identity, please check '
            'this box.'
        ),
        label=_('reveal identity'),
        required=False,
    )

    #todo: this is odd that this form takes question as an argument
    def __init__(self, *args, **kwargs):
        """populate EditQuestionForm with initial data"""
        self.question = kwargs.pop('question')
        self.user = kwargs.pop('user')
        revision = kwargs.pop('revision')
        super(EditQuestionForm, self).__init__(*args, **kwargs)
        self.fields['title'].initial = revision.title
        self.fields['text'].initial = revision.text
        self.fields['tags'].initial = revision.tagnames
        self.fields['wiki'].initial = self.question.wiki
        #hide the reveal identity field
        if not self.can_stay_anonymous():
            self.hide_field('reveal_identity')

    def can_stay_anonymous(self):
        """determines if the user cat keep editing the question
        anonymously"""
        return (askbot_settings.ALLOW_ASK_ANONYMOUSLY
            and self.question.is_anonymous
            and self.user.is_owner_of(self.question)
        )

    def clean_reveal_identity(self):
        """cleans the reveal_identity field
        which determines whether previous anonymous
        edits must be rewritten as not anonymous
        this does not necessarily mean that the edit will be anonymous

        only does real work when question is anonymous
        based on the following truth table:

        is_anon  can  owner  checked  cleaned data
        -        *     *        *        False (ignore choice in checkbox)
        +        +     +        +        True
        +        +     +        -        False
        +        +     -        +        Raise(Not owner)
        +        +     -        -        False
        +        -     +        +        True (setting "can" changed, say yes)
        +        -     +        -        False, warn (but prev edits stay anon)
        +        -     -        +        Raise(Not owner)
        +        -     -        -        False
        """
        value = self.cleaned_data['reveal_identity']
        if self.question.is_anonymous:
            if value is True:
                if self.user.is_owner_of(self.question):
                    #regardless of the ALLOW_ASK_ANONYMOUSLY
                    return True
                else:
                    self.show_field('reveal_identity')
                    del self.cleaned_data['reveal_identity']
                    raise forms.ValidationError(
                                _(
                                    'Sorry, only owner of the anonymous '
                                    'question can reveal his or her '
                                    'identity, please uncheck the '
                                    'box'
                                 )
                             )
            else:
                can_ask_anon = askbot_settings.ALLOW_ASK_ANONYMOUSLY
                is_owner = self.user.is_owner_of(self.question)
                if can_ask_anon is False and is_owner:
                    self.show_field('reveal_identity')
                    raise forms.ValidationError(
                        _(
                            'Sorry, apparently rules have just changed - '
                            'it is no longer possible to ask anonymously. '
                            'Please either check the "reveal identity" box '
                            'or reload this page and try editing the question '
                            'again.'
                        )
                    )
                return False
        else:
            #takes care of 8 possibilities - first row of the table
            return False

    def clean(self):
        """Purpose of this function is to determine whether
        it is ok to apply edit anonymously in the synthetic
        field edit_anonymously. It relies on correct cleaning
        if the "reveal_identity" field
        """
        super(EditQuestionForm, self).clean()
        reveal_identity = self.cleaned_data.get('reveal_identity', False)
        stay_anonymous = False
        if reveal_identity is False and self.can_stay_anonymous():
            stay_anonymous = True
        self.cleaned_data['stay_anonymous'] = stay_anonymous
        return self.cleaned_data


class EditAnswerForm(PostAsSomeoneForm):
    text = AnswerEditorField()
    summary = SummaryField()
    wiki = WikiField()

    def __init__(self, answer, revision, *args, **kwargs):
        super(EditAnswerForm, self).__init__(*args, **kwargs)
        self.fields['text'].initial = revision.text
        self.fields['wiki'].initial = answer.wiki


class EditTagWikiForm(forms.Form):
    text = forms.CharField(required=False)
    tag_id = forms.IntegerField()


class EditUserForm(forms.Form):
    email = forms.EmailField(
                         label=u'Email',
                         required=False,
                         max_length=255,
                         widget=forms.TextInput(attrs={'size' : 35})
                    )

    realname = forms.CharField(
                        label=_('Real name'),
                        required=False,
                        max_length=255,
                        widget=forms.TextInput(attrs={'size': 35})
                    )

    website = forms.URLField(
                        label=_('Website'),
                        required=False,
                        max_length=255,
                        widget=forms.TextInput(attrs={'size': 35})
                    )

    city = forms.CharField(
                        label=_('City'),
                        required=False,
                        max_length=255,
                        widget=forms.TextInput(attrs={'size': 35})
                    )

    country = CountryField(required=False)

    show_country = forms.BooleanField(
                        label=_('Show country'),
                        required=False
                    )

    show_marked_tags = forms.BooleanField(
                        label=_('Show tag choices'),
                        required=False
                    )

    birthday = forms.DateField(
                        label=_('Date of birth'),
                        help_text=_(
                            'will not be shown, used to calculate '
                            'age, format: YYYY-MM-DD'
                        ),
                        required=False,
                        widget=forms.TextInput(attrs={'size': 35})
                    )

    about = forms.CharField(
                        label=_('Profile'),
                        required=False,
                        widget=forms.Textarea(attrs={'cols': 60})
                    )

    def __init__(self, user, *args, **kwargs):
        super(EditUserForm, self).__init__(*args, **kwargs)
        logging.debug('initializing the form')
        if askbot_settings.EDITABLE_SCREEN_NAME:
            self.fields['username'] = UserNameField(label=_('Screen name'))
            self.fields['username'].initial = user.username
            self.fields['username'].user_instance = user
        if askbot_settings.EDITABLE_EMAIL:
	    self.fields['email'].required = True;
            self.fields['email'].initial = user.email
        self.fields['realname'].initial = user.real_name
        self.fields['website'].initial = user.website
        self.fields['city'].initial = user.location
        if user.country is None:
            country = 'unknown'
        else:
            country = user.country
        self.fields['country'].initial = country
        self.fields['show_country'].initial = user.show_country
        self.fields['show_marked_tags'].initial = user.show_marked_tags

        if user.date_of_birth is not None:
            self.fields['birthday'].initial = user.date_of_birth

        self.fields['about'].initial = user.about
        self.user = user

    def clean_email(self):
        """For security reason one unique email in database"""
        if self.user.email != self.cleaned_data['email']:
            #todo dry it, there is a similar thing in openidauth
            if askbot_settings.EMAIL_UNIQUE is True:
                if 'email' in self.cleaned_data:
                    try:
                        User.objects.get(email=self.cleaned_data['email'])
                    except User.DoesNotExist:
                        return self.cleaned_data['email']
                    except User.MultipleObjectsReturned:
                        raise forms.ValidationError(_(
                            'this email has already been registered, '
                            'please use another one')
                        )
                    raise forms.ValidationError(_(
                        'this email has already been registered, '
                        'please use another one')
                    )
        return self.cleaned_data['email']


class TagFilterSelectionForm(forms.ModelForm):
    email_tag_filter_strategy = forms.ChoiceField(
        choices=const.TAG_DISPLAY_FILTER_STRATEGY_CHOICES,
        initial=const.EXCLUDE_IGNORED,
        label=_('Choose email tag filter'),
        widget=forms.RadioSelect
    )

    class Meta:
        model = User
        fields = ('email_tag_filter_strategy',)

    def save(self):
        before = self.instance.email_tag_filter_strategy
        super(TagFilterSelectionForm, self).save()
        after = self.instance.email_tag_filter_strategy
        if before != after:
            return True
        return False


class EmailFeedSettingField(forms.ChoiceField):
    def __init__(self, *arg, **kwarg):
        kwarg['choices'] = const.NOTIFICATION_DELIVERY_SCHEDULE_CHOICES
        kwarg['widget'] = forms.RadioSelect
        super(EmailFeedSettingField, self).__init__(*arg, **kwarg)


class EditUserEmailFeedsForm(forms.Form):
    FORM_TO_MODEL_MAP = {
        'all_questions': 'q_all',
        'asked_by_me': 'q_ask',
        'answered_by_me': 'q_ans',
        'individually_selected': 'q_sel',
        'mentions_and_comments': 'm_and_c',
    }
    NO_EMAIL_INITIAL = {
        'all_questions': 'n',
        'asked_by_me': 'n',
        'answered_by_me': 'n',
        'individually_selected': 'n',
        'mentions_and_comments': 'n',
    }
    INSTANT_EMAIL_INITIAL = {
        'all_questions': 'i',
        'asked_by_me': 'i',
        'answered_by_me': 'i',
        'individually_selected': 'i',
        'mentions_and_comments': 'i',
    }

    asked_by_me = EmailFeedSettingField(
                            label=_('Asked by me')
                        )
    answered_by_me = EmailFeedSettingField(
                            label=_('Answered by me')
                        )
    individually_selected = EmailFeedSettingField(
                            label=_('Individually selected')
                        )
    all_questions = EmailFeedSettingField(
                            label=_('Entire forum (tag filtered)'),
                        )

    mentions_and_comments = EmailFeedSettingField(
                            label=_('Comments and posts mentioning me'),
                        )

    def set_initial_values(self, user=None):
        from askbot import models
        KEY_MAP = dict([(v, k) for k, v in self.FORM_TO_MODEL_MAP.iteritems()])
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
        todo: clean up use of this function
        """
        if self.is_bound:
            self.cleaned_data = self.NO_EMAIL_INITIAL
        self.initial = self.NO_EMAIL_INITIAL
        return self

    def get_db_model_subscription_type_names(self):
        """todo: refactor this - too hacky
        should probably use model form instead

        returns list of values acceptable in
        ``attr::models.user.EmailFeedSetting.feed_type``
        """
        return self.FORM_TO_MODEL_MAP.values()

    def set_frequency(self, frequency='n'):
        data = {
            'all_questions': frequency,
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
        for form_field, feed_type in self.FORM_TO_MODEL_MAP.items():
            s, created = models.EmailFeedSetting.objects.get_or_create(
                                                    subscriber=user,
                                                    feed_type=feed_type
                                                )
            if save_unbound:
                #just save initial values instead
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
            (
                'n',
                _('no %(sitename)s email please, thanks')
                    % {'sitename': askbot_settings.APP_SHORT_NAME}
            )
        )
        super(SubscribeForEmailUpdatesField, self).__init__(**kwargs)


class SimpleEmailSubscribeForm(forms.Form):
    subscribe = SubscribeForEmailUpdatesField()

    def save(self, user=None):
        EFF = EditUserEmailFeedsForm
        #here we have kind of an anomaly - the value 'y' is redundant
        #with the frequency variable - needs to be fixed
        if self.is_bound and self.cleaned_data['subscribe'] == 'y':
            email_settings_form = EFF()
            email_settings_form.set_initial_values(user)
            logging.debug('%s wants to subscribe' % user.username)
        else:
            email_settings_form = EFF(initial=EFF.NO_EMAIL_INITIAL)
        email_settings_form.save(user, save_unbound=True)


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
    title = CountedWordsField(
        min_words=1, max_words=4, field_name=_('Title')
    )
    details = CountedWordsField(
        min_words=6, field_name=_('Description')
    )
