"""This file contains data on badges that is not stored in the database.
there are no django models in this file.
This data is static, so there is no point storing it in the db.

However, the database does have model BadgeData, that contains
additional mutable data pertaining to the badges - denormalized award counts
and lists of recipients.

BadgeData django model is located in askbot/models/repute.py

Badges in this file are connected with the contents of BadgeData
via key, determined as a slugified version of badge name.

To implement a new badge, one must create a subclass of Badge,
adde it to BADGES dictionary, register with event in EVENTS_TO_BADGES
and make sure that a signal `award_badges_signal` is sent with the
corresponding event name, actor (user object), context_object and optionally
- timestamp
"""
import datetime

from django.template.defaultfilters import slugify
from django.conf import settings as django_settings
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext
from django.utils import timezone
from django.dispatch import Signal

from askbot import const
from askbot.conf import settings as askbot_settings
from askbot.utils.decorators import auto_now_timestamp
from askbot.utils.functions import format_setting_name
from askbot.utils.loading import load_module


class Badge(object):
    """base class for the badges

    badges must implement method consider_award
    which returns a boolean True if award succeds
    and False otherwise

    consider_award assumes that the function is called
    upon correct event, i.e. it is the responsibility of
    the caller to try awarding badges at appropriate times
    """
    key = 'base-badge'  # override this

    def __init__(self, name='', level=None, description=None, multiple=False):
        # key - must be an ASCII only word
        self.name = name
        self.level = level
        self.description = description
        self.multiple = multiple
        self.css_class = const.BADGE_CSS_CLASSES[self.level]

    def get_stored_data(self):
        from askbot.models.repute import BadgeData
        data, created = BadgeData.objects.get_or_create(slug=self.key)
        return data

    @property
    def awarded_count(self):
        return self.get_stored_data().awarded_count

    @property
    def awarded_to(self):
        return self.get_stored_data().awarded_to

    @property
    def award_badge(self):
        """related name from `askbot.models.Award`
        the name of this property is confusing, but for now
        left in sync with the name on the `Award` model

        the goal is that any badge recalled from this
        module would behave just like the instance of BadgeData
        and vice versa
        """
        return self.get_stored_data().award_badge

    @classmethod
    def is_enabled(cls):
        setting_name = format_setting_name(cls.key) + '_BADGE_ENABLED'
        return getattr(askbot_settings, setting_name, False)

    def get_level_display(self):
        """display name for the level of the badge"""
        return dict(const.BADGE_TYPE_CHOICES).get(self.level)

    def award(self, recipient=None, context_object=None, timestamp=None):
        """do award, the recipient was proven to deserve,
        Returns True, if awarded, or False
        """
        from askbot.models.repute import Award
        if not self.multiple:
            if recipient.badges.filter(slug=self.key).exists():
                return False
        else:
            content_type = ContentType.objects.get_for_model(context_object)
            filters = {
                'user': recipient,
                'object_id': context_object.id,
                'content_type': content_type,
                'badge__slug': self.key,
            }
            # multiple badge is not re-awarded for the same post
            if Award.objects.filter(**filters).count() != 0:
                return False

        badge = self.get_stored_data()
        award = Award(user=recipient, badge=badge, awarded_at=timestamp,
                      content_object=context_object)
        award.save()  # note: there are signals that listen to saving the Award
        return True

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        """Normally this method should be reimplemented
        in subclass, but some badges are awarded without
        checks. Those do no need to override this method

        actor - user who committed some action, context_object -
        the object related to the award situation, e.g. answer
        """
        return self.award(actor, context_object, timestamp)


class Disciplined(Badge):
    key = 'disciplined'

    def __init__(self):
        description = _(
            'Deleted own post with %(votes)s or more upvotes'
        ) % {'votes': askbot_settings.DISCIPLINED_BADGE_MIN_UPVOTES}
        super(Disciplined, self).__init__(
            name=_('Disciplined'), description=description,
            level=const.BRONZE_BADGE, multiple=True)

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        if context_object.author != actor:
            return False
        if context_object.points >= \
                askbot_settings.DISCIPLINED_BADGE_MIN_UPVOTES:
            return self.award(actor, context_object, timestamp)


class PeerPressure(Badge):
    key = 'peer-pressure'

    def __init__(self):
        description = _(
            u'Deleted own post with %(votes)s or more downvotes'
        ) % {'votes': askbot_settings.PEER_PRESSURE_BADGE_MIN_DOWNVOTES}
        super(PeerPressure, self).__init__(
            name=_('Peer Pressure'), description=description,
            level=const.BRONZE_BADGE, multiple=True)

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        if context_object.author != actor:
            return False
        if context_object.points <= \
                -1 * askbot_settings.PEER_PRESSURE_BADGE_MIN_DOWNVOTES:
            return self.award(actor, context_object, timestamp)
        return False


class Teacher(Badge):
    key = 'teacher'

    def __init__(self):
        description = _(
            'Gave an %(answer_voted_up)s at least %(votes)s times for the first time'
        ) % {
            'votes': askbot_settings.TEACHER_BADGE_MIN_UPVOTES,
            'answer_voted_up': askbot_settings.WORDS_ANSWER_VOTED_UP
        }
        super(Teacher, self).__init__(
            name=_('Teacher'), description=description,
            level=const.BRONZE_BADGE, multiple=False)

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        if context_object.post_type != 'answer':
            return False

        if context_object.points >= askbot_settings.TEACHER_BADGE_MIN_UPVOTES:
            return self.award(context_object.author, context_object, timestamp)
        return False


class FirstVote(Badge):
    """this badge is not awarded directly, but through
    Supporter and Critic, which must provide
    * key, name and description properties through __new__ call
    """
    key = 'first-vote'

    def __init__(self):
        super(FirstVote, self).__init__(
            name=self.name, description=self.description,
            level=const.BRONZE_BADGE, multiple=False)

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        if context_object.post_type not in ('question', 'answer'):
            return False
        return self.award(actor, context_object, timestamp)


class Supporter(FirstVote):
    """first upvote"""
    key = 'supporter'

    def __new__(cls):
        self = super(Supporter, cls).__new__(cls)
        self.name = _('Supporter')
        self.description = _('First upvote')
        return self


class Critic(FirstVote):
    """like supporter, but for downvote"""
    key = 'critic'

    def __new__(cls):
        self = super(Critic, cls).__new__(cls)
        self.name = _('Critic')
        self.description = _('First downvote')
        return self


class CivicDuty(Badge):
    """awarded once after a certain number of votes"""
    key = 'civic-duty'

    def __init__(self):
        min_votes = askbot_settings.CIVIC_DUTY_BADGE_MIN_VOTES
        super(CivicDuty, self).__init__(
            name=_('Civic Duty'),
            description=_('Voted %(num)s times') % {'num': min_votes},
            level=const.SILVER_BADGE, multiple=False)

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        obj = context_object
        if not (obj.is_question() or obj.is_answer() or obj.is_comment()):
            return False
        if actor.askbot_votes.count() >= askbot_settings.CIVIC_DUTY_BADGE_MIN_VOTES:
            return self.award(actor, obj, timestamp)
        return False


class SelfLearner(Badge):
    key = 'self-learner'

    def __init__(self):
        description = _('%(answered_own_question)s with at least %(num)s up votes') % {
            'num': askbot_settings.SELF_LEARNER_BADGE_MIN_UPVOTES,
            'answered_own_question': askbot_settings.WORDS_ANSWERED_OWN_QUESTION
        }
        super(SelfLearner, self).__init__(
            name=_('Self-Learner'), description=description,
            level=const.BRONZE_BADGE, multiple=True)

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        if context_object.post_type != 'answer':
            return False

        min_upvotes = askbot_settings.SELF_LEARNER_BADGE_MIN_UPVOTES
        question = context_object.thread._question_post()
        answer = context_object

        if question.author_id == answer.author_id and answer.points >= min_upvotes:
            self.award(context_object.author, context_object, timestamp)


class QualityPost(Badge):
    """Generic Badge for Nice/Good/Great Question or Answer
    this badge is not used directly but is instantiated
    via subclasses created via __new__() method definitions

    The subclass has a responsibility to specify properties:
    * min_votes - a value from live settings
    * post_type - string 'question' or 'answer'
    * key, name, description, level and multiple - as intended in the Badge
    """
    key = 'quality-post'

    def __init__(self):
        super(QualityPost, self).__init__(
            name=self.name, description=self.description,
            level=self.level, multiple=self.multiple)

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        if context_object.post_type not in ('answer', 'question'):
            return False
        if context_object.points >= self.min_votes:
            return self.award(context_object.author, context_object, timestamp)
        return False


class NiceAnswer(QualityPost):
    key = 'nice-answer'

    def __new__(cls):
        self = super(NiceAnswer, cls).__new__(cls)
        self.name = askbot_settings.WORDS_NICE_ANSWER
        self.level = const.BRONZE_BADGE
        self.multiple = True
        self.min_votes = askbot_settings.NICE_ANSWER_BADGE_MIN_UPVOTES
        self.description = _('%(answer_voted_up)s %(num)s times') % {
            'num': self.min_votes,
            'answer_voted_up': askbot_settings.WORDS_ANSWER_VOTED_UP
        }
        self.post_type = 'answer'
        return self


class GoodAnswer(QualityPost):
    key = 'good-answer'

    def __new__(cls):
        self = super(GoodAnswer, cls).__new__(cls)
        self.name = askbot_settings.WORDS_GOOD_ANSWER
        self.level = const.SILVER_BADGE
        self.multiple = True
        self.min_votes = askbot_settings.GOOD_ANSWER_BADGE_MIN_UPVOTES
        self.description = _('%(answer_voted_up)s %(num)s times') % {
            'num': self.min_votes,
            'answer_voted_up': askbot_settings.WORDS_ANSWER_VOTED_UP
        }
        self.post_type = 'answer'
        return self


class GreatAnswer(QualityPost):
    key = 'great-answer'

    def __new__(cls):
        self = super(GreatAnswer, cls).__new__(cls)
        self.name = askbot_settings.WORDS_GREAT_ANSWER
        self.level = const.GOLD_BADGE
        self.multiple = True
        self.min_votes = askbot_settings.GREAT_ANSWER_BADGE_MIN_UPVOTES
        self.description = _('%(answer_voted_up)s %(num)s times') % {
            'num': self.min_votes,
            'answer_voted_up': askbot_settings.WORDS_ANSWER_VOTED_UP
        }
        self.post_type = 'answer'
        return self


class NiceQuestion(QualityPost):
    key = 'nice-question'

    def __new__(cls):
        self = super(NiceQuestion, cls).__new__(cls)
        self.name = askbot_settings.WORDS_NICE_QUESTION
        self.level = const.BRONZE_BADGE
        self.multiple = True
        self.min_votes = askbot_settings.NICE_QUESTION_BADGE_MIN_UPVOTES
        self.description = _('%(question_voted_up)s %(num)s times') % {
            'num': self.min_votes,
            'question_voted_up': askbot_settings.WORDS_QUESTION_VOTED_UP
        }
        self.post_type = 'question'
        return self


class GoodQuestion(QualityPost):
    key = 'good-question'

    def __new__(cls):
        self = super(GoodQuestion, cls).__new__(cls)
        self.name = askbot_settings.WORDS_GOOD_QUESTION
        self.level = const.SILVER_BADGE
        self.multiple = True
        self.min_votes = askbot_settings.GOOD_QUESTION_BADGE_MIN_UPVOTES
        self.description = _('%(question_voted_up)s %(num)s times') % {
            'num': self.min_votes,
            'question_voted_up': askbot_settings.WORDS_QUESTION_VOTED_UP
        }
        self.post_type = 'question'
        return self


class GreatQuestion(QualityPost):
    key = 'great-question'

    def __new__(cls):
        self = super(GreatQuestion, cls).__new__(cls)
        self.name = askbot_settings.WORDS_GREAT_QUESTION
        self.level = const.GOLD_BADGE
        self.multiple = True
        self.min_votes = askbot_settings.GREAT_QUESTION_BADGE_MIN_UPVOTES
        self.description = _('%(question_voted_up)s %(num)s times') % {
            'num': self.min_votes,
            'question_voted_up': askbot_settings.WORDS_QUESTION_VOTED_UP
        }
        self.post_type = 'question'
        return self


class Student(QualityPost):
    key = 'student'

    def __new__(cls):
        self = super(Student, cls).__new__(cls)
        self.name = _('Student')
        self.level = const.BRONZE_BADGE
        self.multiple = False
        self.min_votes = 1
        self.description = _('%(asked_first_question)s with at least one up vote') % {
            'asked_first_question': askbot_settings.WORDS_ASKED_FIRST_QUESTION
        }
        self.post_type = 'question'
        return self


class FrequentedQuestion(Badge):
    """this badge is not awarded directly
    but must be subclassed by Popular, Notable and Famous Question
    badges via __new__() method definitions

    The subclass has a responsibility to specify properties:
    * min_views - a value from live settings
    * key, name, description and level and multiple - as intended in the Badge
    """
    key = 'frequented-question'

    def __init__(self):
        super(FrequentedQuestion, self).__init__(
            name=self.name, description=self.description,
            level=self.level, multiple=True)

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        if context_object.post_type != 'question':
            return False
        if context_object.thread.view_count >= self.min_views:
            return self.award(context_object.author, context_object, timestamp)
        return False


class PopularQuestion(FrequentedQuestion):
    key = 'popular-question'

    def __new__(cls):
        self = super(PopularQuestion, cls).__new__(cls)
        self.name = askbot_settings.WORDS_POPULAR_QUESTION
        self.level = const.BRONZE_BADGE
        self.min_views = askbot_settings.POPULAR_QUESTION_BADGE_MIN_VIEWS
        self.description = _('%(asked_a_question)s with %(views)s views') % {
            'views': self.min_views,
            'asked_a_question': askbot_settings.WORDS_ASKED_A_QUESTION
        }
        return self


class NotableQuestion(FrequentedQuestion):
    key = 'notable-question'

    def __new__(cls):
        self = super(NotableQuestion, cls).__new__(cls)
        self.name = askbot_settings.WORDS_NOTABLE_QUESTION
        self.level = const.SILVER_BADGE
        self.min_views = askbot_settings.NOTABLE_QUESTION_BADGE_MIN_VIEWS
        self.description = _('%(asked_a_question)s with %(views)s views') % {
            'views': self.min_views,
            'asked_a_question': askbot_settings.WORDS_ASKED_A_QUESTION
        }
        return self


class FamousQuestion(FrequentedQuestion):
    key = 'famous-question'

    def __new__(cls):
        self = super(FamousQuestion, cls).__new__(cls)
        self.name = askbot_settings.WORDS_FAMOUS_QUESTION
        self.level = const.GOLD_BADGE
        self.multiple = True
        self.min_views = askbot_settings.FAMOUS_QUESTION_BADGE_MIN_VIEWS
        self.description = _('%(asked_a_question)s with %(views)s views') % {
            'views': self.min_views,
            'asked_a_question': askbot_settings.WORDS_ASKED_A_QUESTION
        }
        return self


class Scholar(Badge):
    """scholar badge is awarded to the asker when
    he/she accepts an answer for the first time
    """
    key = 'scholar'

    def __init__(self):
        description = _('%(asked_a_question)s and %(accepted_an_answer)s') % {
                            'asked_a_question': askbot_settings.WORDS_ASKED_A_QUESTION,
                            'accepted_an_answer': askbot_settings.WORDS_ACCEPTED_AN_ANSWER
                        }
        super(Scholar, self).__init__(
            name=_('Scholar'), level=const.BRONZE_BADGE,
            multiple=False, description=description)

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        if context_object.post_type != 'answer':
            return False
        answer = context_object
        if answer.thread._question_post().author != actor:
            return False
        return self.award(actor, context_object, timestamp)


class VotedAcceptedAnswer(Badge):
    """superclass for Enlightened and Guru badges
    not awarded directly

    Subclasses must define __new__ function
    """
    key = 'voted-accepted-answer'

    def __init__(self):
        super(VotedAcceptedAnswer, self).__init__(
            name=self.name, level=self.level,
            multiple=self.multiple, description=self.description)

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        if context_object.post_type != 'answer':
            return None
        answer = context_object
        if answer.points >= self.min_votes and answer.endorsed:
            return self.award(answer.author, answer, timestamp)


class Enlightened(VotedAcceptedAnswer):
    key = 'enlightened'

    def __new__(cls):
        self = super(Enlightened, cls).__new__(cls)
        self.name = _('Enlightened')
        self.level = const.SILVER_BADGE
        self.multiple = False
        self.min_votes = askbot_settings.ENLIGHTENED_BADGE_MIN_UPVOTES
        descr = _('%(gave_accepted_answer)s upvoted %(num)s or more times')
        self.description = descr % {
            'num': self.min_votes,
            'gave_accepted_answer': askbot_settings.WORDS_GAVE_ACCEPTED_ANSWER
        }
        return self


class Guru(VotedAcceptedAnswer):
    key = 'guru'

    def __new__(cls):
        self = super(Guru, cls).__new__(cls)
        self.name = _('Guru')
        self.level = const.GOLD_BADGE
        self.multiple = True
        self.min_votes = askbot_settings.GURU_BADGE_MIN_UPVOTES
        descr = _('%(gave_accepted_answer)s upvoted %(num)s or more times')
        self.description = descr % {
            'num': self.min_votes,
            'gave_accepted_answer': askbot_settings.WORDS_GAVE_ACCEPTED_ANSWER
        }
        return self


class Necromancer(Badge):
    key = 'necromancer'

    def __init__(self):
        days = askbot_settings.NECROMANCER_BADGE_MIN_DELAY
        votes = askbot_settings.NECROMANCER_BADGE_MIN_UPVOTES
        description = _(
            '%(answered_a_question)s more than %(days)s days '
            'later with at least %(votes)s votes'
        ) % {
            'days': days,
            'votes': votes,
            'answered_a_question': askbot_settings.WORDS_ANSWERED_A_QUESTION
        }
        super(Necromancer, self).__init__(
            name=_('Necromancer'), level=const.SILVER_BADGE,
            description=description, multiple=True)

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        if context_object.post_type != 'answer':
            return False
        answer = context_object
        question = answer.thread._question_post()
        delta = datetime.timedelta(askbot_settings.NECROMANCER_BADGE_MIN_DELAY)
        min_score = askbot_settings.NECROMANCER_BADGE_MIN_UPVOTES
        if answer.added_at - question.added_at >= delta \
                and answer.points >= min_score:
            return self.award(answer.author, answer, timestamp)
        return False


class CitizenPatrol(Badge):
    key = 'citizen-patrol'

    def __init__(self):
        super(CitizenPatrol, self).__init__(
            name=_('Citizen Patrol'), level=const.BRONZE_BADGE,
            multiple=False, description=_('First flagged post'))


class Cleanup(Badge):
    """This badge is inactive right now.
    to make it live we need to be able to either
    detect "undo" actions or rewrite the view
    correspondingly
    """
    key = 'cleanup'

    def __init__(self):
        super(Cleanup, self).__init__(
            name=_('Cleanup'), level=const.BRONZE_BADGE,
            multiple=False, description=_('First rollback'))


class Pundit(Badge):
    """Inactive until it is possible to vote
    for comments.
    Pundit is someone who makes good comments.
    """
    key = 'pundit'

    def __init__(self):
        super(Pundit, self).__init__(
            name=_('Pundit'), level=const.SILVER_BADGE, multiple=False,
            description=_('Left 10 comments with score of 10 or more'))


class EditorTypeBadge(Badge):
    """subclassing badges are types of editors
    must provide usual parameters + min_edits
    via __new__ function
    """
    key = 'editor-type-badge'

    def __init__(self):
        super(EditorTypeBadge, self).__init__(
            name=self.name, level=self.level,
            multiple=False, description=self.description
        )

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        atypes = (
            const.TYPE_ACTIVITY_UPDATE_QUESTION,
            const.TYPE_ACTIVITY_UPDATE_ANSWER
        )
        filters = {'user': actor, 'activity_type__in': atypes}
        from askbot.models.user import Activity
        if Activity.objects.filter(**filters).count() == self.min_edits:
            return self.award(actor, context_object, timestamp)


class Editor(EditorTypeBadge):
    key = 'editor'

    def __new__(cls):
        self = super(Editor, cls).__new__(cls)
        self.name = _('Editor')
        self.level = const.BRONZE_BADGE
        self.multiple = False
        self.description = _('First edit')
        self.min_edits = 1
        return self


class AssociateEditor(EditorTypeBadge):
    key = 'associate-editor'  # legacy copycat name from stackoverflow

    def __new__(cls):
        self = super(AssociateEditor, cls).__new__(cls)
        self.name = _('Associate Editor')
        self.level = const.SILVER_BADGE
        self.multiple = False
        self.min_edits = askbot_settings.ASSOCIATE_EDITOR_BADGE_MIN_EDITS
        self.description = _('Edited %(num)s entries') % {'num': self.min_edits}
        return self


class Organizer(Badge):
    key = 'organizer'

    def __init__(self):
        super(Organizer, self).__init__(
            name=_('Organizer'), level=const.BRONZE_BADGE,
            multiple=False, description=_('First retag'))


class Autobiographer(Badge):
    key = 'autobiographer'

    def __init__(self):
        super(Autobiographer, self).__init__(
            name=_('Autobiographer'), level=const.BRONZE_BADGE,
            multiple=False, description=_('Completed all user profile fields'))

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        user = context_object
        if user.email and user.real_name and user.website \
                and user.location and user.get_localized_profile().about:
            return self.award(user, user, timestamp)
        return False


class FavoriteTypeBadge(Badge):
    """subclass must use __new__ and in addition
    must provide min_stars property for the badge
    """
    key = 'favorite-type-badge'

    def __init__(self):
        description = _(
            '%(asked_a_question)s with %(num)s followers'
        ) % {
            'num': self.min_stars,
            'asked_a_question': askbot_settings.WORDS_ASKED_A_QUESTION
        }
        super(FavoriteTypeBadge, self).__init__(
            name=self.name, level=self.level, multiple=True,
            description=description)

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        question = context_object
        # model FavoriteQuestion imported under alias of Fave
        from askbot.models.question import FavoriteQuestion as Fave  # name collision
        count = Fave.objects.filter(thread=question.thread)\
            .exclude(user=question.author)\
            .count()
        if count == self.min_stars:
            return self.award(question.author, question, timestamp)
        return False


class StellarQuestion(FavoriteTypeBadge):
    key = 'stellar-question'

    def __new__(cls):
        self = super(StellarQuestion, cls).__new__(cls)
        self.name = askbot_settings.WORDS_STELLAR_QUESTION
        self.level = const.GOLD_BADGE
        self.min_stars = askbot_settings.STELLAR_QUESTION_BADGE_MIN_STARS
        return self


class FavoriteQuestion(FavoriteTypeBadge):
    key = 'favorite-question'

    def __new__(cls):
        self = super(FavoriteQuestion, cls).__new__(cls)
        self.name = askbot_settings.WORDS_FAVORITE_QUESTION
        self.level = const.SILVER_BADGE
        self.min_stars = askbot_settings.FAVORITE_QUESTION_BADGE_MIN_STARS
        return self


class Enthusiast(Badge):
    """Awarded to a user who visits the site
    for a certain number of days in a row
    """
    key = 'enthusiast'

    def __init__(self):
        super(Enthusiast, self).__init__(
            name = _('Enthusiast'),
            level = const.SILVER_BADGE,
            multiple = False,
            description = _(
                'Visited site every day for %(num)s days in a row'
            ) % {'num': askbot_settings.ENTHUSIAST_BADGE_MIN_DAYS}
        )

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        min_days = askbot_settings.ENTHUSIAST_BADGE_MIN_DAYS
        if actor.consecutive_days_visit_count == min_days:
            return self.award(actor, context_object, timestamp)
        return False


class Commentator(Badge):
    """Commentator is a bronze badge that is
    awarded once when user posts a certain number of
    comments"""
    key = 'commentator'

    def __init__(self):
        super(Commentator, self).__init__(
            name=_('Commentator'), level=const.BRONZE_BADGE,
            multiple=False, description=_(
                'Posted %(num_comments)s comments'
            ) % {'num_comments': askbot_settings.COMMENTATOR_BADGE_MIN_COMMENTS}
        )

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        from askbot.models import Post
        num_comments = Post.objects.get_comments().filter(author=actor).count()
        if num_comments >= askbot_settings.COMMENTATOR_BADGE_MIN_COMMENTS:
            return self.award(actor, context_object, timestamp)
        return False


class Taxonomist(Badge):
    key = 'taxonomist'

    def __init__(self):
        super(Taxonomist, self).__init__(
            name=_('Taxonomist'), level=const.SILVER_BADGE,
            multiple=False, description=ungettext(
                'Created a tag used %(num)s time',
                'Created a tag used %(num)s times',
                askbot_settings.TAXONOMIST_BADGE_MIN_USE_COUNT
            ) % {'num': askbot_settings.TAXONOMIST_BADGE_MIN_USE_COUNT})

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        tag = context_object
        taxonomist_threshold = askbot_settings.TAXONOMIST_BADGE_MIN_USE_COUNT
        if tag.used_count == taxonomist_threshold:
            return self.award(tag.created_by, tag, timestamp)
        return False


class RapidResponder(Badge):
    key = 'rapid-responder'

    def __init__(self):
        description = _('Responded to question within %(max_delay)s hours') % {
            'max_delay': askbot_settings.RAPID_RESPONDER_BADGE_MAX_DELAY,
        }
        super(RapidResponder, self).__init__(
            name=_('Rapid Responder'), level=const.SILVER_BADGE,
            description=description, multiple=True)

    def consider_award(self, actor=None, context_object=None, timestamp=None):
        if context_object.post_type != 'answer':
            return False
        answer = context_object
        question = answer.thread._question_post()
        delta = datetime.timedelta(hours=askbot_settings.RAPID_RESPONDER_BADGE_MAX_DELAY)
        if answer.added_at - question.added_at <= delta:
            return self.award(answer.author, answer, timestamp)
        return False

    @classmethod
    def expire(cls, award):
        """special method to check if badge should be expired and expire it"""
        now = timezone.now()
        expire_date = award.awarded_at + datetime.timedelta(askbot_settings.RAPID_RESPONDER_BADGE_EXPIRES)
        if now > expire_date:
            award.delete()
            return True
        return False


class Expert(Badge):
    """Stub badge"""
    key = 'expert'

    def __init__(self):
        super(Expert, self).__init__(
            name=_('Expert'), level=const.SILVER_BADGE,
            multiple=False, description=_('Very active in one tag'))

ORIGINAL_DATA = """

extra badges from stackexchange
* commentator - left n comments (single)
* enthusiast, fanatic - visited site n days in a row (s)
* epic, legendary - hit daily reputation cap on n days (s)
* mortarboard - hit the daily reputation cap for the first time (s)
* populist - provided an answer that outscored an accepted answer two-fold or by n points, whichever is higher (m)
* reversal - provided an answer with +n points to a question of -m points
   (_('Yearling'), 2, _('yearling'), _('Active member for a year'), False, 0),


    (_('Generalist'), 2, _('generalist'), _('Active in many different tags'), False, 0),
    (_('Beta'), 2, _('beta'), _('Actively participated in the private beta'), False, 0),
    (_('Alpha'), 2, _('alpha'), _('Actively participated in the private alpha'), False, 0),
"""


def get_badge_keys(badges):
    """returns list of badge keys for the list,
    tuple, or set of badges"""
    return set([badge.key for badge in badges])


def get_badges_dict(e_to_b):
    badges = set()
    for event_badges in e_to_b.values():
        badges.update(set(event_badges))

    badges_dict = dict()
    for badge in badges:
        badges_dict[badge.key] = badge

    return badges_dict


def extend_badge_events(e_to_b):
    mod_path = django_settings.ASKBOT_CUSTOM_BADGES
    if mod_path:
        extra_e_to_b = load_module(mod_path)
        events = set(extra_e_to_b.keys())
        for event in events:
            if event not in e_to_b:
                raise ValueError('unkown badge event %s' % event)
            event_badges = set(e_to_b[event])
            extra_event_badges = set(extra_e_to_b[event])

            badge_keys = get_badge_keys(event_badges)
            extra_badge_keys = get_badge_keys(extra_event_badges)
            common_badge_keys = badge_keys & extra_badge_keys
            if len(common_badge_keys):
                info = ', '.join(common_badge_keys)
                raise ValueError('change key values of custom badges: %s' % info)

            event_badges.update(extra_event_badges)
            e_to_b[event] = event_badges
    return e_to_b


# events are sent as a parameter via signal award_badges_signal
# from appropriate locations in the code of askbot application
# most likely - from manipulator functions that are added to the User objects
EVENTS_TO_BADGES = {
    'accept_best_answer': (Scholar, Guru, Enlightened),
    'delete_post': (Disciplined, PeerPressure,),
    'downvote': (Critic, CivicDuty),  # no regard for question or answer for now
    'edit_answer': (Editor, AssociateEditor),
    'edit_question': (Editor, AssociateEditor),
    'flag_post': (CitizenPatrol,),
    'post_answer': (Necromancer, RapidResponder,),
    'post_comment': (Commentator,),
    'post_question': (),
    'retag_question': (Organizer,),
    'select_favorite_question': (FavoriteQuestion, StellarQuestion,),
    'site_visit': (Enthusiast,),
    'update_tag': (Taxonomist,),
    'update_user_profile': (Autobiographer,),
    'upvote_answer': (
                    Teacher, NiceAnswer, GoodAnswer,
                    GreatAnswer, Supporter, SelfLearner, CivicDuty,
                    Guru, Enlightened, Necromancer
                ),
    'upvote_question': (
                    NiceQuestion, GoodQuestion,
                    GreatQuestion, Student, Supporter, CivicDuty
                ),
    'upvote_comment': (),  # TODO - add some badges here
    'view_question': (PopularQuestion, NotableQuestion, FamousQuestion,),
    'manually_triggered': ()
}

EVENTS_TO_BADGES = extend_badge_events(EVENTS_TO_BADGES)
BADGES = get_badges_dict(EVENTS_TO_BADGES)


def get_badge(name=None):
    """Get badge object by name, if none matches the name
    raise KeyError
    """
    key = slugify(name)
    return BADGES[key]()


def init_badges():
    """Calling this function will set up badge record
    int the database for each badge enumerated in the
    `BADGES` dictionary
    """
    # TODO: maybe better to redo individual badges
    # so that get_stored_data() is called implicitly
    # from the __init__ function?
    for key in BADGES.keys():
        get_badge(key).get_stored_data()
    # remove any badges from the database
    # that are no longer in the BADGES dictionary
    from askbot.models.repute import BadgeData
    BadgeData.objects.exclude(slug__in=map(slugify, BADGES.keys())).delete()

award_badges_signal = Signal(providing_args=[
    'actor', 'event', 'context_object', 'timestamp'])
# actor - user who triggers the event
# event - string name of the event, e.g 'downvote'
# context_object - database object related to the event, e.g. question


@auto_now_timestamp
def award_badges(event=None, actor=None,
                 context_object=None, timestamp=None, **kwargs):
    """function that is called when signal `award_badges_signal` is sent
    """
    try:
        consider_badges = EVENTS_TO_BADGES[event]
    except KeyError:
        raise NotImplementedError('event "%s" is not implemented' % event)

    for badge in consider_badges:
        badge_instance = badge()
        if badge_instance.is_enabled():
            badge_instance.consider_award(actor, context_object, timestamp)

award_badges_signal.connect(award_badges)
