import datetime
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext as _
from django.utils.html import escape
from askbot import const
from django.core.urlresolvers import reverse

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
            return self.filter(user=user, voted_at__range=(today, today + datetime.timedelta(1))).count()
        else:
            return 0


class Vote(models.Model):
    VOTE_UP = +1
    VOTE_DOWN = -1
    VOTE_CHOICES = (
        (VOTE_UP,   u'Up'),
        (VOTE_DOWN, u'Down'),
    )
    user = models.ForeignKey('auth.User', related_name='votes')
    voted_post = models.ForeignKey('Post', related_name='votes')

    vote           = models.SmallIntegerField(choices=VOTE_CHOICES)
    voted_at       = models.DateTimeField(default=datetime.datetime.now)

    objects = VoteManager()

    class Meta:
        unique_together = ('user', 'voted_post')
        app_label = 'askbot'
        db_table = u'vote'

    def __unicode__(self):
        return u'[%s] voted at %s: %s' %(self.user, self.voted_at, self.vote)

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
        #importing locally because of circular dependency
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
    awarded_to = models.ManyToManyField(
                    User, through='Award', related_name='badges'
                )
    #use this field if badges should be sorted
    #on the badges page in some specific ordering
    #and add setting ASKBOT_BADGE_ORDERING = 'custom'
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
        #todo - rename "type" -> "level" in this model
        return self._get_meta_data().get_level_display()

    class Meta:
        app_label = 'askbot'
        ordering = ('display_order', 'slug')

    def __unicode__(self):
        return u'%s: %s' % (self.get_type_display(), self.slug)

    def get_absolute_url(self):
        return '%s%s/' % (reverse('badge', args=[self.id]), self.slug)

class Award(models.Model):
    """The awarding of a Badge to a User."""
    user       = models.ForeignKey(User, related_name='award_user')
    badge      = models.ForeignKey(BadgeData, related_name='award_badge')
    content_type   = models.ForeignKey(ContentType)
    object_id      = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')
    awarded_at = models.DateTimeField(default=datetime.datetime.now)
    notified   = models.BooleanField(default=False)

    def __unicode__(self):
        return u'[%s] is awarded a badge [%s] at %s' % (self.user.username, self.badge.get_name(), self.awarded_at)

    class Meta:
        app_label = 'askbot'
        db_table = u'award'

class ReputeManager(models.Manager):
    def get_reputation_by_upvoted_today(self, user):
        """
        For one user in one day, he can only earn rep till certain score (ep. +200)
        by upvoted(also subtracted from upvoted canceled). This is because we need
        to prohibit gaming system by upvoting/cancel again and again.
        """
        if user is None:
            return 0
        else:
            today = datetime.date.today()
            tomorrow = today + datetime.timedelta(1)
            rep_types = (1,-8)
            sums = self.filter(models.Q(reputation_type__in=rep_types),
                                user=user,
                                reputed_at__range=(today, tomorrow),
                      ).aggregate(models.Sum('positive'), models.Sum('negative'))
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
    user     = models.ForeignKey(User)
    #todo: combine positive and negative to one value
    positive = models.SmallIntegerField(default=0)
    negative = models.SmallIntegerField(default=0)
    question = models.ForeignKey('Post', null=True, blank=True)
    reputed_at = models.DateTimeField(default=datetime.datetime.now)
    reputation_type = models.SmallIntegerField(choices=const.TYPE_REPUTATION)
    reputation = models.IntegerField(default=1)

    #comment that must be used if reputation_type == 10
    #assigned_by_moderator - so that reason can be displayed
    #in that case Question field will be blank
    comment = models.CharField(max_length=128, null=True)

    objects = ReputeManager()

    def __unicode__(self):
        return u'[%s]\' reputation changed at %s' % (self.user.username, self.reputed_at)

    class Meta:
        app_label = 'askbot'
        db_table = u'repute'

    def get_explanation_snippet(self):
        """returns HTML snippet with a link to related question
        or a text description for a the reason of the reputation change

        in the implementation description is returned only
        for Repute.reputation_type == 10 - "assigned by the moderator"

        part of the purpose of this method is to hide this idiosyncracy
        """
        if self.reputation_type == 10:#todo: hide magic number
            return  _('<em>Changed by moderator. Reason:</em> %(reason)s') \
                                                    % {'reason':self.comment}
        else:
            delta = self.positive + self.negative#.negative is < 0 so we add!
            link_title_data = {
                                'points': abs(delta),
                                'username': self.user.username,
                                'question_title': self.question.thread.title
                            }

            return '<a href="%(url)s">%(question_title)s</a>' \
                            % {
                               'url': self.question.get_absolute_url(),
                               'question_title': escape(self.question.thread.title),
                            }
