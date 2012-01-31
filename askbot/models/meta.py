import datetime
from django.db import models


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
        return '[%s] voted at %s: %s' %(self.user, self.voted_at, self.vote)

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
        score_before = self.voted_post.score
        if self.vote > 0:
            # cancel upvote
            auth.onUpVotedCanceled(self, self.voted_post, self.user)
        else:
            # cancel downvote
            auth.onDownVotedCanceled(self, self.voted_post, self.user)
        score_after = self.voted_post.score

        return score_after - score_before
