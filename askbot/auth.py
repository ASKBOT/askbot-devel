"""
Authorisation related functions.

This entire module will be removed some time in
the future

Many of these functions are being replaced with assertions:
User.assert_can...
"""
import datetime
from django.db import transaction
from askbot.models import Repute
from askbot.models import Answer
from askbot.models import signals
from askbot.conf import settings as askbot_settings

###########################################
## actions and reputation changes event
###########################################
@transaction.commit_on_success
def onFlaggedItem(post, user, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.now()

    post.offensive_flag_count = post.offensive_flag_count + 1
    post.save()

    if post.post_type == 'comment':#todo: fix this
        flagged_user = post.user
    else:
        flagged_user = post.author

    flagged_user.receive_reputation(
        askbot_settings.REP_LOSS_FOR_RECEIVING_FLAG
    )
    flagged_user.save()

    question = post.get_origin_post()

    reputation = Repute(
                    user=flagged_user,
                    negative=askbot_settings.REP_LOSS_FOR_RECEIVING_FLAG,
                    question=question,
                    reputed_at=timestamp,
                    reputation_type=-4,#todo: clean up magic number
                    reputation=flagged_user.reputation
                )
    reputation.save()

    signals.flag_offensive.send(
        sender=post.__class__,
        instance=post,
        mark_by=user
    )

    if post.post_type == 'comment':
        #do not hide or delete comments automatically yet,
        #because there is no .deleted field in the comment model
        return

    #todo: These should be updated to work on same revisions.
    if post.offensive_flag_count ==  askbot_settings.MIN_FLAGS_TO_HIDE_POST:
        #todo: strange - are we supposed to hide the post here or the name of
        #setting is incorrect?
        flagged_user.receive_reputation(
            askbot_settings.REP_LOSS_FOR_RECEIVING_THREE_FLAGS_PER_REVISION
        )

        flagged_user.save()

        reputation = Repute(
            user=flagged_user,
            negative=\
                askbot_settings.REP_LOSS_FOR_RECEIVING_THREE_FLAGS_PER_REVISION,
            question=question,
            reputed_at=timestamp,
            reputation_type=-6,
            reputation=flagged_user.reputation
        )
        reputation.save()

    elif post.offensive_flag_count == askbot_settings.MIN_FLAGS_TO_DELETE_POST:
        flagged_user.receive_reputation(
            askbot_settings.REP_LOSS_FOR_RECEIVING_FIVE_FLAGS_PER_REVISION
        )

        flagged_user.save()

        reputation = Repute(
            user=flagged_user,
            negative=\
                askbot_settings.REP_LOSS_FOR_RECEIVING_FIVE_FLAGS_PER_REVISION,
            question=question,
            reputed_at=timestamp,
            reputation_type=-7,
            reputation=flagged_user.reputation
        )
        reputation.save()

        post.deleted = True
        #post.deleted_at = timestamp
        #post.deleted_by = Admin
        post.save()


@transaction.commit_on_success
def onUnFlaggedItem(post, user, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.now()

    post.offensive_flag_count = post.offensive_flag_count - 1
    post.save()

    if post.post_type == 'comment':#todo: fix this
        flagged_user = post.user
    else:
        flagged_user = post.author

    flagged_user.receive_reputation(
        - askbot_settings.REP_LOSS_FOR_RECEIVING_FLAG
    )
    flagged_user.save()

    question = post.get_origin_post()

    reputation = Repute(
                    user=flagged_user,
                    positive=askbot_settings.REP_LOSS_FOR_RECEIVING_FLAG,
                    question=question,
                    reputed_at=timestamp,
                    reputation_type=-4,#todo: clean up magic number
                    reputation=flagged_user.reputation
                )
    reputation.save()

    signals.remove_flag_offensive.send(
        sender=post.__class__,
        instance=post,
        mark_by=user
    )

    if post.post_type == 'comment':
        #do not hide or delete comments automatically yet,
        #because there is no .deleted field in the comment model
        return

    #todo: These should be updated to work on same revisions.
    # The post fell below HIDE treshold - unhide it.
    if post.offensive_flag_count ==  askbot_settings.MIN_FLAGS_TO_HIDE_POST - 1:
        #todo: strange - are we supposed to hide the post here or the name of
        #setting is incorrect?
        flagged_user.receive_reputation(
            - askbot_settings.REP_LOSS_FOR_RECEIVING_THREE_FLAGS_PER_REVISION
        )

        flagged_user.save()

        reputation = Repute(
            user=flagged_user,
            positive=\
                askbot_settings.REP_LOSS_FOR_RECEIVING_THREE_FLAGS_PER_REVISION,
            question=question,
            reputed_at=timestamp,
            reputation_type=-6,
            reputation=flagged_user.reputation
        )
        reputation.save()
    # The post fell below DELETE treshold, undelete it
    elif post.offensive_flag_count == askbot_settings.MIN_FLAGS_TO_DELETE_POST-1 :
        flagged_user.receive_reputation(
            - askbot_settings.REP_LOSS_FOR_RECEIVING_FIVE_FLAGS_PER_REVISION
        )

        flagged_user.save()

        reputation = Repute(
            user=flagged_user,
            positive =\
                askbot_settings.REP_LOSS_FOR_RECEIVING_FIVE_FLAGS_PER_REVISION,
            question=question,
            reputed_at=timestamp,
            reputation_type=-7,
            reputation=flagged_user.reputation
        )
        reputation.save()

        post.deleted = False
        post.save()

@transaction.commit_on_success
def onAnswerAccept(answer, user, timestamp=None):
    answer.accepted = True
    answer.accepted_at = timestamp
    answer.question.answer_accepted = True
    answer.save()
    answer.question.save()
    if answer.author != user:
        answer.author.receive_reputation(
            askbot_settings.REP_GAIN_FOR_RECEIVING_ANSWER_ACCEPTANCE
        )
        answer.author.save()
        reputation = Repute(user=answer.author,
                   positive=askbot_settings.REP_GAIN_FOR_RECEIVING_ANSWER_ACCEPTANCE,
                   question=answer.question,
                   reputed_at=timestamp,
                   reputation_type=2,
                   reputation=answer.author.reputation)
        reputation.save()

    user.receive_reputation(askbot_settings.REP_GAIN_FOR_ACCEPTING_ANSWER)
    user.save()
    reputation = Repute(user=user,
               positive=askbot_settings.REP_GAIN_FOR_ACCEPTING_ANSWER,
               question=answer.question,
               reputed_at=timestamp,
               reputation_type=3,
               reputation=user.reputation)
    reputation.save()

@transaction.commit_on_success
def onAnswerAcceptCanceled(answer, user, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.now()
    answer.accepted = False
    answer.accepted_at = None
    answer.question.answer_accepted = False
    answer.save()
    answer.question.save()

    answer.author.receive_reputation(
        askbot_settings.REP_LOSS_FOR_RECEIVING_CANCELATION_OF_ANSWER_ACCEPTANCE
    )
    answer.author.save()
    reputation = Repute(
        user=answer.author,
        negative=\
         askbot_settings.REP_LOSS_FOR_RECEIVING_CANCELATION_OF_ANSWER_ACCEPTANCE,
        question=answer.question,
        reputed_at=timestamp,
        reputation_type=-2,
        reputation=answer.author.reputation
    )
    reputation.save()

    user.receive_reputation(
        askbot_settings.REP_LOSS_FOR_CANCELING_ANSWER_ACCEPTANCE
    )
    user.save()
    reputation = Repute(user=user,
               negative=askbot_settings.REP_LOSS_FOR_CANCELING_ANSWER_ACCEPTANCE,
               question=answer.question,
               reputed_at=timestamp,
               reputation_type=-1,
               reputation=user.reputation)
    reputation.save()

@transaction.commit_on_success
def onUpVoted(vote, post, user, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.now()
    vote.save()

    if post.post_type != 'comment':
        post.vote_up_count = int(post.vote_up_count) + 1
    post.score = int(post.score) + 1
    post.save()

    if post.post_type == 'comment':
        #reputation is not affected by the comment votes
        return

    if not (post.wiki or post.is_anonymous):
        author = post.author
        todays_rep_gain = Repute.objects.get_reputation_by_upvoted_today(author)
        if todays_rep_gain <  askbot_settings.MAX_REP_GAIN_PER_USER_PER_DAY:
            author.receive_reputation(
                askbot_settings.REP_GAIN_FOR_RECEIVING_UPVOTE
            )
            author.save()

            question = post
            if isinstance(post, Answer):
                question = post.question

            reputation = Repute(user=author,
                       positive=askbot_settings.REP_GAIN_FOR_RECEIVING_UPVOTE,
                       question=question,
                       reputed_at=timestamp,
                       reputation_type=1,
                       reputation=author.reputation)
            reputation.save()

@transaction.commit_on_success
def onUpVotedCanceled(vote, post, user, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.now()
    vote.delete()

    if post.post_type != 'comment':
        post.vote_up_count = int(post.vote_up_count) - 1
        if post.vote_up_count < 0:
            post.vote_up_count  = 0

    post.score = int(post.score) - 1
    post.save()

    if post.post_type == 'comment':
        #comment votes do not affect reputation
        return

    if not (post.wiki or post.is_anonymous):
        author = post.author
        author.receive_reputation(
            askbot_settings.REP_LOSS_FOR_RECEIVING_UPVOTE_CANCELATION
        )
        author.save()

        question = post
        if isinstance(post, Answer):
            question = post.question

        reputation = Repute(
            user=author,
            negative=askbot_settings.REP_LOSS_FOR_RECEIVING_UPVOTE_CANCELATION,
            question=question,
            reputed_at=timestamp,
            reputation_type=-8,
            reputation=author.reputation
        )
        reputation.save()

@transaction.commit_on_success
def onDownVoted(vote, post, user, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.now()
    vote.save()

    post.vote_down_count = int(post.vote_down_count) + 1
    post.score = int(post.score) - 1
    post.save()

    if not (post.wiki or post.is_anonymous):
        author = post.author
        author.receive_reputation(askbot_settings.REP_LOSS_FOR_DOWNVOTING)
        author.save()

        question = post
        if isinstance(post, Answer):
            question = post.question

        reputation = Repute(user=author,
                   negative=askbot_settings.REP_LOSS_FOR_DOWNVOTING,
                   question=question,
                   reputed_at=timestamp,
                   reputation_type=-3,
                   reputation=author.reputation)
        reputation.save()

        user.receive_reputation(
            askbot_settings.REP_LOSS_FOR_RECEIVING_DOWNVOTE
        )
        user.save()

        reputation = Repute(user=user,
                   negative=askbot_settings.REP_LOSS_FOR_RECEIVING_DOWNVOTE,
                   question=question,
                   reputed_at=timestamp,
                   reputation_type=-5,
                   reputation=user.reputation)
        reputation.save()

@transaction.commit_on_success
def onDownVotedCanceled(vote, post, user, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.now()
    vote.delete()

    post.vote_down_count = int(post.vote_down_count) - 1
    if post.vote_down_count < 0:
        post.vote_down_count  = 0
    post.score = post.score + 1
    post.save()

    if not (post.wiki or post.is_anonymous):
        author = post.author
        author.receive_reputation(
            askbot_settings.REP_GAIN_FOR_RECEIVING_DOWNVOTE_CANCELATION
        )
        author.save()

        question = post
        if isinstance(post, Answer):
            question = post.question

        reputation = Repute(user=author,
                positive=\
                    askbot_settings.REP_GAIN_FOR_RECEIVING_DOWNVOTE_CANCELATION,
                question=question,
                reputed_at=timestamp,
                reputation_type=4,
                reputation=author.reputation
            )
        reputation.save()

        user.receive_reputation(askbot_settings.REP_GAIN_FOR_CANCELING_DOWNVOTE)
        user.save()

        reputation = Repute(user=user,
                   positive=askbot_settings.REP_GAIN_FOR_CANCELING_DOWNVOTE,
                   question=question,
                   reputed_at=timestamp,
                   reputation_type=5,
                   reputation=user.reputation)
        reputation.save()
