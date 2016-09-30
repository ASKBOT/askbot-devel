"""
Authorisation related functions.

This entire module will be removed some time in
the future

Many of these functions are being replaced with assertions:
User.assert_can...
"""
from django.db import transaction
from django.utils import timezone
from askbot.models import Repute
# from askbot.models import Answer
from askbot import signals
from askbot.conf import settings as askbot_settings


###########################################
## actions and reputation changes event
###########################################
@transaction.atomic
def onFlaggedItem(post, user, timestamp=None):
    if timestamp is None:
        timestamp = timezone.now()

    post.offensive_flag_count = post.offensive_flag_count + 1
    post.save()

    flagged_user = post.author

    flagged_user.receive_reputation(
        askbot_settings.REP_LOSS_FOR_RECEIVING_FLAG,
        post.language_code)
    flagged_user.save()

    question = post.thread._question_post()

    reputation = Repute(
        user=flagged_user,
        negative=askbot_settings.REP_LOSS_FOR_RECEIVING_FLAG,
        question=question,
        reputed_at=timestamp,
        reputation_type=-4,  # TODO: clean up magic number
        reputation=flagged_user.reputation)
    reputation.save()

    signals.flag_offensive.send(sender=post.__class__, instance=post,
                                mark_by=user)

    if post.post_type == 'comment':
        # do not hide or delete comments automatically yet,
        # because there is no .deleted field in the comment model
        return

    # TODO: These should be updated to work on same revisions.
    if post.offensive_flag_count == askbot_settings.MIN_FLAGS_TO_HIDE_POST:
        # TODO: strange - are we supposed to hide the post here or the name of
        # setting is incorrect?
        flagged_user.receive_reputation(
            askbot_settings.REP_LOSS_FOR_RECEIVING_THREE_FLAGS_PER_REVISION,
            post.language_code)

        flagged_user.save()

        reputation = Repute(
            user=flagged_user,
            negative=askbot_settings.REP_LOSS_FOR_RECEIVING_THREE_FLAGS_PER_REVISION,
            question=question,
            reputed_at=timestamp,
            reputation_type=-6,
            reputation=flagged_user.reputation)
        reputation.save()

    elif post.offensive_flag_count == askbot_settings.MIN_FLAGS_TO_DELETE_POST:
        flagged_user.receive_reputation(
            askbot_settings.REP_LOSS_FOR_RECEIVING_FIVE_FLAGS_PER_REVISION,
            post.language_code)

        flagged_user.save()

        reputation = Repute(
            user=flagged_user,
            negative=askbot_settings.REP_LOSS_FOR_RECEIVING_FIVE_FLAGS_PER_REVISION,
            question=question,
            reputed_at=timestamp,
            reputation_type=-7,
            reputation=flagged_user.reputation)
        reputation.save()

        post.deleted = True
        # post.deleted_at = timestamp
        # post.deleted_by = Admin
        post.save()

        signals.after_post_removed.send(sender=post.__class__, instance=post,
                                        deleted_by=user)


@transaction.atomic
def onUnFlaggedItem(post, user, timestamp=None):
    if timestamp is None:
        timestamp = timezone.now()

    post.offensive_flag_count = post.offensive_flag_count - 1
    post.save()

    flagged_user = post.author

    flagged_user.receive_reputation(
        -askbot_settings.REP_LOSS_FOR_RECEIVING_FLAG,  # negative of a negative
        post.language_code)
    flagged_user.save()

    question = post.thread._question_post()

    reputation = Repute(
        user=flagged_user,
        positive=abs(askbot_settings.REP_LOSS_FOR_RECEIVING_FLAG),
        question=question,
        reputed_at=timestamp,
        reputation_type=-4,  # TODO: clean up magic number
        reputation=flagged_user.reputation)
    reputation.save()

    signals.remove_flag_offensive.send(sender=post.__class__, instance=post,
                                       mark_by=user)

    if post.post_type == 'comment':
        # do not hide or delete comments automatically yet,
        # because there is no .deleted field in the comment model
        return

    # TODO: These should be updated to work on same revisions.
    # The post fell below HIDE treshold - unhide it.
    if post.offensive_flag_count == askbot_settings.MIN_FLAGS_TO_HIDE_POST - 1:
        # TODO: strange - are we supposed to hide the post here or the name of
        # setting is incorrect?
        flagged_user.receive_reputation(
            -askbot_settings.REP_LOSS_FOR_RECEIVING_THREE_FLAGS_PER_REVISION,
            post.language_code)

        flagged_user.save()

        reputation = Repute(
            user=flagged_user,
            positive=abs(askbot_settings.REP_LOSS_FOR_RECEIVING_THREE_FLAGS_PER_REVISION),
            question=question,
            reputed_at=timestamp,
            reputation_type=-6,
            reputation=flagged_user.reputation)
        reputation.save()
    # The post fell below DELETE treshold, undelete it
    elif post.offensive_flag_count == askbot_settings.MIN_FLAGS_TO_DELETE_POST-1:
        flagged_user.receive_reputation(
            -askbot_settings.REP_LOSS_FOR_RECEIVING_FIVE_FLAGS_PER_REVISION,
            post.language_code)

        flagged_user.save()

        reputation = Repute(
            user=flagged_user,
            positive=abs(askbot_settings.REP_LOSS_FOR_RECEIVING_FIVE_FLAGS_PER_REVISION),
            question=question,
            reputed_at=timestamp,
            reputation_type=-7,
            reputation=flagged_user.reputation)
        reputation.save()

        post.deleted = False
        post.save()

        signals.after_post_restored.send(sender=post.__class__, instance=post,
                                         restored_by=user)


@transaction.atomic
def onAnswerAccept(answer, user, timestamp=None):
    answer.thread.set_accepted_answer(
        answer=answer, actor=user, timestamp=timestamp)
    question = answer.thread._question_post()

    if answer.author != user:
        answer.author.receive_reputation(
            askbot_settings.REP_GAIN_FOR_RECEIVING_ANSWER_ACCEPTANCE,
            answer.language_code)
        answer.author.save()
        reputation = Repute(
            user=answer.author,
            positive=abs(askbot_settings.REP_GAIN_FOR_RECEIVING_ANSWER_ACCEPTANCE),
            question=question,
            reputed_at=timestamp,
            reputation_type=2,
            reputation=answer.author.reputation)
        reputation.save()

    if answer.author_id == question.author_id and user.pk == question.author_id:
        # a plug to prevent reputation gaming by posting a question
        # then answering and accepting as best all by the same person
        return

    user.receive_reputation(askbot_settings.REP_GAIN_FOR_ACCEPTING_ANSWER,
                            answer.language_code)
    user.save()
    reputation = Repute(
        user=user,
        positive=askbot_settings.REP_GAIN_FOR_ACCEPTING_ANSWER,
        question=question,
        reputed_at=timestamp,
        reputation_type=3,
        reputation=user.reputation)
    reputation.save()


@transaction.atomic
def onAnswerAcceptCanceled(answer, user, timestamp=None):
    if timestamp is None:
        timestamp = timezone.now()

    answer.endorsed = False
    answer.endorsed_by = None
    answer.endorsed_at = None
    answer.save()

    answer.thread.accepted_answer = None
    answer.thread.save()

    question = answer.thread._question_post()

    if user != answer.author:
        answer.author.receive_reputation(
            -askbot_settings.REP_GAIN_FOR_RECEIVING_ANSWER_ACCEPTANCE,
            answer.language_code)
        answer.author.save()
        reputation = Repute(
            user=answer.author,
            negative=-askbot_settings.REP_GAIN_FOR_RECEIVING_ANSWER_ACCEPTANCE,
            question=question,
            reputed_at=timestamp,
            reputation_type=-2,
            reputation=answer.author.reputation)
        reputation.save()

    if answer.author_id == question.author_id and user.pk == question.author_id:
        # a symmettric measure for the reputation gaming plug
        # as in the onAnswerAccept function
        # here it protects the user from uwanted reputation loss
        return

    user.receive_reputation(-askbot_settings.REP_GAIN_FOR_ACCEPTING_ANSWER,
                            answer.language_code)
    user.save()
    reputation = Repute(
        user=user,
        negative=-askbot_settings.REP_GAIN_FOR_ACCEPTING_ANSWER,
        question=question,
        reputed_at=timestamp,
        reputation_type=-1,
        reputation=user.reputation)
    reputation.save()


@transaction.atomic
def onUpVoted(vote, post, user, timestamp=None):
    if timestamp is None:
        timestamp = timezone.now()
    vote.save()

    if post.post_type != 'comment':
        post.vote_up_count = int(post.vote_up_count) + 1
    post.points = int(post.points) + 1
    post.save()

    if post.post_type == 'comment':
        # reputation is not affected by the comment votes
        return

    if not (post.wiki or post.is_anonymous):
        author = post.author
        todays_rep_gain = Repute.objects.get_reputation_by_upvoted_today(author)
        if todays_rep_gain < askbot_settings.MAX_REP_GAIN_PER_USER_PER_DAY:
            author.receive_reputation(
                askbot_settings.REP_GAIN_FOR_RECEIVING_UPVOTE,
                post.language_code)
            author.save()

            # TODO: this is suboptimal if post is already a question
            question = post.thread._question_post()

            reputation = Repute(
                user=author,
                positive=askbot_settings.REP_GAIN_FOR_RECEIVING_UPVOTE,
                question=question,
                reputed_at=timestamp,
                reputation_type=1,
                reputation=author.reputation)
            reputation.save()


@transaction.atomic
def onUpVotedCanceled(vote, post, user, timestamp=None):
    if timestamp is None:
        timestamp = timezone.now()
    vote.delete()

    if post.post_type != 'comment':
        post.vote_up_count = int(post.vote_up_count) - 1
        if post.vote_up_count < 0:
            post.vote_up_count = 0

    post.points = int(post.points) - 1
    post.save()

    if post.post_type == 'comment':
        # comment votes do not affect reputation
        return

    if not (post.wiki or post.is_anonymous):
        author = post.author
        author.receive_reputation(
            -askbot_settings.REP_GAIN_FOR_RECEIVING_UPVOTE,
            post.language_code)
        author.save()

        # TODO: this is suboptimal if post is already a question
        question = post.thread._question_post()

        reputation = Repute(
            user=author,
            negative=-askbot_settings.REP_GAIN_FOR_RECEIVING_UPVOTE,
            question=question,
            reputed_at=timestamp,
            reputation_type=-8,
            reputation=author.reputation)
        reputation.save()


@transaction.atomic
def onDownVoted(vote, post, user, timestamp=None):
    if timestamp is None:
        timestamp = timezone.now()
    vote.save()

    post.vote_down_count = int(post.vote_down_count) + 1
    post.points = int(post.points) - 1
    post.save()

    if not (post.wiki or post.is_anonymous):
        author = post.author
        author.receive_reputation(
            askbot_settings.REP_LOSS_FOR_RECEIVING_DOWNVOTE,
            post.language_code)
        author.save()

        # TODO: this is suboptimal if post is already a question
        question = post.thread._question_post()

        reputation = Repute(
            user=author,
            negative=abs(askbot_settings.REP_LOSS_FOR_RECEIVING_DOWNVOTE),
            question=question,
            reputed_at=timestamp,
            reputation_type=-3,
            reputation=author.reputation)
        reputation.save()

        user.receive_reputation(
            askbot_settings.REP_LOSS_FOR_DOWNVOTING,
            post.language_code)
        user.save()

        reputation = Repute(
            user=user,
            negative=askbot_settings.REP_LOSS_FOR_DOWNVOTING,
            question=question,
            reputed_at=timestamp,
            reputation_type=-5,
            reputation=user.reputation)
        reputation.save()


@transaction.atomic
def onDownVotedCanceled(vote, post, user, timestamp=None):
    if timestamp is None:
        timestamp = timezone.now()
    vote.delete()

    post.vote_down_count = int(post.vote_down_count) - 1
    if post.vote_down_count < 0:
        post.vote_down_count = 0
    post.points = post.points + 1
    post.save()

    if not (post.wiki or post.is_anonymous):
        author = post.author
        author.receive_reputation(
            -askbot_settings.REP_LOSS_FOR_RECEIVING_DOWNVOTE,
            post.language_code)
        author.save()

        # TODO: this is suboptimal if post is already a question
        question = post.thread._question_post()

        reputation = Repute(
            user=author,
            positive=abs(askbot_settings.REP_LOSS_FOR_RECEIVING_DOWNVOTE),
            question=question,
            reputed_at=timestamp,
            reputation_type=4,
            reputation=author.reputation)
        reputation.save()

        user.receive_reputation(
            -askbot_settings.REP_LOSS_FOR_DOWNVOTING,
            post.language_code)
        user.save()

        reputation = Repute(
            user=user,
            positive=abs(askbot_settings.REP_LOSS_FOR_DOWNVOTING),
            question=question,
            reputed_at=timestamp,
            reputation_type=5,
            reputation=user.reputation)
        reputation.save()
