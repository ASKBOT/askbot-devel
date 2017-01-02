from django import forms as django_forms
from django.contrib.auth.models import AnonymousUser
from askbot.tests.utils import AskbotTestCase
from askbot.tests.utils import with_settings
from askbot.conf import settings as askbot_settings
from askbot import forms
from askbot.utils import forms as util_forms
from askbot import models

# Test should fail if the second item is None
EMAIL_CASES = (
    ('user@example.com', 'user@example.com'),
    ('Name Name <name@example.com>', 'name@example.com'),
    ('"Name Name [example.com]" <name@example.com>', 'name@example.com'),
    (
        'someone <reply+m-4823355-3ae97f4698708d0be6bb087d6d4ce1e5e33ac131@reply.example.com>',
        'reply+m-4823355-3ae97f4698708d0be6bb087d6d4ce1e5e33ac131@reply.example.com'
    ),
    (
        'freddy krueger <someone@example.edu> (by way of somebody else)',
        'someone@example.edu'
    ),
    (
        'Google Anniversary Promotion =?iso-8859-1?Q?=A9_2011?= <someone@example.br>',
        'someone@example.br'
    ),
    ('=?koi8-r?B?5sHExcXXwSDvzNjHwQ==?= <someone@example.ru>', 'someone@example.ru'),
    ('root@example.org (Cron Daemon)', 'root@example.org'),
    ('<summary@example.com>', 'summary@example.com'),
    ('some text without an email adderess', None)
)

# Test fails if second item is None
SUBJECT_LINE_CASES = (
    (
        ' [ tag1;long  tag, another] question title',
        ('tag1 long-tag another', 'question title')
    ),
    ('[] question title', None),
    ('question title', None),
    ('   [question title', None),
    ('] question title', None),
)


class AskByEmailFormTests(AskbotTestCase):
    """Tests :class:`~askbot.forms.AskByEmailForm`
    form"""
    def setUp(self):
        # Begin data set that must pass
        self.data = {
            'sender': 'someone@example.com',
            'subject': '[tag-one] where is titanic?',
            'body_text': 'where is titanic?'
        }

    def test_subject_line(self):
        """loops through various forms of the subject line
        and makes sure that tags and title are parsed out"""
        setting_backup = askbot_settings.TAGS_ARE_REQUIRED
        askbot_settings.update('TAGS_ARE_REQUIRED', True)
        user = AnonymousUser()
        for test_case in SUBJECT_LINE_CASES:
            self.data['subject'] = test_case[0]
            form = forms.AskByEmailForm(self.data, user=user)
            output = test_case[1]
            if output is None:
                self.assertFalse(form.is_valid())
            else:
                self.assertTrue(form.is_valid())
                self.assertEquals(
                    form.cleaned_data['tagnames'],
                    output[0]
                )
                self.assertEquals(
                    form.cleaned_data['title'],
                    output[1]
                )
        askbot_settings.update('TAGS_ARE_REQUIRED', setting_backup)

    def test_email(self):
        """loops through variants of the from field
        in the emails and tests the email address
        extractor"""
        user = AnonymousUser()
        for test_case in EMAIL_CASES:
            self.data['sender'] = test_case[0]
            expected_result = test_case[1]
            form = forms.AskByEmailForm(self.data, user=user)
            if expected_result is None:
                self.assertFalse(form.is_valid())
            else:
                self.assertTrue(form.is_valid())
                self.assertEquals(
                    form.cleaned_data['email'],
                    expected_result
                )


class TagNamesFieldTests(AskbotTestCase):
    def setUp(self):
        self.field = forms.TagNamesField()
        self.user = self.create_user('user1')

    def tearDown(self):
        askbot_settings.update('MANDATORY_TAGS', '')

    def clean(self, value):
        return self.field.clean(value).strip().split(' ')

    def assert_tags_equal(self, tag_list1, tag_list2):
        self.assertEqual(sorted(tag_list1), sorted(tag_list2))

    def test_force_lowercase(self):
        """FORCE_LOWERCASE setting is on
        """
        askbot_settings.update('FORCE_LOWERCASE_TAGS', True)
        cleaned_tags = self.clean('Tag1 TAG5 tag1 tag5')
        self.assert_tags_equal(cleaned_tags, ['tag1', 'tag5'])

    def test_custom_case(self):
        """FORCE_LOWERCASE setting is off
        """
        askbot_settings.update('FORCE_LOWERCASE_TAGS', False)
        models.Tag(name='TAG1', created_by=self.user).save()
        models.Tag(name='Tag2', created_by=self.user).save()
        cleaned_tags = self.clean('tag1 taG2 TAG1 tag3 tag3')
        self.assert_tags_equal(cleaned_tags, ['TAG1', 'Tag2', 'tag3'])

    def test_catch_missing_mandatory_tag(self):
        askbot_settings.update('MANDATORY_TAGS', 'one two')
        self.assertRaises(
            django_forms.ValidationError,
            self.clean,
            ('three',)
        )

    def test_pass_with_entered_mandatory_tag(self):
        askbot_settings.update('MANDATORY_TAGS', 'one two')
        cleaned_tags = self.clean('one')
        self.assert_tags_equal(cleaned_tags, ['one'])

    def test_pass_with_entered_wk_mandatory_tag(self):
        askbot_settings.update('MANDATORY_TAGS', 'one* two')
        askbot_settings.update('USE_WILDCARD_TAGS', True)
        cleaned_tags = self.clean('oneness')
        self.assert_tags_equal(cleaned_tags, ['oneness'])


class EditQuestionAnonymouslyFormTests(AskbotTestCase):
    """setup the following truth table
    on reveal_identity field:
    is_anon  can  owner  checked  result

    """
    truth_table = (
        (0, 0, 0, 0, False),
        (0, 0, 0, 1, False),
        (0, 0, 1, 0, False),
        (0, 0, 1, 1, False),
        (0, 1, 0, 0, False),
        (0, 1, 0, 1, False),
        (0, 1, 1, 0, False),
        (0, 1, 1, 1, False),  # all up to this point are False
        (1, 0, 0, 0, False),
        (1, 1, 0, 0, False),
        (1, 1, 1, 0, False),
        (1, 1, 1, 1, True),
    )

    # legend: is_anon - question is anonymous
    #         can - askbot_settings.ALLOW_ASK_ANONYMOUSLY
    #         owner - editor is question owner
    #         checked - the checkbox "reveal_identity" is marked
    def setUp(self):
        self.create_user()
        self.create_user(
            username='other_user',
            status='m'  # must be able to edit
        )
        super(EditQuestionAnonymouslyFormTests, self).setUp()

    def setup_data(self, is_anon, can_be_anon, is_owner, box_checked):
        """sets up data in the same order as shown in the
        truth table above

        the four positional arguments are in the same order
        """
        askbot_settings.update('ALLOW_ASK_ANONYMOUSLY', can_be_anon)
        question = self.post_question(is_anonymous=is_anon)
        if is_owner:
            editor = self.user
        else:
            editor = self.other_user
        data = {
            'tags': 'tag1 tag2',
            'text': 'ostaousohuosuh',
            'title': 'stahosetuhaoeudhuh'
        }
        if box_checked:
            data['reveal_identity'] = 'on'
        self.form = forms.EditQuestionForm(
                        data,
                        question=question,
                        user=editor,
                        revision=question.get_latest_revision(),
                    )

    def test_reveal_identity_field(self):
        """runs through the truth table and tests them items by one
        """
        current_item = 0
        for entry in self.truth_table:
            self.setup_data(*(entry[:4]))

            if self.form.is_valid():
                result = self.form.cleaned_data.get('reveal_identity', False)
            else:
                result = 'error'

            error_message = 'failed truth table item %d' % current_item
            current_item += 1

            expected_result = entry[4]
            self.assertEquals(result, expected_result, error_message)


class AskFormTests(AskbotTestCase):
    def setup_data(self, allow_anonymous=True, ask_anonymously=None):
        askbot_settings.update('ALLOW_ASK_ANONYMOUSLY', allow_anonymous)
        data = {
            'title': 'test title',
            'text': 'test content',
            'tags': 'test',
        }
        if ask_anonymously:
            data['ask_anonymously'] = 'on'
        self.form = forms.AskForm(data, user=AnonymousUser())
        self.form.full_clean()

    def assert_anon_is(self, value):
        self.assertEquals(
            self.form.cleaned_data['ask_anonymously'],
            value
        )

    def test_ask_anonymously_disabled(self):
        """test that disabled anon postings yields False"""
        self.setup_data(ask_anonymously=True, allow_anonymous=False)
        self.assert_anon_is(False)

    def test_ask_anonymously_field_positive(self):
        """check that the 'yes' selection goes through
        """
        self.setup_data(ask_anonymously=True)
        self.assert_anon_is(True)

    def test_ask_anonymously_field_negative(self):
        """check that the 'no' selection goes through
        """
        self.setup_data(ask_anonymously=False)
        self.assert_anon_is(False)


class UserStatusFormTest(AskbotTestCase):
    def setup_data(self, status):
        data = {'user_status': status, 'delete_content': False}
        self.moderator = self.create_user('moderator_user')
        self.moderator.set_status('m')
        self.subject = self.create_user('normal_user')
        self.subject.set_status('a')
        self.form = forms.ChangeUserStatusForm(data,
                                               moderator=self.moderator,
                                               subject=self.subject)

    def test_moderator_can_suspend_user(self):
        self.setup_data('s')
        self.assertEquals(self.form.is_valid(), True)

    def test_moderator_can_block_user(self):
        self.setup_data('s')
        self.assertEquals(self.form.is_valid(), True)

    def test_moderator_cannot_grant_admin(self):
        self.setup_data('d')
        self.assertEquals(self.form.is_valid(), False)

    def test_moderator_cannot_grant_moderator(self):
        self.setup_data('m')
        self.assertEquals(self.form.is_valid(), False)


# Test for askbot.utils.forms
class UserNameFieldTest(AskbotTestCase):
    def setUp(self):
        self.u1 = self.create_user('user1')
        self.username_field = util_forms.UserNameField()

    def test_clean(self):
        self.username_field.skip_clean = True
        self.assertEquals(self.username_field.clean('bar'), 'bar')  # Will pass anything

        self.username_field.skip_clean = False

        # Will not pass b/c instance is not User model
        self.username_field.user_instance = dict(foo=1)
        self.assertRaises(TypeError, self.username_field.clean, 'foo')

        self.username_field.user_instance = self.u1
        # Will pass
        self.assertEquals(self.username_field.clean('user1'), self.u1.username)

        # Not pass username required
        self.assertRaises(django_forms.ValidationError, self.username_field.clean, '')

        # Invalid username and username in reserved words
        self.assertRaises(django_forms.ValidationError, self.username_field.clean, '  ')
        self.assertRaises(django_forms.ValidationError, self.username_field.clean, 'fuck')
        self.assertEqual(self.username_field.clean('......'), '......')
        # TODO: test more things


class AnswerEditorFieldTests(AskbotTestCase):
    """don't need to test the QuestionEditorFieldTests, b/c the
    class is identical"""
    def setUp(self):
        self.old_min_length = askbot_settings.MIN_ANSWER_BODY_LENGTH
        askbot_settings.update('MIN_ANSWER_BODY_LENGTH', 10)
        self.field = forms.AnswerEditorField(user=AnonymousUser())

    def tearDown(self):
        askbot_settings.update('MIN_ANSWER_BODY_LENGTH', self.old_min_length)

    def test_fail_short_body(self):
        self.assertRaises(django_forms.ValidationError,
                          self.field.clean,
                          'a')

    def test_pass_long_body(self):
        self.assertEquals(self.field.clean(10*'a'), 10*'a')


class PostAsSomeoneFormTests(AskbotTestCase):

    form = forms.PostAsSomeoneForm

    def setUp(self):
        self.good_data = {
            'username': 'me',
            'email': 'me@example.com'
        }

    def test_blank_form_validates(self):
        form = forms.PostAsSomeoneForm({})
        self.assertEqual(form.is_valid(), True)

    def test_complete_form_validates(self):
        form = forms.PostAsSomeoneForm(self.good_data)
        self.assertEqual(form.is_valid(), True)

    def test_missing_email_fails(self):
        form = forms.PostAsSomeoneForm({'post_author_username': 'me'})
        self.assertEqual(form.is_valid(), False)

    def test_missing_username_fails(self):
        form = forms.PostAsSomeoneForm({'post_author_email': 'me@example.com'})
        self.assertEqual(form.is_valid(), False)


class AskWidgetFormTests(AskbotTestCase):
    def setUp(self):
        self.good_data = {'title': "What's the price of a house in london?"}
        self.good_data_anon = {
            'title': "What's the price of a house in london?",
            'ask_anonymously': True
        }

        self.bad_data = {'title': ''}

    def test_valid_input(self):
        form_object = forms.AskWidgetForm(
            include_text=False, data=self.good_data, user=AnonymousUser()
        )
        self.assertTrue(form_object.is_valid())
        form_object = forms.AskWidgetForm(
            include_text=False, data=self.good_data_anon, user=AnonymousUser()
        )
        self.assertTrue(form_object.is_valid())

    def test_invalid_input(self):
        form_object = forms.AskWidgetForm(
            include_text=False, data=self.bad_data, user=AnonymousUser()
        )
        self.assertFalse(form_object.is_valid())


TEXT_WITH_LINK = 'blah blah http://example.com/url/image.png'


class EditorFieldTests(AskbotTestCase):

    def setUp(self):
        self.user = self.create_user('user')
        self.user.reputation = 5
        self.user.save()

    @with_settings(EDITOR_TYPE='markdown', MIN_REP_TO_SUGGEST_LINK=10)
    def test_low_rep_user_cannot_post_links_markdown(self):
        field = forms.EditorField(user=self.user)
        self.assertRaises(
            django_forms.ValidationError, field.clean, TEXT_WITH_LINK
        )

    @with_settings(EDITOR_TYPE='tinymce', MIN_REP_TO_SUGGEST_LINK=10)
    def test_low_rep_user_cannot_post_links_tinymce(self):
        field = forms.EditorField(user=self.user)
        self.assertRaises(
            django_forms.ValidationError, field.clean, TEXT_WITH_LINK
        )


class CleanTagTest(AskbotTestCase):
    def test_look_in_db_true(self):
        tag_name = u'foo'
        new_name = forms.clean_tag(tag_name, look_in_db=True)
        self.assertEqual(tag_name, new_name)

    def test_look_in_db_false(self):
        tag_name = u'foo'
        new_name = forms.clean_tag(tag_name, look_in_db=False)
        self.assertEqual(tag_name, new_name)

    def test_name_too_long(self):
        tag_name = u'foo' * askbot_settings.MAX_TAG_LENGTH
        with self.assertRaises(forms.forms.ValidationError):
            forms.clean_tag(tag_name, look_in_db=True)
