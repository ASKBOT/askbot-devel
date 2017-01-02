import datetime
from django.conf import settings as django_settings
from django.core.urlresolvers import reverse
from django.test.client import Client
from django.utils import timezone
from askbot.tests.utils import AskbotTestCase
from askbot.conf import settings
from askbot import models
from askbot.models.badges import award_badges_signal

class BadgeTests(AskbotTestCase):

    def setUp(self):
        self.u1 = self.create_user(username = 'user1')
        self.u2 = self.create_user(username = 'user2')
        self.u3 = self.create_user(username = 'user3')
        self.client = Client()

    def assert_have_badge(self, badge_key, recipient = None, expected_count = 1):
        """note - expected_count matches total number of
        badges within test, not the one that was awarded between the calls
        to this assertion"""
        filters = {'badge__slug': badge_key, 'user': recipient}
        count = models.Award.objects.filter(**filters).count()
        self.assertEquals(count, expected_count)

    def assert_accepted_answer_badge_works(self,
                                    badge_key = None,
                                    min_points = None,
                                    expected_count = 1,
                                    previous_count = 0,
                                    trigger = None
                                ):
        assert(trigger in ('accept_best_answer', 'upvote_answer'))
        question = self.post_question(user = self.u1)
        answer = self.post_answer(user = self.u2, question = question)
        answer.points = min_points - 1
        answer.save()

        recipient = answer.author

        if trigger == 'accept_best_answer':
            self.u1.upvote(answer)
            self.assert_have_badge(badge_key, recipient, previous_count)
            self.u1.accept_best_answer(answer)
        else:
            self.u1.accept_best_answer(answer)
            self.assert_have_badge(badge_key, recipient, previous_count)
            self.u1.upvote(answer)
        self.assert_have_badge(badge_key, recipient, expected_count)

    def assert_upvoted_answer_badge_works(self,
                                    badge_key = None,
                                    min_points = None,
                                    multiple = False
                                ):
        """test answer badge where answer author is the recipient
        where badge award is triggered by upvotes
        * min_points - minimum # of upvotes required
        * multiple - multiple award or not
        * badge_key - key on askbot.models.badges.Badge object
        """
        question = self.post_question(user = self.u1)
        answer = self.post_answer(user = self.u2, question = question)
        answer.points = min_points - 1
        answer.save()
        self.u1.upvote(answer)
        self.assert_have_badge(badge_key, recipient = self.u2)
        self.u3.upvote(answer)
        self.assert_have_badge(badge_key, recipient = self.u2, expected_count = 1)

        #post another question and check that there are no new badges
        question2 = self.post_question(user = self.u1)
        answer2 = self.post_answer(user = self.u2, question = question2)
        answer2.score = min_points - 1
        answer2.save()
        self.u1.upvote(answer2)

        if multiple == True:
            expected_count = 2
        else:
            expected_count = 1

        self.assert_have_badge(
                badge_key,
                recipient = self.u2,
                expected_count = expected_count
            )

    def assert_upvoted_question_badge_works(self,
                                    badge_key = None,
                                    min_points = None,
                                    multiple = False
                                ):
        """test question badge where question author is the recipient
        where badge award is triggered by upvotes
        * min_points - minimum # of upvotes required
        * multiple - multiple award or not
        * badge_key - key on askbot.models.badges.Badge object
        """
        question = self.post_question(user = self.u1)
        question.points = min_points - 1
        question.save()
        self.u2.upvote(question)
        self.assert_have_badge(badge_key, recipient = self.u1)
        self.u3.upvote(question)
        self.assert_have_badge(badge_key, recipient = self.u1, expected_count = 1)

        #post another question and check that there are no new badges
        question2 = self.post_question(user = self.u1)
        question2.points = min_points - 1
        question2.save()
        self.u2.upvote(question2)

        if multiple == True:
            expected_count = 2
        else:
            expected_count = 1

        self.assert_have_badge(
                        badge_key,
                        recipient = self.u1,
                        expected_count = expected_count
                    )

    def test_disciplined_badge(self):
        question = self.post_question(user = self.u1)
        question.points = settings.DISCIPLINED_BADGE_MIN_UPVOTES
        question.save()
        self.u1.delete_question(question)
        self.assert_have_badge('disciplined', recipient = self.u1)

        question2 = self.post_question(user = self.u1)
        question2.points = settings.DISCIPLINED_BADGE_MIN_UPVOTES
        question2.save()
        self.u1.delete_question(question2)
        self.assert_have_badge('disciplined', recipient = self.u1, expected_count = 2)

    def test_peer_pressure_badge(self):
        question = self.post_question(user = self.u1)
        answer = self.post_answer(user = self.u1, question = question)
        answer.points = -1*settings.PEER_PRESSURE_BADGE_MIN_DOWNVOTES
        answer.save()
        self.u1.delete_answer(answer)
        self.assert_have_badge('peer-pressure', recipient = self.u1)

    def test_teacher_badge(self):
        self.assert_upvoted_answer_badge_works(
            badge_key = 'teacher',
            min_points = settings.TEACHER_BADGE_MIN_UPVOTES,
            multiple = False
        )

    def test_nice_answer_badge(self):
        self.assert_upvoted_answer_badge_works(
            badge_key = 'nice-answer',
            min_points = settings.NICE_ANSWER_BADGE_MIN_UPVOTES,
            multiple = True
        )

    def test_nice_question_badge(self):
        self.assert_upvoted_question_badge_works(
            badge_key = 'nice-question',
            min_points = settings.NICE_QUESTION_BADGE_MIN_UPVOTES,
            multiple = True
        )

    def test_popular_question_badge(self):
        question = self.post_question(user = self.u1)
        min_views = settings.POPULAR_QUESTION_BADGE_MIN_VIEWS
        question.thread.view_count = min_views - 1
        question.thread.save()

        #patch not_a_robot_request to return True
        from askbot.utils import functions
        functions.not_a_robot_request = lambda v: True

        url = question.get_absolute_url()

        self.client.login(method='force', user_id=self.u2.id)
        self.client.get(url)
        self.assert_have_badge('popular-question', recipient=self.u1)

        self.client.login(method='force', user_id=self.u3.id)
        self.client.get(url)
        self.assert_have_badge('popular-question', recipient=self.u1, expected_count=1)

        question2 = self.post_question(user=self.u1)
        question2.thread.view_count = min_views - 1
        question2.thread.save()
        self.client.login(method='force', user_id=self.u2.id)
        self.client.get(question2.get_absolute_url())
        self.assert_have_badge('popular-question', recipient=self.u1, expected_count=2)

    def test_student_badge(self):
        question = self.post_question(user = self.u1)
        self.u2.upvote(question)
        self.assert_have_badge('student', recipient = self.u1)
        self.u3.upvote(question)
        self.assert_have_badge('student', recipient = self.u1, expected_count = 1)

        question2 = self.post_question(user = self.u1)
        self.u2.upvote(question)
        self.assert_have_badge('student', recipient = self.u1, expected_count = 1)

    def test_supporter_badge(self):
        question = self.post_question(user = self.u1)
        self.u2.upvote(question)
        self.assert_have_badge('supporter', recipient = self.u2)

        answer = self.post_answer(user = self.u1, question = question)
        self.u3.upvote(answer)
        self.assert_have_badge('supporter', recipient = self.u3)
        self.u2.upvote(answer)
        self.assert_have_badge('supporter', recipient = self.u2, expected_count = 1)

    def test_critic_badge(self):
        question = self.post_question(user = self.u1)
        self.u2.downvote(question)
        self.assert_have_badge('critic', recipient = self.u2)

        answer = self.post_answer(user = self.u1, question = question)
        self.u3.downvote(answer)
        self.assert_have_badge('critic', recipient = self.u3)
        self.u2.downvote(answer)
        self.assert_have_badge('critic', recipient = self.u2, expected_count = 1)

    def test_self_learner_badge(self):
        question = self.post_question(user = self.u1)
        answer = self.post_answer(user = self.u1, question = question)
        min_votes = settings.SELF_LEARNER_BADGE_MIN_UPVOTES
        answer.points = min_votes - 1
        answer.save()
        self.u2.upvote(answer)
        self.assert_have_badge('self-learner', recipient = self.u1)

        #copy-paste of the first question, except expect second badge
        question = self.post_question(user = self.u1)
        answer = self.post_answer(user = self.u1, question = question)
        answer.points = min_votes - 1
        answer.save()
        self.u2.upvote(answer)
        self.assert_have_badge('self-learner', recipient = self.u1, expected_count = 2)

        question = self.post_question(user = self.u2)
        answer = self.post_answer(user = self.u1, question = question)
        answer.points = min_votes - 1
        answer.save()
        self.u2.upvote(answer)
        #no badge when asker != answerer
        self.assert_have_badge(
            'self-learner',
            recipient = self.u1,
            expected_count = 2
        )

    def test_civic_duty_badge(self):
        settings.update('CIVIC_DUTY_BADGE_MIN_VOTES', 2)
        question = self.post_question(user = self.u1)
        answer = self.post_answer(user = self.u2, question = question)
        answer2 = self.post_answer(user = self.u1, question = question)
        self.u3.upvote(question)
        self.u3.downvote(answer)
        self.assert_have_badge('civic-duty', recipient = self.u3)
        self.u3.upvote(answer2)
        self.assert_have_badge('civic-duty', recipient = self.u3, expected_count = 1)
        self.u3.downvote(answer)
        self.assert_have_badge('civic-duty', recipient = self.u3, expected_count = 1)

    def test_scholar_badge(self):
        question = self.post_question(user = self.u1)
        answer = self.post_answer(user = self.u2, question = question)
        self.u1.accept_best_answer(answer)
        self.assert_have_badge('scholar', recipient = self.u1)
        question2 = self.post_question(user = self.u1)
        answer2 = self.post_answer(user = self.u2, question = question2)
        self.u1.accept_best_answer(answer2)
        self.assert_have_badge(
            'scholar',
            recipient = self.u1,
            expected_count=1
        )

    def assert_enlightened_badge_works(self, trigger):
        self.assert_accepted_answer_badge_works(
            'enlightened',
            min_points = settings.ENLIGHTENED_BADGE_MIN_UPVOTES,
            expected_count = 1,
            trigger = trigger
        )
        self.assert_accepted_answer_badge_works(
            'enlightened',
            min_points = settings.ENLIGHTENED_BADGE_MIN_UPVOTES,
            expected_count = 1,
            previous_count = 1,
            trigger = trigger
        )

    def assert_guru_badge_works(self, trigger):
        self.assert_accepted_answer_badge_works(
            'guru',
            min_points = settings.GURU_BADGE_MIN_UPVOTES,
            expected_count = 1,
            trigger = trigger
        )
        self.assert_accepted_answer_badge_works(
            'guru',
            min_points = settings.GURU_BADGE_MIN_UPVOTES,
            previous_count = 1,
            expected_count = 2,
            trigger = trigger
        )

    def test_enlightened_badge1(self):
        self.assert_enlightened_badge_works('upvote_answer')

    def test_enlightened_badge2(self):
        self.assert_enlightened_badge_works('accept_best_answer')

    def test_guru_badge1(self):
        self.assert_guru_badge_works('upvote_answer')

    def test_guru_badge2(self):
        self.assert_guru_badge_works('accept_best_answer')

    def test_necromancer_badge(self):
        question = self.post_question(user = self.u1)
        now = timezone.now()
        delta = datetime.timedelta(settings.NECROMANCER_BADGE_MIN_DELAY + 1)
        future = now + delta
        answer = self.post_answer(
                        user = self.u2,
                        question = question,
                        timestamp = future
                    )
        answer.points = settings.NECROMANCER_BADGE_MIN_UPVOTES - 1
        answer.save()
        self.assert_have_badge('necromancer', self.u2, expected_count = 0)
        self.u1.upvote(answer)
        self.assert_have_badge('necromancer', self.u2, expected_count = 1)

    def test_citizen_patrol_question(self):
        self.u2.set_status('m')
        question = self.post_question(user = self.u1)
        self.u2.flag_post(question)
        self.assert_have_badge('citizen-patrol', self.u2)
        question = self.post_question(user = self.u1)
        self.u2.flag_post(question)
        self.assert_have_badge('citizen-patrol', self.u2, 1)

    def test_citizen_patrol_answer(self):
        self.u2.set_status('m')
        question = self.post_question(user = self.u1)
        answer = self.post_answer(user = self.u1, question = question)
        self.u2.flag_post(answer)
        self.assert_have_badge('citizen-patrol', self.u2)
        question = self.post_question(user = self.u1)
        answer = self.post_answer(user = self.u1, question = question)
        self.u2.flag_post(answer)
        self.assert_have_badge('citizen-patrol', self.u2, 1)

    def test_editor_badge_question(self):
        self.u2.set_status('m')
        question = self.post_question(user = self.u1)
        self.u2.edit_question(
            question = question,
            title = 'hahaha',
            body_text = 'heheeh',
            revision_comment = 'ihihih'
        )
        self.assert_have_badge('editor', self.u2, 1)
        #double check that its not multiple
        question = self.post_question(user = self.u1)
        self.u2.edit_question(
            question = question,
            title = 'hahaha',
            body_text = 'heheeh',
            revision_comment = 'ihihih'
        )
        self.assert_have_badge('editor', self.u2, 1)

    def test_editor_badge_answer(self):
        self.u2.set_status('m')
        question = self.post_question(user = self.u1)
        answer = self.post_answer(user = self.u1, question = question)
        self.u2.edit_answer(answer = answer, body_text = 'hahaha')
        self.assert_have_badge('editor', self.u2, 1)
        #double check that its not multiple
        question = self.post_question(user = self.u1)
        answer = self.post_answer(user = self.u1, question = question)
        self.u2.edit_answer(answer = answer, body_text = 'hahaha')
        self.assert_have_badge('editor', self.u2, 1)

    def test_associate_editor_badge(self):
        self.u2.set_status('m')
        question = self.post_question(user = self.u1)
        settings.update('ASSOCIATE_EDITOR_BADGE_MIN_EDITS', 2)
        self.u2.edit_question(
            question = question,
            title = 'hahaha',
            body_text = 'sdgsdjghsldkfshd',
            revision_comment = 'sdgdfgsgfs'
        )
        self.assert_have_badge('associate-editor', self.u2, 0)
        self.u2.edit_question(
            question = question,
            title = 'hahaha',
            body_text = 'sdgsdjghsldkfshd',
            revision_comment = 'sdgdfgsgfs'
        )
        self.assert_have_badge('associate-editor', self.u2, 1)
        self.u2.edit_question(
            question = question,
            title = 'hahaha',
            body_text = 'sdgsdjghsldkfshd',
            revision_comment = 'sdgdfgsgfs'
        )
        self.assert_have_badge('associate-editor', self.u2, 1)

    def test_organizer_badge(self):
        question = self.post_question(user = self.u1)
        self.u1.retag_question(question = question, tags = 'blah boom')
        self.assert_have_badge('organizer', self.u1, 1)
        self.u1.retag_question(question = question, tags = 'blah pooh')
        self.assert_have_badge('organizer', self.u1, 1)

    def test_autobiographer_badge(self):
        self.u1.real_name = 'blah'
        self.u1.website = 'cnn.com'
        self.u1.location = 'irvine'
        self.u1.save()
        self.u1.update_localized_profile(about='blabla bla')
        award_badges_signal.send(None,
            event = 'update_user_profile',
            actor = self.u1,
            context_object = self.u1
        )
        self.assert_have_badge('autobiographer', self.u1, 1)
        award_badges_signal.send(None,
            event = 'update_user_profile',
            actor = self.u1,
            context_object = self.u1
        )
        self.assert_have_badge('autobiographer', self.u1, 1)

    def test_stellar_badge1(self):
        question = self.post_question(user = self.u1)
        settings.update('STELLAR_QUESTION_BADGE_MIN_STARS', 2)
        self.u2.toggle_favorite_question(question)
        self.assert_have_badge('stellar-question', self.u1, 0)
        self.u3.toggle_favorite_question(question)
        self.assert_have_badge('stellar-question', self.u1, 1)

    def test_stellar_badge2(self):
        question = self.post_question(user = self.u1)
        settings.update('STELLAR_QUESTION_BADGE_MIN_STARS', 2)
        self.u2.toggle_favorite_question(question)
        self.assert_have_badge('stellar-question', self.u1, 0)
        self.u1.toggle_favorite_question(question)
        """no gaming"""
        self.assert_have_badge('stellar-question', self.u1, 0)

    def test_stellar_badge3(self):
        question = self.post_question(user = self.u1)
        settings.update('STELLAR_QUESTION_BADGE_MIN_STARS', 2)
        self.u2.toggle_favorite_question(question)
        self.assert_have_badge('stellar-question', self.u1, 0)
        self.u3.toggle_favorite_question(question)
        #award now
        self.assert_have_badge('stellar-question', self.u1, 1)
        self.u3.toggle_favorite_question(question)
        #dont take back
        self.assert_have_badge('stellar-question', self.u1, 1)
        self.u3.toggle_favorite_question(question)
        #dont reaward
        self.assert_have_badge('stellar-question', self.u1, 1)

    def test_commentator_badge(self):
        question = self.post_question(user = self.u1)
        min_comments = settings.COMMENTATOR_BADGE_MIN_COMMENTS
        for i in xrange(min_comments - 1):
            self.post_comment(user = self.u1, parent_post = question)

        self.assert_have_badge('commentator', self.u1, 0)
        self.post_comment(user = self.u1, parent_post = question)
        self.assert_have_badge('commentator', self.u1, 1)
        self.post_comment(user = self.u1, parent_post = question)
        self.assert_have_badge('commentator', self.u1, 1)

    def test_taxonomist_badge(self):
        self.post_question(user = self.u1, tags = 'test')
        min_use = settings.TAXONOMIST_BADGE_MIN_USE_COUNT
        for i in xrange(min_use - 2):
            self.post_question(user = self.u2, tags = 'test')
        self.assert_have_badge('taxonomist', self.u1, 0)
        self.post_question(user = self.u2, tags = 'test')
        self.assert_have_badge('taxonomist', self.u1, 1)

    def test_enthusiast_badge(self):
        yesterday = timezone.now() - datetime.timedelta(1)
        self.u1.last_seen = yesterday
        prev_visit_count = settings.ENTHUSIAST_BADGE_MIN_DAYS - 1
        self.u1.consecutive_days_visit_count = prev_visit_count
        self.u1.save()
        self.assert_have_badge('enthusiast', self.u1, 0)
        self.client.login(method = 'force', user_id = self.u1.id)
        self.client.get(reverse('questions'))
        self.assert_have_badge('enthusiast', self.u1, 1)
