"""Tests haystack indexes and queries"""
from django.core import exceptions
from django.conf import settings
from django.contrib.auth.models import User
from askbot.tests.utils import AskbotTestCase, skipIf
from askbot import models
import datetime

class HaystackSearchTests(AskbotTestCase):
    """tests methods on User object,
    that were added for askbot
    """
    def setUp(self):
        self._old_value = getattr(settings, 'ENABLE_HAYSTACK_SEARCH', False)
        self._old_search_engine = getattr(settings, 'HAYSTACK_SEARCH_ENGINE', 'simple')
        setattr(settings, "ENABLE_HAYSTACK_SEARCH", True)
        setattr(settings, "HAYSTACK_SEARCH_ENGINE", 'simple')

        self.user = self.create_user(username='gepeto')
        self.other_user = self.create_user(username='pinocho')
        self.other_user.location = 'Managua'
        self.other_user.update_localized_profile(
                                        about="I'm made of wood, gepeto made me"
                                                )
        self.other_user.save()
        body_1 = '''Lorem turpis purus? Amet mattis eu et sociis phasellus
        montes elementum proin ut urna enim, velit, tincidunt quis ut,
        et integer mus? Nunc! Vut sed? Ac tincidunt egestas adipiscing,
        magna et pulvinar mid est urna ultricies, turpis tristique nisi,
        cum. Urna. Purus elit porttitor nisi porttitor ridiculus tincidunt
        amet duis, gepeto'''
        #from Baldy of Nome by Esther Birdsall Darling
        body_2 = ''' With unseeing eyes and dragging steps, the boy trudged along the snowy
        trail, dreading the arrival at Golconda Camp. For there was the House of
        Judgment, where all of the unfortunate events of that most unhappy day
        would be reviewed sternly, lorem'''
        self.question1 = self.post_question(
                                           user=self.user,
                                           body_text=body_1,
                                           title='Test title 1'
                                          )
        self.question2 = self.post_question(
                                           user=self.other_user,
                                           body_text=body_2,
                                           title='Test title 2, Baldy of Nome'
                                           )
        self.answer1 = self.post_answer(
                                        user=self.user,
                                        question = self.question1,
                                        body_text="This is a answer for question 1"
                                       )
        self.answer1 = self.post_answer(
                                        user=self.other_user,
                                        question = self.question2,
                                        body_text="Just a random text to fill the space"
                                       )

    def tearDown(self):
        setattr(settings, "ENABLE_HAYSTACK_SEARCH", self._old_value)
        setattr(settings, "HAYSTACK_SEARCH_ENGINE", self._old_search_engine)

    @skipIf('haystack' not in settings.INSTALLED_APPS,
        'Haystack not setup')
    def test_title_search(self):
        #title search
        title_search_qs = models.Thread.objects.get_for_query('title')
        title_search_qs_2  = models.Thread.objects.get_for_query('Nome')
        self.assertEquals(title_search_qs.count(), 2)
        self.assertEquals(title_search_qs_2.count(), 1)

    @skipIf('haystack' not in settings.INSTALLED_APPS,
        'Haystack not setup')
    def test_body_search(self):

        #bodysearch
        body_search_qs = models.Thread.objects.get_for_query('Lorem')
        self.assertEquals(body_search_qs.count(), 2)
        body_search_qs_2 = models.Thread.objects.get_for_query('steps')
        self.assertEquals(body_search_qs_2.count(), 1)

    @skipIf('haystack' not in settings.INSTALLED_APPS,
        'Haystack not setup')
    def test_user_profile_search(self):
        #must return pinocho
        user_profile_qs = models.get_users_by_text_query('wood')
        self.assertEquals(user_profile_qs.count(), 1)

        #returns both gepeto and pinocho because gepeto nickname
        #and gepeto name in pinocho's profile
        user_profile_qs = models.get_users_by_text_query('gepeto')
        self.assertEquals(user_profile_qs.count(), 2)

    @skipIf('haystack' not in settings.INSTALLED_APPS,
        'Haystack not setup')
    def test_get_django_queryset(self):
        '''makes a query that can return multiple models'''
        #gepeto is present in profile and in question
        from askbot.search.haystack.helpers import get_threads_from_query, get_users_from_query

        qs = get_users_from_query(query='gepeto')

        for instance in qs:
           self.assertTrue(isinstance(instance, User))

        qs = get_threads_from_query(query='gepeto')

        for instance in qs:
           self.assertTrue(isinstance(instance, models.Thread))
