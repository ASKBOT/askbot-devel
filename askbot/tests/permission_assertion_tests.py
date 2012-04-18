import datetime
from django.test.client import Client
from django.core.urlresolvers import reverse
from django.conf import settings
from django.test import TestCase
from django.core import exceptions
from askbot.tests import utils
from askbot.conf import settings as askbot_settings
from askbot import models
from askbot.templatetags import extra_filters as template_filters
from askbot.tests.utils import skipIf


class PermissionAssertionTestCase(TestCase):
    """base TestCase class for permission
    assertion tests

    subclass may redefine method extraSetUp
    """

    def setUp(self):
        self.user = utils.create_user(
                            username = 'test',
                            email = 'test@test.com'
                        )
        self.extraSetUp()

    def extraSetUp(self):
        pass

    def create_other_user(self):
        return utils.create_user(
                        username = 'other',
                        email = 'other@test.com'
                    )

    def post_question(self, author = None, timestamp = None):
        if author is None:
            author = self.user
        return author.post_question(
                            title = 'test question title',
                            body_text = 'test question body',
                            tags = 'test',
                            timestamp = timestamp
                        )

    def post_answer(self, question = None, author = None):
        if author is None:
            author = self.user
        return author.post_answer(
                        question = question,
                        body_text = 'test answer'
                    )

class SeeOffensiveFlagsPermissionAssertionTests(utils.AskbotTestCase):

    def setUp(self):
        super(SeeOffensiveFlagsPermissionAssertionTests, self).setUp()
        self.create_user()
        self.create_user(username = 'other_user')
        self.min_rep = askbot_settings.MIN_REP_TO_VIEW_OFFENSIVE_FLAGS

    def setup_answer(self):
        question = self.post_question()
        answer = self.post_answer(question = question)
        return answer

    def test_low_rep_user_cannot_see_flags(self):
        question = self.post_question()
        assert(self.other_user.reputation < self.min_rep)
        self.assertFalse(
            template_filters.can_see_offensive_flags(
                self.other_user,
                question
            )
        )

    def test_high_rep_user_can_see_flags(self):
        question = self.post_question()
        self.other_user.reputation = self.min_rep
        self.assertTrue(
            template_filters.can_see_offensive_flags(
                self.other_user,
                question
            )
        )

    def test_low_rep_owner_can_see_flags(self):
        question = self.post_question()
        assert(self.user.reputation < self.min_rep)
        self.assertTrue(
            template_filters.can_see_offensive_flags(
                self.user,
                question
            )
        )

    def test_admin_can_see_flags(self):
        question = self.post_question()
        self.other_user.set_admin_status()
        self.other_user.save()
        assert(self.other_user.reputation < self.min_rep)
        self.assertTrue(
            template_filters.can_see_offensive_flags(
                self.other_user,
                question
            )
        )

    def test_moderator_can_see_flags(self):
        question = self.post_question()
        self.other_user.set_status('m')
        assert(self.other_user.reputation < self.min_rep)
        self.assertTrue(
            template_filters.can_see_offensive_flags(
                self.other_user,
                question
            )
        )

    #tests below test answers only
    def test_suspended_owner_can_see_flags(self):
        answer = self.setup_answer()
        self.user.set_status('s')
        assert(self.user.reputation < self.min_rep)
        self.assertTrue(
            template_filters.can_see_offensive_flags(
                self.user,
                answer
            )
        )

    def test_blocked_owner_can_see_flags(self):
        answer = self.setup_answer()
        self.user.set_status('b')
        assert(self.user.reputation < self.min_rep)
        self.assertTrue(
            template_filters.can_see_offensive_flags(
                self.user,
                answer
            )
        )

    def test_suspended_user_cannot_see_flags(self):
        answer = self.setup_answer()
        self.other_user.set_status('s')
        self.assertFalse(
            template_filters.can_see_offensive_flags(
                self.other_user,
                answer
            )
        )

    def test_blocked_user_cannot_see_flags(self):
        answer = self.setup_answer()
        self.other_user.set_status('b')
        self.assertFalse(
            template_filters.can_see_offensive_flags(
                self.other_user,
                answer
            )
        )

class DeleteAnswerPermissionAssertionTests(utils.AskbotTestCase):
    
    def setUp(self):
        self.create_user()
        self.create_user(username = 'other_user')
        self.question = self.post_question()
        self.min_rep = askbot_settings.MIN_REP_TO_DELETE_OTHERS_POSTS

    def post_answer(self, user = None):
        if user is None:
            user = self.user
        self.answer = super(
                            DeleteAnswerPermissionAssertionTests,
                            self
                        ).post_answer(
                            question = self.question,
                            user = user
                        )

    def assert_can_delete(self):
        self.user.assert_can_delete_answer(self.answer)

    def assert_cannot_delete(self):
        self.assertRaises(
            exceptions.PermissionDenied,
            self.user.assert_can_delete_answer,
            answer = self.answer
        )

    def test_low_rep_user_cannot_delete(self):
        self.post_answer(user = self.other_user)
        assert(self.user.reputation < self.min_rep)
        self.assert_cannot_delete()

    def test_high_rep_user_can_delete(self):
        self.post_answer(user = self.other_user)
        self.user.reputation = self.min_rep
        self.assert_can_delete()

    def test_low_rep_owner_can_delete(self):
        self.post_answer()
        assert(self.user.reputation < self.min_rep)
        self.assert_can_delete()

    def test_suspended_owner_can_delete(self):
        self.post_answer()
        assert(self.user.reputation < self.min_rep)
        self.user.set_status('s')
        self.assert_can_delete()

    def test_blocked_owner_cannot_delete(self):
        self.post_answer()
        assert(self.user.reputation < self.min_rep)
        self.user.set_status('b')
        self.assert_cannot_delete()

    def test_blocked_user_cannot_delete(self):
        self.post_answer(user = self.other_user)
        self.user.set_status('b')
        self.assert_cannot_delete()

    def test_high_rep_blocked_owner_cannot_delete(self):
        self.post_answer()
        self.user.set_status('b')
        self.user.reputation = 100000
        self.assert_cannot_delete()

    def test_low_rep_admin_can_delete(self):
        self.post_answer(user = self.other_user)
        self.user.set_admin_status()
        self.user.save()
        assert(self.user.reputation < self.min_rep)
        self.assert_can_delete()

    def test_low_rep_moderator_can_delete(self):
        self.post_answer(user = self.other_user)
        self.user.set_status('m')
        assert(self.user.reputation < self.min_rep)
        self.assert_can_delete()

class DeleteQuestionPermissionAssertionTests(utils.AskbotTestCase):
    """These specifically test cases where user is
    owner of the question

    all other cases are the same as DeleteAnswer...
    """

    def setUp(self):
        self.create_user()
        self.create_user(username = 'other_user')
        self.question = self.post_question()

    def assert_can_delete(self):
        self.user.assert_can_delete_question(
                                question = self.question
                            )

    def assert_cannot_delete(self):
        self.assertRaises(
            exceptions.PermissionDenied,
            self.user.assert_can_delete_question,
            question = self.question
        )

    def upvote_answer(self, answer = None, user = None):
        if user is None:
            user = self.user
        user.reputation = askbot_settings.MIN_REP_TO_VOTE_UP
        user.upvote(answer)

    def test_owner_can_delete_question_with_nonvoted_answer_by_other(self):
        self.post_answer(
                    user = self.other_user,
                    question = self.question
                )
        self.assert_can_delete()

    def test_owner_can_delete_question_with_upvoted_answer_posted_by_self(self):
        answer = self.post_answer(
                    user = self.user,
                    question = self.question
                )
        self.upvote_answer(
                    answer = answer,
                    user = self.other_user
                )
        self.assert_can_delete()

    def test_owner_cannot_delete_question_with_upvoted_answer_posted_by_other(self):
        answer = self.post_answer(
                    user = self.other_user,
                    question = self.question
                )
        self.upvote_answer(
                    answer = answer,
                    user = self.user
                )
        self.assert_cannot_delete()

    def test_owner_can_delete_question_without_answers(self):
        self.assert_can_delete()

    def test_moderator_can_delete_question_with_upvoted_answer_by_other(self):
        self.user.set_status('m')
        answer = self.post_answer(
                    user = self.other_user,
                    question = self.question
                )
        self.user.upvote(answer)
        self.assert_can_delete()


class CloseQuestionPermissionAssertionTests(utils.AskbotTestCase):
    
    def setUp(self):
        super(CloseQuestionPermissionAssertionTests, self).setUp()
        self.create_user()
        self.create_user(username = 'other_user')
        self.question = self.post_question()
        self.min_rep = askbot_settings.MIN_REP_TO_CLOSE_OTHERS_QUESTIONS
        self.min_rep_own = askbot_settings.MIN_REP_TO_CLOSE_OWN_QUESTIONS

    def assert_can_close(self, user = None):
        user.assert_can_close_question(self.question)
        self.assertTrue(
            template_filters.can_close_question(
                user,
                self.question
            )
        )

    def assert_cannot_close(self, user = None):
        self.assertRaises(
            exceptions.PermissionDenied,
            user.assert_can_close_question,
            self.question
        )
        self.assertFalse(
            template_filters.can_close_question(
                user,
                self.question
            )
        )

    def test_low_rep_admin_can_close(self):
        self.other_user.set_admin_status()
        self.other_user.save()
        assert(self.other_user.reputation < self.min_rep)
        self.assert_can_close(user = self.other_user)

    def test_low_rep_moderator_can_close(self):
        self.other_user.set_status('m')
        assert(self.other_user.reputation < self.min_rep)
        self.assert_can_close(user = self.other_user)

    def test_low_rep_owner_cannot_close(self):
        assert(self.user.reputation < self.min_rep)
        assert(self.user.reputation < self.min_rep_own)
        self.assert_cannot_close(user = self.user)

    def test_high_rep_owner_can_close(self):
        self.user.reputation = self.min_rep_own
        self.assert_can_close(user = self.user)

    def test_high_rep_other_can_close(self):
        self.other_user.reputation = self.min_rep
        self.assert_can_close(user = self.other_user)

    def test_low_rep_blocked_cannot_close(self):
        self.other_user.set_status('b')
        assert(self.other_user.reputation < self.min_rep)
        self.assert_cannot_close(user = self.other_user)

    def test_high_rep_blocked_cannot_close(self):
        self.other_user.set_status('b')
        self.other_user.reputation = self.min_rep
        self.assert_cannot_close(user = self.other_user)

    def test_medium_rep_blocked_owner_cannot_close(self):
        self.user.set_status('b')
        self.user.reputation = self.min_rep_own
        self.assert_cannot_close(user = self.user)

    def test_high_rep_blocked_owner_cannot_close(self):
        self.user.set_status('b')
        self.user.reputation = self.min_rep
        self.assert_cannot_close(user = self.user)

    def test_low_rep_suspended_cannot_close(self):
        self.other_user.set_status('s')
        assert(self.other_user.reputation < self.min_rep)
        self.assert_cannot_close(user = self.other_user)

    def test_high_rep_suspended_cannot_close(self):
        self.other_user.set_status('s')
        self.other_user.reputation = self.min_rep
        self.assert_cannot_close(user = self.other_user)

    def test_medium_rep_suspended_owner_cannot_close(self):
        self.user.set_status('s')
        self.user.reputation = self.min_rep_own
        self.assert_cannot_close(user = self.user)

    def test_high_rep_suspended_owner_cannot_close(self):
        self.user.set_status('s')
        self.user.reputation = self.min_rep
        self.assert_cannot_close(user = self.user)


class ReopenQuestionPermissionAssertionTests(utils.AskbotTestCase):
    """rules to reo
        user = self,
        post = question,
        admin_or_moderator_required = True,
        owner_can = True,
        owner_min_rep_setting = owner_min_rep_setting,
        owner_low_rep_error_message = owner_low_rep_error_message,
        general_error_message = general_error_message
    """

    def setUp(self):
        self.min_rep = askbot_settings.MIN_REP_TO_REOPEN_OWN_QUESTIONS
        self.create_user()
        self.create_user(username = 'other_user')
        self.question = self.post_question()
        self.user.set_status('m')
        self.user.close_question(self.question)
        self.user.set_status('a')

    def assert_can_reopen(self, user = None):
        if user == None:
            user = self.user

        user.assert_can_reopen_question(self.question)

    def assert_cannot_reopen(self, user = None):
        if user == None:
            user = self.user

        self.assertRaises(
            exceptions.PermissionDenied,
            user.assert_can_reopen_question,
            question = self.question
        )


    def test_high_rep_nonowner_cannot_reopen(self):
        self.other_user.reputation = 1000000
        self.assert_cannot_reopen(user = self.other_user)

    def test_low_rep_admin_can_reopen(self):
        self.other_user.set_admin_status()
        self.assert_can_reopen(user = self.other_user)

    def test_low_rep_moderator_can_reopen(self):
        self.other_user.set_status('m')
        self.assert_can_reopen(user = self.other_user)

    def test_low_rep_owner_cannot_reopen(self):
        self.assert_cannot_reopen()

    def test_high_rep_owner_can_reopen(self):
        self.user.reputation = self.min_rep
        self.assert_can_reopen()

    def test_high_rep_suspended_owner_cannot_reopen(self):
        self.user.reputation = self.min_rep
        self.user.set_status('s')
        self.assert_cannot_reopen()

    def test_high_rep_blocked_cannot_reopen(self):
        self.other_user.reputation = self.min_rep
        self.other_user.set_status('b')
        self.assert_cannot_reopen(user = self.other_user)

    def test_high_rep_suspended_cannot_reopen(self):
        self.other_user.reputation = self.min_rep
        self.other_user.set_status('s')
        self.assert_cannot_reopen(user = self.other_user)

class EditQuestionPermissionAssertionTests(utils.AskbotTestCase):
    
    def setUp(self):
        self.create_user()
        self.create_user(username = 'other_user')
        self.post = self.post_question()
        self.min_rep = askbot_settings.MIN_REP_TO_EDIT_OTHERS_POSTS
        self.min_rep_wiki = askbot_settings.MIN_REP_TO_EDIT_WIKI

    def assert_user_can(
                    self,
                    user = None,
                ):
        if user is None:
            user = self.user

        user.assert_can_edit_post(self.post)
        self.assertTrue(
            template_filters.can_edit_post(user, self.post)
        )

    def assert_user_cannot(
                    self,
                    user = None,
                ):
        if user is None:
            user = self.user

        self.assertRaises(
                    exceptions.PermissionDenied,
                    user.assert_can_edit_post,
                    self.post
                )
        self.assertFalse(
            template_filters.can_edit_post(user, self.post)
        )

    def assert_other_can(self):
        self.assert_user_can(user = self.other_user)

    def assert_other_cannot(self):
        self.assert_user_cannot(user = self.other_user)

    def test_admin_can_edit(self):
        self.other_user.set_admin_status()
        self.other_user.save()
        self.assert_other_can()

    def test_admin_can_edit_deleted(self):
        self.post.deleted = True
        self.other_user.set_admin_status()
        self.other_user.save()
        self.assert_other_can()

    def test_mod_can_edit(self):
        self.other_user.set_status('m')
        self.assert_other_can()

    def test_low_rep_user_cannot_edit_others_post(self):
        assert(self.other_user.reputation < self.min_rep)
        self.assert_other_cannot()

    def test_low_rep_user_cannot_edit_others_wiki(self):
        self.post.wiki = True
        assert(self.other_user.reputation < self.min_rep_wiki)
        self.assert_other_cannot()

    def test_low_rep_user_can_edit_own_wiki(self):
        self.post.wiki = True
        self.assert_user_can()

    def test_medium_rep_user_can_edit_others_wiki(self):
        self.post.wiki = True
        self.other_user.reputation = self.min_rep_wiki
        self.assert_other_can()

    def test_high_rep_user_can_edit_others_post(self):
        self.other_user.reputation = self.min_rep
        self.assert_other_can()

    #def test_medium_rep_user_can_edit_others_wiki(self):
    #def test_low_rep_user_can_edit_own_wiki(self):
    #def test_low_rep_user_cannot_edit_others_wiki(self):
    #def test_high_rep_blocked_cannot_edit_others_wiki(self):
    def test_medium_rep_user_cannot_edit_others_post(self):
        self.other_user.reputation = self.min_rep_wiki
        self.assert_other_cannot()

    def test_high_rep_user_cannot_edit_others_deleted_post(self):
        self.other_user.reputation = self.min_rep
        self.post.deleted = True
        self.assert_other_cannot()

    def test_high_rep_user_cannot_edit_others_deleted_wiki(self):
        self.other_user.reputation = self.min_rep
        self.post.deleted = True
        self.post.wiki = True
        self.assert_other_cannot()

    def test_low_rep_suspended_can_edit_own_post(self):
        self.user.set_status('s')
        assert(self.user.reputation < self.min_rep)
        self.assert_user_can()

    def test_low_rep_suspended_can_edit_own_deleted_post(self):
        self.user.set_status('s')
        self.post.deleted = True
        self.assert_user_can()

    def test_high_rep_suspended_cannot_edit_others_deleted_post(self):
        self.other_user.reputation = self.min_rep
        self.other_user.set_status('s')
        self.post.deleted = True
        self.assert_other_cannot()

    def test_high_rep_suspended_cannot_edit_others_post(self):
        self.other_user.set_status('s')
        self.other_user.reputation = self.min_rep
        self.assert_other_cannot()

    def test_high_rep_blocked_cannot_edit_own_post(self):
        self.user.set_status('b')
        self.user.reputation = self.min_rep
        self.assert_user_cannot()

    def test_high_rep_blocked_cannot_edit_others_post(self):
        self.user.set_status('b')
        self.user.reputation = self.min_rep
        self.assert_user_cannot()

    def test_high_rep_blocked_cannot_edit_others_deleted_post(self):
        self.other_user.set_status('b')
        self.other_user.reputation = self.min_rep
        self.post.deleted = True
        self.assert_other_cannot()

    def test_high_rep_blocked_cannot_edit_others_wiki(self):
        self.other_user.set_status('b')
        self.other_user.reputation = self.min_rep
        self.post.wiki = True
        self.assert_other_cannot()

class EditAnswerPermissionAssertionTests(
            EditQuestionPermissionAssertionTests
        ):
    def setUp(self):
        super(
                EditAnswerPermissionAssertionTests,
                self,
            ).setUp()
        self.post = self.post_answer(question = self.post)

    def assert_user_can(
                    self,
                    user = None,
                ):
        if user is None:
            user = self.user

        user.assert_can_edit_answer(self.post)
        self.assertTrue(
            template_filters.can_edit_post(user, self.post)
        )

    def assert_user_cannot(
                    self,
                    user = None,
                ):
        if user is None:
            user = self.user

        self.assertRaises(
                    exceptions.PermissionDenied,
                    user.assert_can_edit_answer,
                    self.post
                )
        self.assertFalse(
            template_filters.can_edit_post(user, self.post)
        )


class RetagQuestionPermissionAssertionTests(
            EditQuestionPermissionAssertionTests
        ):

    def setUp(self):
        super(
                RetagQuestionPermissionAssertionTests,
                self,
            ).setUp()
        self.min_rep = askbot_settings.MIN_REP_TO_RETAG_OTHERS_QUESTIONS

    def assert_user_can(
                    self,
                    user = None,
                ):
        if user is None:
            user = self.user

        user.assert_can_retag_question(self.post)
        self.assertTrue(
            template_filters.can_retag_question(user, self.post)
        )

    def assert_user_cannot(
                    self,
                    user = None,
                ):
        if user is None:
            user = self.user

        self.assertRaises(
                    exceptions.PermissionDenied,
                    user.assert_can_retag_question,
                    self.post
                )
        self.assertFalse(
            template_filters.can_edit_post(user, self.post)
        )
    def test_medium_rep_user_can_edit_others_wiki(self):
        pass
    def test_low_rep_user_can_edit_own_wiki(self):
        pass
    def test_low_rep_user_cannot_edit_others_wiki(self):
        pass
    def test_high_rep_blocked_cannot_edit_others_wiki(self):
        pass
    def test_medium_rep_user_cannot_edit_others_post(self):
        pass

class FlagOffensivePermissionAssertionTests(PermissionAssertionTestCase):

    def extraSetUp(self):
        self.min_rep = askbot_settings.MIN_REP_TO_FLAG_OFFENSIVE
        self.question = self.post_question()
        self.answer = self.post_answer(question = self.question)

    def assert_user_cannot_flag(self):
        self.assertRaises(
            exceptions.PermissionDenied,
            self.user.flag_post,
            post = self.question
        )
        self.assertFalse(
            template_filters.can_flag_offensive(
                self.user,
                self.question
            )
        )
        self.assertRaises(
            exceptions.PermissionDenied,
            self.user.flag_post,
            post = self.answer
        )
        self.assertFalse(
            template_filters.can_flag_offensive(
                self.user,
                self.answer
            )
        )

    def assert_user_can_flag(self):
        self.user.flag_post(post = self.question)
        self.assertTrue(
            template_filters.can_flag_offensive(
                self.user,
                self.question
            )
        )
        self.user.flag_post(post = self.answer)
        self.assertTrue(
            template_filters.can_flag_offensive(
                self.user,
                self.answer
            )
        )

    def setup_high_rep(self):
        #there is a catch - assert_user_can_flag
        #flags twice and each time user reputation
        #suffers a hit, so test may actually fail
        #set amply high reputation
        extra_rep = -100 * askbot_settings.REP_LOSS_FOR_RECEIVING_FLAG
        #NB: REP_LOSS is negative
        self.user.reputation = self.min_rep + extra_rep
        self.user.save()

    def test_high_rep_user_cannot_exceed_max_flags_per_day(self):
        max_flags = askbot_settings.MAX_FLAGS_PER_USER_PER_DAY
        other_user = self.create_other_user()
        other_user.reputation = self.min_rep
        for i in range(max_flags):
            question = self.post_question()
            other_user.flag_post(question)
        question = self.post_question()
        self.assertRaises(
            exceptions.PermissionDenied,
            other_user.flag_post,
            question
        )

    def test_admin_has_no_limit_for_flags_per_day(self):
        max_flags = askbot_settings.MAX_FLAGS_PER_USER_PER_DAY
        other_user = self.create_other_user()
        other_user.set_admin_status()
        other_user.save()
        for i in range(max_flags + 1):
            question = self.post_question()
            other_user.flag_post(question)

    def test_moderator_has_no_limit_for_flags_per_day(self):
        max_flags = askbot_settings.MAX_FLAGS_PER_USER_PER_DAY
        other_user = self.create_other_user()
        other_user.set_status('m')
        for i in range(max_flags + 1):
            question = self.post_question()
            other_user.flag_post(question)

    def test_low_rep_user_cannot_flag(self):
        assert(self.user.reputation < self.min_rep)
        self.assert_user_cannot_flag()

    def test_high_rep_blocked_or_suspended_user_cannot_flag(self):
        self.setup_high_rep()
        self.user.set_status('b')
        self.assert_user_cannot_flag()
        self.user.set_status('s')
        self.assert_user_cannot_flag()

    def test_high_rep_user_can_flag(self):
        self.setup_high_rep()
        self.assert_user_can_flag()

    def test_low_rep_moderator_can_flag(self):
        assert(self.user.reputation < self.min_rep)
        self.user.set_status('m')
        self.assert_user_can_flag()

    def low_rep_administrator_can_flag(self):
        assert(self.user.reputation < self.min_rep)
        self.user.set_admin_status()
        self.assert_user_can_flag()

    def test_superuser_cannot_flag_question_twice(self):
        self.user.set_admin_status()
        self.user.save()
        self.user.flag_post(post = self.question)
        self.assertRaises(
            exceptions.PermissionDenied,
            self.user.flag_post,
            post = self.question
        )
        #here is a deviation - the link will still be shown
        #in templates
        self.assertTrue(
            template_filters.can_flag_offensive(
                self.user,
                self.question
            )
        )

    def test_superuser_cannot_flag_answer_twice(self):
        self.user.set_admin_status()
        self.user.save()
        self.user.flag_post(post = self.answer)
        self.assertRaises(
            exceptions.PermissionDenied,
            self.user.flag_post,
            post = self.answer
        )
        self.assertTrue(
            template_filters.can_flag_offensive(
                self.user,
                self.answer
            )
        )

    def test_high_rep_user_cannot_flag_question_twice(self):
        self.user.reputation = self.min_rep
        self.user.flag_post(post = self.question)
        self.assertRaises(
            exceptions.PermissionDenied,
            self.user.flag_post,
            post = self.question
        )
        self.assertTrue(
            template_filters.can_flag_offensive(
                self.user,
                self.question
            )
        )

    def test_high_rep_user_cannot_flag_answer_twice(self):
        self.user.reputation = self.min_rep
        self.user.flag_post(post = self.answer)
        self.assertRaises(
            exceptions.PermissionDenied,
            self.user.flag_post,
            post = self.answer
        )
        self.assertTrue(
            template_filters.can_flag_offensive(
                self.user,
                self.answer
            )
        )


class CommentPermissionAssertionTests(PermissionAssertionTestCase):

    def extraSetUp(self):
        self.min_rep = askbot_settings.MIN_REP_TO_LEAVE_COMMENTS
        self.other_user = self.create_other_user()

    def test_blocked_user_cannot_comment_own_question(self):
        question = self.post_question()

        self.user.set_status('b')
        self.assertRaises(
                    exceptions.PermissionDenied,
                    self.user.post_comment,
                    parent_post = question,
                    body_text = 'test comment'
                )
        self.assertFalse(
                template_filters.can_post_comment(
                    self.user,
                    question
                )
            )

    def test_blocked_user_cannot_comment_own_answer(self):
        question = self.post_question()
        answer = self.post_answer(question)

        self.user.set_status('b')

        self.assertRaises(
                    exceptions.PermissionDenied,
                    self.user.post_comment,
                    parent_post = answer,
                    body_text = 'test comment'
                )
        self.assertFalse(
                template_filters.can_post_comment(
                        self.user,
                        answer
                    )
            )

    def test_blocked_user_cannot_delete_own_comment(self):
        question = self.post_question()
        comment = self.user.post_comment(
                        parent_post = question,
                        body_text = 'test comment'
                    )
        self.user.set_status('b')
        self.assertRaises(
            exceptions.PermissionDenied,
            self.user.delete_post,
            post = comment
        )
        self.assertFalse(
            template_filters.can_delete_comment(
                self.user, 
                comment
            )
        )

    def test_low_rep_user_cannot_delete_others_comment(self):
        question = self.post_question()
        comment = self.user.post_comment(
                        parent_post = question,
                        body_text = 'test comment'
                    )
        assert(
            self.other_user.reputation < \
            askbot_settings.MIN_REP_TO_DELETE_OTHERS_COMMENTS
        )
        self.assertRaises(
            exceptions.PermissionDenied,
            self.other_user.delete_post,
            post = comment
        )
        self.assertFalse(
            template_filters.can_delete_comment(
                self.other_user, 
                comment
            )
        )

    def test_high_rep_user_can_delete_comment(self):
        question = self.post_question()
        comment = self.user.post_comment(
                        parent_post = question,
                        body_text = 'test comment'
                    )
        self.other_user.reputation = \
            askbot_settings.MIN_REP_TO_DELETE_OTHERS_COMMENTS

        self.other_user.delete_comment(comment)
        self.assertTrue(
            template_filters.can_delete_comment(
                self.other_user, 
                comment
            )
        )

    def test_low_rep_user_can_delete_own_comment(self):
        question = self.post_question()
        answer = self.other_user.post_answer(
                        question = question,
                        body_text = 'test answer'
                    )
        comment = self.user.post_comment(
                        parent_post = answer,
                        body_text = 'test comment'
                    )
        assert(
            self.user.reputation < \
            askbot_settings.MIN_REP_TO_DELETE_OTHERS_COMMENTS
        )
        self.user.delete_comment(comment)
        self.assertTrue(
            template_filters.can_delete_comment(
                self.user, 
                comment
            )
        )

    def test_moderator_can_delete_comment(self):
        question = self.post_question()
        comment = self.user.post_comment(
                        parent_post = question,
                        body_text = 'test comment'
                    )
        self.other_user.set_status('m')
        self.other_user.delete_comment(comment)
        self.assertTrue(
            template_filters.can_delete_comment(
                self.other_user, 
                comment
            )
        )

    def test_admin_can_delete_comment(self):
        question = self.post_question()
        comment = self.user.post_comment(
                        parent_post = question,
                        body_text = 'test comment'
                    )
        self.other_user.set_admin_status()
        self.other_user.save()
        self.other_user.delete_comment(comment)
        self.assertTrue(
            template_filters.can_delete_comment(
                self.other_user, 
                comment
            )
        )

    def test_high_rep_suspended_user_cannot_delete_others_comment(self):
        question = self.post_question()
        comment = self.user.post_comment(
                        parent_post = question,
                        body_text = 'test comment'
                    )
        self.other_user.reputation = \
            askbot_settings.MIN_REP_TO_DELETE_OTHERS_COMMENTS + 1
        self.other_user.set_status('s')
        self.assertRaises(
                exceptions.PermissionDenied,
                self.other_user.delete_post,
                post = comment
            )
        self.assertFalse(
            template_filters.can_delete_comment(
                self.other_user, 
                comment
            )
        )

    def test_suspended_user_can_delete_own_comment(self):
        question = self.post_question()
        comment = self.user.post_comment(
                        parent_post = question,
                        body_text = 'test comment'
                    )
        self.user.set_status('s')
        self.user.delete_comment(comment)
        self.assertTrue(
            template_filters.can_delete_comment(
                self.user, 
                comment
            )
        )

    def test_low_rep_user_cannot_comment_others(self):
        question = self.post_question(
                            author = self.other_user
                        )
        assert(self.user.reputation < self.min_rep)
        self.assertRaises(
                    exceptions.PermissionDenied,
                    self.user.post_comment,
                    parent_post = question,
                    body_text = 'test comment'
                )
        self.assertFalse(
                template_filters.can_post_comment(
                    self.user,
                    question
                )
            )

    def test_low_rep_user_can_comment_others_answer_to_own_question(self):
        question = self.post_question()
        assert(self.user.reputation < self.min_rep)
        answer = self.other_user.post_answer(
                        question = question,
                        body_text = 'test answer'
                    )
        comment = self.user.post_comment(
                                    parent_post = answer,
                                    body_text = 'test comment'
                                )
        self.assertTrue(isinstance(comment, models.Comment))
        self.assertTrue(
            template_filters.can_post_comment(
                self.user,
                answer
            )
        )

    def test_high_rep_user_can_comment(self):
        question = self.post_question(
                            author = self.other_user
                        )
        self.user.reputation = self.min_rep
        comment = self.user.post_comment(
                            parent_post = question,
                            body_text = 'test comment'
                        )
        self.assertTrue(isinstance(comment, models.Comment))
        self.assertTrue(
            template_filters.can_post_comment(
                self.user,
                question
            )
        )

    def test_suspended_user_cannot_comment_others_question(self):
        question = self.post_question(author = self.other_user)
        self.user.set_status('s')
        self.assertRaises(
                exceptions.PermissionDenied,
                self.user.post_comment,
                parent_post = question,
                body_text = 'test comment'
            )
        self.assertFalse(
            template_filters.can_post_comment(
                self.user,
                question
            )
        )

    def test_suspended_user_can_comment_own_question(self):
        question = self.post_question()
        self.user.set_status('s')
        comment = self.user.post_comment(
                            parent_post = question,
                            body_text = 'test comment'
                        )
        self.assertTrue(isinstance(comment, models.Comment))
        self.assertTrue(
            template_filters.can_post_comment(
                self.user,
                question
            )
        )

    def test_low_rep_admin_can_comment_others_question(self):
        question = self.post_question()
        self.other_user.set_admin_status()
        self.other_user.save()
        assert(self.other_user.is_administrator())
        assert(self.other_user.reputation < self.min_rep)
        comment = self.other_user.post_comment(
                            parent_post = question,
                            body_text = 'test comment'
                        )
        self.assertTrue(isinstance(comment, models.Comment))
        self.assertTrue(
            template_filters.can_post_comment(
                self.other_user,
                question
            )
        )

    def test_low_rep_moderator_can_comment_others_question(self):
        question = self.post_question()
        self.other_user.set_status('m')
        assert(self.other_user.is_moderator())
        assert(self.other_user.reputation < self.min_rep)
        comment = self.other_user.post_comment(
                            parent_post = question,
                            body_text = 'test comment'
                        )
        self.assertTrue(isinstance(comment, models.Comment))
        self.assertTrue(
            template_filters.can_post_comment(
                self.other_user,
                question
            )
        )

    def assert_user_can_edit_previous_comment(
                                            self,
                                            old_timestamp = None,
                                            original_poster = None
                                        ):
        """oriposts a question and a comment at
        an old timestamp, then posts another comment now
        then user tries to edit the first comment
        """
        self.other_user.set_admin_status()
        self.other_user.save()

        if original_poster is None:
            original_poster = self.user

        question = self.post_question(
                            author = original_poster,
                            timestamp = old_timestamp
                        )
        comment1 = original_poster.post_comment(
                                    parent_post = question,
                                    timestamp = old_timestamp,
                                    body_text = 'blah'
                                )
        comment2 = self.other_user.post_comment(#post this one with the current timestamp
                                    parent_post = question,
                                    body_text = 'blah'
                                )
        self.user.assert_can_edit_comment(comment1)

    def assert_user_can_edit_very_old_comment(self, original_poster = None):
        """tries to edit comment in the most restictive situation
        """
        askbot_settings.update('USE_TIME_LIMIT_TO_EDIT_COMMENT', True)
        askbot_settings.update('MINUTES_TO_EDIT_COMMENT', 0)
        old_timestamp = datetime.datetime.now() - datetime.timedelta(1)
        self.assert_user_can_edit_previous_comment(
                                    old_timestamp = old_timestamp,
                                    original_poster = original_poster
                                )


    def test_admin_can_edit_very_old_comment(self):
        self.user.set_admin_status()
        self.user.save()
        self.assert_user_can_edit_very_old_comment(original_poster = self.other_user)

    def test_moderator_can_edit_very_old_comment(self):
        self.user.set_status('m')
        self.user.save()
        self.assert_user_can_edit_very_old_comment(original_poster = self.other_user)

    def test_regular_user_cannot_edit_very_old_comment(self):
        self.assertRaises(
            exceptions.PermissionDenied,
            self.assert_user_can_edit_very_old_comment,
            original_poster = self.user
        )

    def test_regular_user_can_edit_reasonably_old_comment(self):
        self.user.set_status('a')
        self.user.save()
        askbot_settings.update('USE_TIME_LIMIT_TO_EDIT_COMMENT', True)
        askbot_settings.update('MINUTES_TO_EDIT_COMMENT', 10)
        #about 3 min ago
        old_timestamp = datetime.datetime.now() - datetime.timedelta(0, 200)
        self.assert_user_can_edit_previous_comment(
                                old_timestamp = old_timestamp,
                                original_poster = self.user
                            )

    def test_disable_comment_edit_time_limit(self):
        self.user.set_status('a')
        self.user.save()
        askbot_settings.update('USE_TIME_LIMIT_TO_EDIT_COMMENT', False)
        askbot_settings.update('MINUTES_TO_EDIT_COMMENT', 10)
        old_timestamp = datetime.datetime.now() - datetime.timedelta(365)#a year ago
        self.assert_user_can_edit_previous_comment(
                                old_timestamp = old_timestamp,
                                original_poster = self.user
                            )


    def test_regular_user_can_edit_last_comment(self):
        """and a very old last comment"""
        self.user.set_status('a')
        self.user.save()
        askbot_settings.update('USE_TIME_LIMIT_TO_EDIT_COMMENT', True)
        askbot_settings.update('MINUTES_TO_EDIT_COMMENT', 10)
        old_timestamp = datetime.datetime.now() - datetime.timedelta(1)
        question = self.post_question(author = self.user, timestamp = old_timestamp)
        comment = self.user.post_comment(
                                    parent_post = question,
                                    body_text = 'blah',
                                    timestamp = old_timestamp
                                )
        self.user.assert_can_edit_comment(comment)

#def user_assert_can_post_comment(self, parent_post):
#def user_assert_can_delete_comment(self, comment = None):

#def user_assert_can_vote_for_post(
#def user_assert_can_revoke_old_vote(self, vote):

#def user_assert_can_flag_offensive(self):

#def user_assert_can_upload_file(request_user):
#def user_assert_can_post_question(self):
#def user_assert_can_post_answer(self):
#def user_assert_can_edit_post(self, post = None):
#def user_assert_can_delete_Post(self, post = None):
#def user_assert_can_close_question(self, question = None):
#def user_assert_can_retag_questions(self):

class AcceptBestAnswerPermissionAssertionTests(utils.AskbotTestCase):

    def setUp(self):
        self.create_user()
        self.create_user(username = 'other_user')
        self.question = self.post_question()

    def other_post_answer(self):
        self.answer = self.post_answer(
                                question = self.question,
                                user = self.other_user
                            )

    def user_post_answer(self):
        self.answer = self.post_answer(
                                question = self.question,
                                user = self.user
                            )

    def assert_user_can(self, user = None):
        if user is None:
            user = self.user
        user.assert_can_accept_best_answer(self.answer)

    def assert_user_cannot(self, user = None):
        if user is None:
            user = self.user
        self.assertRaises(
            exceptions.PermissionDenied,
            user.assert_can_accept_best_answer,
            answer = self.answer
        )

    def test_question_owner_can_accept_others_answer(self):
        self.other_post_answer()
        self.assert_user_can()

    def test_suspended_question_owner_cannot_accept_others_answer(self):
        self.other_post_answer()
        self.user.set_status('s')
        self.assert_user_cannot()

    def test_blocked_question_owner_cannot_accept_others_answer(self):
        self.other_post_answer()
        self.user.set_status('b')
        self.assert_user_cannot()

    def test_answer_owner_cannot_accept_answer(self):
        self.other_post_answer()
        self.assert_user_cannot(user = self.other_user)

    def test_question_and_answer_owner_cannot_accept_answer(self):
        self.user_post_answer()
        self.assert_user_cannot()

    def test_high_rep_other_user_cannot_accept_answer(self):
        self.other_post_answer()
        self.create_user(username = 'third_user')
        self.third_user.reputation = 1000000
        self.assert_user_cannot(user = self.third_user)

    def test_moderator_cannot_accept_own_answer(self):
        self.other_post_answer()
        self.other_user.set_status('m')
        self.assert_user_cannot(user = self.other_user)

    def test_moderator_cannot_accept_others_answer_today(self):
        self.other_post_answer()
        self.create_user(username = 'third_user')
        self.third_user.set_status('m')
        self.assert_user_cannot(user = self.third_user)

    def test_moderator_can_accept_others_old_answer(self):
        self.other_post_answer()
        self.answer.added_at -= datetime.timedelta(
            days = askbot_settings.MIN_DAYS_FOR_STAFF_TO_ACCEPT_ANSWER + 1
        )
        self.answer.save()
        self.create_user(username = 'third_user')
        self.third_user.set_admin_status()
        self.third_user.save()
        self.assert_user_can(user = self.third_user)

    def test_admin_cannot_accept_own_answer(self):
        self.other_post_answer()
        self.other_user.set_admin_status()
        self.other_user.save()
        self.assert_user_cannot(user = self.other_user)

    def test_admin_cannot_accept_others_answer_today(self):
        self.other_post_answer()
        self.create_user(username = 'third_user')
        self.third_user.set_admin_status()
        self.third_user.save()
        self.assert_user_cannot(user = self.third_user)

    def test_admin_can_accept_others_old_answer(self):
        self.other_post_answer()
        self.answer.added_at -= datetime.timedelta(
            days = askbot_settings.MIN_DAYS_FOR_STAFF_TO_ACCEPT_ANSWER + 1
        )
        self.answer.save()
        self.create_user(username = 'third_user')
        self.third_user.set_admin_status()
        self.third_user.save()
        self.assert_user_can(user = self.third_user)

class VotePermissionAssertionTests(PermissionAssertionTestCase):
    """Tests permission for voting
    """
    def extraSetUp(self):
        self.min_rep_up = askbot_settings.MIN_REP_TO_VOTE_UP
        self.min_rep_down = askbot_settings.MIN_REP_TO_VOTE_DOWN
        self.other_user = self.create_other_user()

    def assert_cannot_vote(self, user = None, dir = None):
        assert(dir in ('up', 'down'))

        vote_func = self.get_vote_function(
                                        user = user, 
                                        dir = dir
                                    )

        self.assertRaises(
                exceptions.PermissionDenied,
                vote_func,
                self.question,
            )
        self.assertRaises(
                exceptions.PermissionDenied,
                vote_func,
                self.answer,
            )

    def prepare_data(self, status = 'a', rep = 1):
        self.question = self.post_question()
        self.answer = self.post_answer(question = self.question)
        self.other_user.reputation = rep
        self.other_user.set_status(status)

    def bad_user_cannot_vote(self, status = 'a', rep = 1, dir = 'up'):
        """dir - vote direction up/down
        rep - reputation
        """
        self.prepare_data(status = status)

        self.assert_cannot_vote(
                        user = self.other_user,
                        dir = dir
                    )

    def get_vote_function(self, dir = None, user = None):

        def vote_func(post):
            user.assert_can_vote_for_post(post = post, direction = dir)
        
        return vote_func


    def good_user_can_vote(self, user = None, dir = 'up'):

        if user is None:
            user = self.other_user

        vote_func = self.get_vote_function(dir = dir, user = user)

        vote_func(self.question)
        vote_func(self.answer)


    def test_blocked_user_cannot_vote(self):
        self.bad_user_cannot_vote(status = 'b')

    def test_suspended_user_cannot_vote(self):
        self.bad_user_cannot_vote(status = 's')

    def test_low_rep_user_cannot_upvote(self):
        self.bad_user_cannot_vote(dir = 'up')

    def test_low_rep_user_cannot_downvote(self):
        self.bad_user_cannot_vote(dir = 'down')

    def test_high_rep_user_can_upvote(self):
        self.prepare_data(rep = self.min_rep_up)
        self.good_user_can_vote(dir = 'up')

    def test_high_rep_user_can_downvote(self):
        self.prepare_data(rep = self.min_rep_down)
        self.good_user_can_vote(dir = 'down')

    def test_low_rep_admins_can_upvote_others(self):
        self.prepare_data()
        self.other_user.set_status('m')
        self.good_user_can_vote(dir = 'up')

    def test_low_rep_admins_can_downvote_others(self):
        self.prepare_data()
        self.other_user.set_status('m')
        self.good_user_can_vote(dir = 'down')

    def test_admins_cannot_upvote_self(self):
        self.prepare_data()
        self.user.set_status('m')
        self.assert_cannot_vote(
                user = self.user,
                dir = 'up'
            )

    def test_admins_cannot_downvote_self(self):
        self.prepare_data()
        self.user.set_status('m')
        self.assert_cannot_vote(
                user = self.user,
                dir = 'down'
            )

class UploadPermissionAssertionTests(PermissionAssertionTestCase):
    """Tests permissions for file uploads
    """

    def extraSetUp(self):
        self.min_rep = askbot_settings.MIN_REP_TO_UPLOAD_FILES

    def test_suspended_user_cannot_upload(self):
        self.user.set_status('s')
        self.assertRaises(
                    exceptions.PermissionDenied,
                    self.user.assert_can_upload_file
                )

    def test_blocked_user_cannot_upload(self):
        self.user.set_status('b')
        self.assertRaises(
                    exceptions.PermissionDenied,
                    self.user.assert_can_upload_file
                )
    def test_low_rep_user_cannot_upload(self):
        self.user.reputation = self.min_rep - 1
        self.assertRaises(
                    exceptions.PermissionDenied,
                    self.user.assert_can_upload_file
                )

    def test_high_rep_user_can_upload(self):
        self.user.reputation = self.min_rep
        try:
            self.user.assert_can_upload_file()
        except exceptions.PermissionDenied:
            self.fail('high rep user must be able to upload')

    def test_low_rep_moderator_can_upload(self):
        assert(self.user.reputation < self.min_rep)
        self.user.set_status('m')
        try:
            self.user.assert_can_upload_file()
        except exceptions.PermissionDenied:
            self.fail('high rep user must be able to upload')

    def test_low_rep_administrator_can_upload(self):
        assert(self.user.reputation < self.min_rep)
        self.user.set_admin_status()
        self.user.save()
        try:
            self.user.assert_can_upload_file()
        except exceptions.PermissionDenied:
            self.fail('high rep user must be able to upload')

class ClosedForumTests(utils.AskbotTestCase):
    def setUp(self):
        self.password = '123'
        self.create_user()
        self.create_user(username = 'other_user')
        self.other_user.set_password(self.password)
        self.other_user.save()
        self.question = self.post_question()
        self.test_url = self.question.get_absolute_url()
        self.redirect_to = settings.LOGIN_URL
        self.client = Client()
        askbot_settings.ASKBOT_CLOSED_FORUM_MODE = True

    @skipIf('askbot.middleware.forum_mode.ForumModeMiddleware' \
        not in settings.MIDDLEWARE_CLASSES,
        'no ForumModeMiddleware set')
    def test_login_page_accessable(self):
        # futher see in page_load_tests.py
        response = self.client.get(reverse('user_signin'))
        self.assertEquals(response.status_code, 200)

    @skipIf('askbot.middleware.forum_mode.ForumModeMiddleware' \
        not in settings.MIDDLEWARE_CLASSES,
        'no ForumModeMiddleware set')
    def test_anonymous_access(self):
        response = self.client.get(self.test_url)
        self.assertEquals(response.status_code, 302)
        self.assertTrue(self.redirect_to in response['Location'])

    @skipIf('askbot.middleware.forum_mode.ForumModeMiddleware' \
        not in settings.MIDDLEWARE_CLASSES,
        'no ForumModeMiddleware set')
    def test_authenticated_access(self):
        self.client.login(username=self.other_user.username, password=self.password)
        response = self.client.get(self.test_url)
        self.assertEquals(response.status_code, 200)

    def tearDown(self):
        askbot_settings.ASKBOT_CLOSED_FORUM_MODE = False
