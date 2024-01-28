import datetime

from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import fields
from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext as _
from django.utils.html import escape
from django.utils import timezone
from django.urls import reverse

from askbot import const
from askbot.models.fields import LanguageCodeField
from askbot.utils.translation import get_language


class VoteManager(models.Manager):
    def get_up_vote_count_from_user(self, user):
        if user is not None:
            return self.filter(user=user, vote=1).count()
        else:
            return 0

    def get_down_vote_count_from_user(self, user):
        if user is not None:
            return self.filter(user=user, vote=-1).count()
        else:
            return 0

    def get_votes_count_today_from_user(self, user):
        if user is not None:
            today = datetime.date.today()
            date_range = today, today + datetime.timedelta(1)
            return self.filter(user=user, voted_at__range=date_range).count()
        else:
            return 0


class Vote(models.Model):
    VOTE_UP = +1
    VOTE_DOWN = -1
    VOTE_CHOICES = (
        (VOTE_UP,   'Up'),
        (VOTE_DOWN, 'Down'),
    )
    user = models.ForeignKey('auth.User', related_name='askbot_votes', on_delete=models.CASCADE)
    voted_post = models.ForeignKey('Post', related_name='votes', on_delete=models.CASCADE)

    vote = models.SmallIntegerField(choices=VOTE_CHOICES)
    voted_at = models.DateTimeField(default=timezone.now)

    objects = VoteManager()

    class Meta:
        unique_together = ('user', 'voted_post')
        app_label = 'askbot'
        db_table = 'vote'
        verbose_name = _("vote")
        verbose_name_plural = _("votes")

    def __str__(self):
        return f'[{self.user}] voted at {self.voted_at}: {self.vote}'

    def __int__(self):
        """1 if upvote -1 if downvote"""
        return self.vote

    def is_upvote(self):
        return self.vote == self.VOTE_UP

    def is_downvote(self):
        return self.vote == self.VOTE_DOWN

    def is_opposite(self, vote_type):
        assert(vote_type in (self.VOTE_UP, self.VOTE_DOWN))
        return self.vote != vote_type

    def cancel(self):
        """cancel the vote
        while taking into account whether vote was up
        or down

        return change in score on the post
        """
        # importing locally because of circular dependency
        from askbot import auth
        score_before = self.voted_post.points
        if self.vote > 0:
            # cancel upvote
            auth.onUpVotedCanceled(self, self.voted_post, self.user)
        else:
            # cancel downvote
            auth.onDownVotedCanceled(self, self.voted_post, self.user)
        score_after = self.voted_post.points

        return score_after - score_before


class BadgeData(models.Model):
    """Awarded for notable actions performed on the site by Users."""
    slug = models.SlugField(max_length=50, unique=True)
    awarded_count = models.PositiveIntegerField(default=0)
    awarded_to = models.ManyToManyField(User, through='Award',
                                        related_name='badges')
    # use this field if badges should be sorted
    # on the badges page in some specific ordering
    # and add setting ASKBOT_BADGE_ORDERING = 'custom'
    display_order = models.PositiveIntegerField(default=0)

    def _get_meta_data(self):
        """retrieves badge metadata stored
        in a file"""
        from askbot.models import badges
        return badges.get_badge(self.slug)

    def is_enabled(self):
        return self._get_meta_data().is_enabled()

    def is_multiple(self):
        return self._get_meta_data().multiple

    def get_level(self):
        return self._get_meta_data().level

    def get_name(self):
        return self._get_meta_data().name

    def get_description(self):
        return self._get_meta_data().description

    def get_css_class(self):
        return self._get_meta_data().css_class

    def get_type_display(self):
        # TODO: rename "type" -> "level" in this model
        return self._get_meta_data().get_level_display()

    class Meta:
        app_label = 'askbot'
        ordering = ('display_order', 'slug')
        verbose_name = _("badge data")
        verbose_name_plural = _("badge data")

    def __str__(self):
        return f'{self.get_type_display()}: {self.slug}'

    def get_absolute_url(self):
        return '{}{}/'.format(reverse('badge', args=[self.id]), self.slug)


class Award(models.Model):
    """The awarding of a Badge to a User."""
    user = models.ForeignKey(User, related_name='award_user', on_delete=models.CASCADE)
    badge = models.ForeignKey(BadgeData, related_name='award_badge', on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = fields.GenericForeignKey('content_type', 'object_id')
    awarded_at = models.DateTimeField(default=timezone.now)
    notified = models.BooleanField(default=False)

    def __str__(self):
        return '[{}] is awarded a badge [{}] at {}'.format(self.user.username,
                                                        self.badge.get_name(),
                                                        self.awarded_at)
    def __lt__(self, other):
        return self.id < other.id

    class Meta:
        app_label = 'askbot'
        db_table = 'award'
        verbose_name = _("award")
        verbose_name_plural = _("awards")


class ReputeManager(models.Manager):
    def get_reputation_by_upvoted_today(self, user):
        """
        For one user in one day, he can only earn rep till certain score
        (ep. +200) by upvoted(also subtracted from upvoted canceled). This is
        because we need to prohibit gaming system by upvoting/cancel again and
        again.
        """
        if user is None:
            return 0
        else:
            today = datetime.date.today()
            tomorrow = today + datetime.timedelta(1)
            rep_types = (1, -8)
            sums = self.filter(models.Q(reputation_type__in=rep_types),
                               user=user,
                               reputed_at__range=(today, tomorrow))\
                .aggregate(models.Sum('positive'), models.Sum('negative'))
            if sums:
                pos = sums['positive__sum']
                neg = sums['negative__sum']
                if pos is None:
                    pos = 0
                if neg is None:
                    neg = 0
                return pos + neg
            else:
                return 0


class Repute(models.Model):
    """The reputation histories for user"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    # TODO: combine positive and negative to one value
    positive = models.SmallIntegerField(default=0)
    negative = models.SmallIntegerField(default=0)
    question = models.ForeignKey('Post', null=True, blank=True, on_delete=models.CASCADE)
    language_code = LanguageCodeField()
    reputed_at = models.DateTimeField(default=timezone.now)
    reputation_type = models.SmallIntegerField(choices=const.TYPE_REPUTATION)
    reputation = models.IntegerField(default=1)

    # comment that must be used if reputation_type == 10
    # assigned_by_moderator - so that reason can be displayed
    # in that case Question field will be blank
    comment = models.CharField(max_length=128, null=True)

    objects = ReputeManager()

    def __str__(self):
        return f'[{self.user.username}]\' reputation changed at {self.reputed_at}'

    class Meta:
        app_label = 'askbot'
        db_table = 'repute'
        verbose_name = _("repute")
        verbose_name_plural = _("repute")

    def save(self, *args, **kwargs):
        if self.question:
            self.language_code = self.question.language_code
        else:
            self.language_code = get_language()
        super().save(*args, **kwargs)

    def get_explanation_snippet(self):
        """returns HTML snippet with a link to related question
        or a text description for a the reason of the reputation change

        in the implementation description is returned only
        for Repute.reputation_type == 10 - "assigned by the moderator"

        part of the purpose of this method is to hide this idiosyncracy
        """
        if self.reputation_type == 10:  # TODO: hide magic number
            return _('<em>Changed by moderator. Reason:</em> %(reason)s') \
                                                    % {'reason': self.comment}
        else:  # .negative is < 0 so we add!
            delta = self.positive + self.negative
            link_title_data = {
                'points': abs(delta),
                'username': self.user.username,
                'question_title': self.question.thread.title
            }

            return '<a href="{url}">{question_title}</a>'.format(
               url=self.question.get_absolute_url(),
               question_title=escape(self.question.thread.title),
           )
