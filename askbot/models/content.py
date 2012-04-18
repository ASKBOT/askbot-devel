import datetime
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.core import urlresolvers
from django.db import models
from django.utils import html as html_utils
from django.utils.datastructures import SortedDict
from django.utils.translation import ugettext as _
from django.utils.http import urlquote as django_urlquote
from django.core import exceptions as django_exceptions

from askbot.utils.slug import slugify
from askbot import const
from askbot.models.meta import Comment, Vote
from askbot.models.user import EmailFeedSetting
from askbot.models.tag import Tag, MarkedTag, tags_match_some_wildcard
from askbot.models.post import PostRevision
from askbot.models.base import parse_post_text, parse_and_save_post
from askbot.conf import settings as askbot_settings
from askbot import exceptions

class Content(models.Model):
    """
        Base class for Question and Answer
    """
    author = models.ForeignKey(User, related_name='%(class)ss')
    added_at = models.DateTimeField(default=datetime.datetime.now)

    deleted     = models.BooleanField(default=False)
    deleted_at  = models.DateTimeField(null=True, blank=True)
    deleted_by  = models.ForeignKey(User, null=True, blank=True, related_name='deleted_%(class)ss')

    wiki = models.BooleanField(default=False)
    wikified_at = models.DateTimeField(null=True, blank=True)

    locked = models.BooleanField(default=False)
    locked_by = models.ForeignKey(User, null=True, blank=True, related_name='locked_%(class)ss')
    locked_at = models.DateTimeField(null=True, blank=True)

    score = models.IntegerField(default=0)
    vote_up_count = models.IntegerField(default=0)
    vote_down_count = models.IntegerField(default=0)

    comment_count = models.PositiveIntegerField(default=0)
    offensive_flag_count = models.SmallIntegerField(default=0)

    last_edited_at = models.DateTimeField(null=True, blank=True)
    last_edited_by = models.ForeignKey(User, null=True, blank=True, related_name='last_edited_%(class)ss')

    html = models.TextField(null=True)#html rendition of the latest revision
    text = models.TextField(null=True)#denormalized copy of latest revision
    comments = generic.GenericRelation(Comment)
    votes = generic.GenericRelation(Vote)

    _use_markdown = True
    _escape_html = False #markdow does the escaping
    _urlize = False

    class Meta:
        abstract = True
        app_label = 'askbot'

    parse = parse_post_text
    parse_and_save = parse_and_save_post

    def __unicode__(self):
        if self.is_question():
            return self.title
        elif self.is_answer():
            return self.html
        raise NotImplementedError

    def get_absolute_url(self, no_slug = False):
        if self.is_answer():
            return u'%(base)s%(slug)s?answer=%(id)d#answer-container-%(id)d' % \
                    {
                        'base': urlresolvers.reverse('question', args=[self.question.id]),
                        'slug': django_urlquote(slugify(self.question.title)),
                        'id': self.id
                    }
        elif self.is_question():
            url = urlresolvers.reverse('question', args=[self.id])
            if no_slug == True:
                return url
            else:
                return url + django_urlquote(self.slug)
        raise NotImplementedError


    def is_answer(self):
        return self.post_type == 'answer'

    def is_question(self):
        return self.post_type == 'question'

    def save(self, *args, **kwargs):
        models.Model.save(self, *args, **kwargs) # TODO: figure out how to use super() here
        if self.is_answer() and 'postgres' in settings.DATABASE_ENGINE:
            #hit the database to trigger update of full text search vector
            self.question.save()


    def get_comments(self, visitor = None):
        """returns comments for a post, annotated with
        ``upvoted_by_user`` parameter, if visitor is logged in
        otherwise, returns query set for all comments to a given post
        """
        if visitor.is_anonymous():
            return self.comments.all().order_by('id')
        else:
            comment_content_type = ContentType.objects.get_for_model(Comment)
            #a fancy query to annotate comments with the visitor votes
            comments = self.comments.extra(
                select = SortedDict([
                            (
                                'upvoted_by_user',
                                'SELECT COUNT(*) from vote, comment '
                                'WHERE vote.user_id = %s AND '
                                'vote.content_type_id = %s AND '
                                'vote.object_id = comment.id',
                            )
                        ]),
                select_params = (visitor.id, comment_content_type.id)
            ).order_by('id')
            return comments

    #todo: maybe remove this wnen post models are unified
    def get_text(self):
        return self.text

    def get_snippet(self):
        """returns an abbreviated snippet of the content
        """
        return html_utils.strip_tags(self.html)[:120] + ' ...'

    def add_comment(self, comment=None, user=None, added_at=None, ip_addr=None):
        if added_at is None:
            added_at = datetime.datetime.now()
        if None in (comment ,user):
            raise Exception('arguments comment and user are required')

        #Comment = models.get_model('askbot','Comment')#todo: forum hardcoded
        comment = Comment(
                            content_object=self, 
                            comment=comment, 
                            user=user, 
                            added_at=added_at,
                            ip_addr = ip_addr,
                        )
        comment.parse_and_save(author = user)
        self.comment_count = self.comment_count + 1
        self.save()

        #tried to add this to bump updated question
        #in most active list, but it did not work
        #becase delayed email updates would be triggered
        #for cases where user did not subscribe for them
        #
        #need to redo the delayed alert sender
        #
        #origin_post = self.get_origin_post()
        #if origin_post == self:
        #    self.last_activity_at = added_at
        #    self.last_activity_by = user
        #else:
        #    origin_post.last_activity_at = added_at
        #    origin_post.last_activity_by = user
        #    origin_post.save()

        return comment

    def get_global_tag_based_subscribers(
                                    self,
                                    tag_mark_reason = None,
                                    subscription_records = None
                                ):
        """returns a list of users who either follow or "do not ignore"
        the given set of tags, depending on the tag_mark_reason

        ``subscription_records`` - query set of ``~askbot.models.EmailFeedSetting``
        this argument is used to reduce number of database queries
        """
        if tag_mark_reason == 'good':
            email_tag_filter_strategy = const.INCLUDE_INTERESTING
            user_set_getter = User.objects.filter
        elif tag_mark_reason == 'bad':
            email_tag_filter_strategy = const.EXCLUDE_IGNORED
            user_set_getter = User.objects.exclude
        else:
            raise ValueError('Uknown value of tag mark reason %s' % tag_mark_reason)

        #part 1 - find users who follow or not ignore the set of tags
        tag_names = self.get_tag_names()
        tag_selections = MarkedTag.objects.filter(
                                            tag__name__in = tag_names,
                                            reason = tag_mark_reason
                                        )
        subscribers = set(
            user_set_getter(
                tag_selections__in = tag_selections
            ).filter(
                notification_subscriptions__in = subscription_records
            ).filter(
                email_tag_filter_strategy = email_tag_filter_strategy
            )
        )

        #part 2 - find users who follow or not ignore tags via wildcard selections
        #inside there is a potentially time consuming loop
        if askbot_settings.USE_WILDCARD_TAGS:
            #todo: fix this 
            #this branch will not scale well
            #because we have to loop through the list of users
            #in python
            if tag_mark_reason == 'good':
                empty_wildcard_filter = {'interesting_tags__exact': ''}
                wildcard_tags_attribute = 'interesting_tags'
                update_subscribers = lambda the_set, item: the_set.add(item)
            elif tag_mark_reason == 'bad':
                empty_wildcard_filter = {'ignored_tags__exact': ''}
                wildcard_tags_attribute = 'ignored_tags'
                update_subscribers = lambda the_set, item: the_set.discard(item)

            potential_wildcard_subscribers = User.objects.filter(
                notification_subscriptions__in = subscription_records
            ).filter(
                email_tag_filter_strategy = email_tag_filter_strategy
            ).exclude(
                **empty_wildcard_filter #need this to limit size of the loop
            )
            for potential_subscriber in potential_wildcard_subscribers:
                wildcard_tags = getattr(
                                    potential_subscriber,
                                    wildcard_tags_attribute
                                ).split(' ')

                if tags_match_some_wildcard(tag_names, wildcard_tags):
                    update_subscribers(subscribers, potential_subscriber)

        return subscribers

    def get_global_instant_notification_subscribers(self):
        """returns a set of subscribers to post according to tag filters
        both - subscribers who ignore tags or who follow only
        specific tags

        this method in turn calls several more specialized
        subscriber retrieval functions
        todo: retrieval of wildcard tag followers ignorers
              won't scale at all
        """
        subscriber_set = set()

        global_subscriptions = EmailFeedSetting.objects.filter(
                                                    feed_type = 'q_all',
                                                    frequency = 'i'
                                                )

        #segment of users who have tag filter turned off
        global_subscribers = User.objects.filter(
            email_tag_filter_strategy = const.INCLUDE_ALL
        )
        subscriber_set.update(global_subscribers)

        #segment of users who want emails on selected questions only
        subscriber_set.update(
            self.get_global_tag_based_subscribers(
                                        subscription_records = global_subscriptions,
                                        tag_mark_reason = 'good'
                                    )
        )

        #segment of users who want to exclude ignored tags
        subscriber_set.update(
            self.get_global_tag_based_subscribers(
                                        subscription_records = global_subscriptions,
                                        tag_mark_reason = 'bad'
                                    )
        )
        return subscriber_set


    def get_instant_notification_subscribers(
                                self,
                                potential_subscribers = None,
                                mentioned_users = None,
                                exclude_list = None,
                            ):
        """get list of users who have subscribed to
        receive instant notifications for a given post
        this method works for questions and answers

        Arguments:

        * ``potential_subscribers`` is not used here! todo: why? - clean this out
          parameter is left for the uniformity of the interface
          (Comment method does use it)
          normally these methods would determine the list
          :meth:`~askbot.models.question.Question.get_response_recipients`
          :meth:`~askbot.models.question.Answer.get_response_recipients`
          - depending on the type of the post
        * ``mentioned_users`` - users, mentioned in the post for the first time
        * ``exclude_list`` - users who must be excluded from the subscription

        Users who receive notifications are:

        * of ``mentioned_users`` - those who subscribe for the instant
          updates on the @name mentions
        * those who follow the parent question
        * global subscribers (any personalized tag filters are applied)
        * author of the question who subscribe to instant updates 
          on questions that they asked
        * authors or any answers who subsribe to instant updates
          on the questions which they answered
        """
        #print '------------------'
        #print 'in content function'
        subscriber_set = set()
        #print 'potential subscribers: ', potential_subscribers

        #1) mention subscribers - common to questions and answers
        if mentioned_users:
            mention_subscribers = EmailFeedSetting.objects.filter_subscribers(
                                            potential_subscribers = mentioned_users,
                                            feed_type = 'm_and_c',
                                            frequency = 'i'
                                        )
            subscriber_set.update(mention_subscribers)

        origin_post = self.get_origin_post()

        #print origin_post

        #2) individually selected - make sure that users
        #are individual subscribers to this question
        selective_subscribers = origin_post.followed_by.all()
        #print 'question followers are ', [s for s in selective_subscribers]
        if selective_subscribers:
            selective_subscribers = EmailFeedSetting.objects.filter_subscribers(
                                potential_subscribers = selective_subscribers,
                                feed_type = 'q_sel',
                                frequency = 'i'
                            )
            subscriber_set.update(selective_subscribers)
            #print 'selective subscribers: ', selective_subscribers

        #3) whole forum subscribers
        global_subscribers = origin_post.get_global_instant_notification_subscribers()
        subscriber_set.update(global_subscribers)

        #4) question asked by me (todo: not "edited_by_me" ???)
        question_author = origin_post.author
        if EmailFeedSetting.objects.filter(
                                            subscriber = question_author,
                                            frequency = 'i',
                                            feed_type = 'q_ask'
                                        ):
            subscriber_set.add(question_author)

        #4) questions answered by me -make sure is that people 
        #are authors of the answers to this question
        #todo: replace this with a query set method
        answer_authors = set()
        for answer in origin_post.answers.all():
            authors = answer.get_author_list()
            answer_authors.update(authors)

        if answer_authors:
            answer_subscribers = EmailFeedSetting.objects.filter_subscribers(
                                    potential_subscribers = answer_authors,
                                    frequency = 'i',
                                    feed_type = 'q_ans',
                                )
            subscriber_set.update(answer_subscribers)
            #print 'answer subscribers: ', answer_subscribers

        #print 'exclude_list is ', exclude_list
        subscriber_set -= set(exclude_list)

        #print 'final subscriber set is ', subscriber_set
        return list(subscriber_set)

    def get_latest_revision(self):
        return self.revisions.all().order_by('-revised_at')[0]

    def get_latest_revision_number(self):
        return self.get_latest_revision().revision

    def get_time_of_last_edit(self):
        if self.last_edited_at:
            return self.last_edited_at
        else:
            return self.added_at

    def get_owner(self):
        return self.author

    def get_author_list(
                    self,
                    include_comments = False, 
                    recursive = False, 
                    exclude_list = None):

        #todo: there may be a better way to do these queries
        authors = set()
        authors.update([r.author for r in self.revisions.all()])
        if include_comments:
            authors.update([c.user for c in self.comments.all()])
        if recursive:
            if hasattr(self, 'answers'):
                for a in self.answers.exclude(deleted = True):
                    authors.update(a.get_author_list( include_comments = include_comments ) )
        if exclude_list:
            authors -= set(exclude_list)
        return list(authors)

    def passes_tag_filter_for_user(self, user):

        question = self.get_origin_post()
        if user.email_tag_filter_strategy == const.INCLUDE_INTERESTING:
            #at least some of the tags must be marked interesting
            return user.has_affinity_to_question(
                                            question,
                                            affinity_type = 'like'
                                        )
        elif user.email_tag_filter_strategy == const.EXCLUDE_IGNORED:
            return not user.has_affinity_to_question(
                                            question,
                                            affinity_type = 'dislike'
                                        )
        elif user.email_tag_filter_strategy == const.INCLUDE_ALL:
            return True
        else:
            raise ValueError(
                        'unexpected User.email_tag_filter_strategy %s' \
                        % user.email_tag_filter_strategy
                    )

    def post_get_last_update_info(self):#todo: rename this subroutine
        when = self.added_at
        who = self.author
        if self.last_edited_at and self.last_edited_at > when:
            when = self.last_edited_at
            who = self.last_edited_by
        comments = self.comments.all()
        if len(comments) > 0:
            for c in comments:
                if c.added_at > when:
                    when = c.added_at
                    who = c.user
        return when, who

    def tagname_meta_generator(self):
        return u','.join([unicode(tag) for tag in self.get_tag_names()])

    def get_origin_post(self):
        if self.is_answer():
            return self.question
        elif self.is_question():
            return self
        raise NotImplementedError

    def _repost_as_question(self, new_title = None):
        """posts answer as question, together with all the comments
        while preserving time stamps and authors
        does not delete the answer itself though
        """
        if not self.is_answer():
            raise NotImplementedError
        revisions = self.revisions.all().order_by('revised_at')
        rev0 = revisions[0]
        new_question = rev0.author.post_question(
            title = new_title,
            body_text = rev0.text,
            tags = self.question.tagnames,
            wiki = self.question.wiki,
            is_anonymous = self.question.is_anonymous,
            timestamp = rev0.revised_at
        )
        if len(revisions) > 1:
            for rev in revisions[1:]:
                rev.author.edit_question(
                    question = new_question,
                    body_text = rev.text,
                    revision_comment = rev.summary,
                    timestamp = rev.revised_at
                )
        for comment in self.comments.all():
            comment.content_object = new_question
            comment.save()
        return new_question

    def swap_with_question(self, new_title = None):
        """swaps answer with the question it belongs to and
        sets the title of question to ``new_title``
        """
        if not self.is_answer():
            raise NotImplementedError
        #1) make new question by using new title, tags of old question
        #   and the answer body, as well as the authors of all revisions
        #   and repost all the comments
        new_question = self._repost_as_question(new_title = new_title)

        #2) post question (all revisions and comments) as answer
        new_answer = self.question.repost_as_answer(question = new_question)

        #3) assign all remaining answers to the new question
        self.question.answers.update(question = new_question)
        self.question.delete()
        self.delete()
        return new_question


    def get_page_number(self, answers = None):
        """When question has many answers, answers are
        paginated. This function returns number of the page
        on which the answer will be shown, using the default
        sort order. The result may depend on the visitor."""
        if self.is_question():
            return 1
        elif self.is_answer():
            order_number = 0
            for answer in answers:
                if self == answer:
                    break
                order_number += 1
            return int(order_number/const.ANSWERS_PAGE_SIZE) + 1
        raise NotImplementedError

    def get_user_vote(self, user):
        if not self.is_answer():
            raise NotImplementedError
        
        if user.is_anonymous():
            return None

        votes = self.votes.filter(user=user)
        if votes and votes.count() > 0:
            return votes[0]
        else:
            return None


    def _question__assert_is_visible_to(self, user):
        """raises QuestionHidden"""
        if self.deleted:
            message = _(
                    'Sorry, this question has been '
                    'deleted and is no longer accessible'
                )
            if user.is_anonymous():
                raise exceptions.QuestionHidden(message)
            try:
                user.assert_can_see_deleted_post(self)
            except django_exceptions.PermissionDenied:
                raise exceptions.QuestionHidden(message)

    def _answer__assert_is_visible_to(self, user):
        """raises QuestionHidden or AnswerHidden"""
        try:
            self.question.assert_is_visible_to(user)
        except exceptions.QuestionHidden:
            message = _(
                        'Sorry, the answer you are looking for is '
                        'no longer available, because the parent '
                        'question has been removed'
                       )
            raise exceptions.QuestionHidden(message)
        if self.deleted:
            message = _(
                    'Sorry, this answer has been '
                    'removed and is no longer accessible'
                )
            if user.is_anonymous():
                raise exceptions.AnswerHidden(message)
            try:
                user.assert_can_see_deleted_post(self)
            except django_exceptions.PermissionDenied:
                raise exceptions.AnswerHidden(message)

    def assert_is_visible_to(self, user):
        if self.is_question():
            return self._question__assert_is_visible_to(user)
        elif self.is_answer():
            return self._answer__assert_is_visible_to(user)
        raise NotImplementedError

    def get_updated_activity_data(self, created = False):
        if self.is_answer():
            #todo: simplify this to always return latest revision for the second
            #part
            if created:
                return const.TYPE_ACTIVITY_ANSWER, self
            else:
                latest_revision = self.get_latest_revision()
                return const.TYPE_ACTIVITY_UPDATE_ANSWER, latest_revision
        elif self.is_question():
            if created:
                return const.TYPE_ACTIVITY_ASK_QUESTION, self
            else:
                latest_revision = self.get_latest_revision()
                return const.TYPE_ACTIVITY_UPDATE_QUESTION, latest_revision
        raise NotImplementedError

    def get_tag_names(self):
        if self.is_question():
            """Creates a list of Tag names from the ``tagnames`` attribute."""
            return self.tagnames.split(u' ')
        elif self.is_answer():
            """return tag names on the question"""
            return self.question.get_tag_names()
        raise NotImplementedError


    def _answer__apply_edit(self, edited_at=None, edited_by=None, text=None, comment=None, wiki=False):

        if text is None:
            text = self.get_latest_revision().text
        if edited_at is None:
            edited_at = datetime.datetime.now()
        if edited_by is None:
            raise Exception('edited_by is required')

        self.last_edited_at = edited_at
        self.last_edited_by = edited_by
        #self.html is denormalized in save()
        self.text = text
        #todo: bug wiki has no effect here

        #must add revision before saving the answer
        self.add_revision(
            author = edited_by,
            revised_at = edited_at,
            text = text,
            comment = comment
        )

        self.parse_and_save(author = edited_by)

        self.question.last_activity_at = edited_at
        self.question.last_activity_by = edited_by
        self.question.save()

    def _question__apply_edit(self, edited_at=None, edited_by=None, title=None,\
                    text=None, comment=None, tags=None, wiki=False, \
                    edit_anonymously = False):

        latest_revision = self.get_latest_revision()
        #a hack to allow partial edits - important for SE loader
        if title is None:
            title = self.title
        if text is None:
            text = latest_revision.text
        if tags is None:
            tags = latest_revision.tagnames

        if edited_by is None:
            raise Exception('parameter edited_by is required')

        if edited_at is None:
            edited_at = datetime.datetime.now()

        # Update the Question itself
        self.title = title
        self.last_edited_at = edited_at
        self.last_activity_at = edited_at
        self.last_edited_by = edited_by
        self.last_activity_by = edited_by
        self.tagnames = tags
        self.text = text
        self.is_anonymous = edit_anonymously

        #wiki is an eternal trap whence there is no exit
        if self.wiki == False and wiki == True:
            self.wiki = True

        # Update the Question tag associations
        if latest_revision.tagnames != tags:
            self.update_tags(tagnames = tags, user = edited_by, timestamp = edited_at)

        # Create a new revision
        self.add_revision(
            author = edited_by,
            text = text,
            revised_at = edited_at,
            is_anonymous = edit_anonymously,
            comment = comment,
        )

        self.parse_and_save(author = edited_by)

    def apply_edit(self, *kargs, **kwargs):
        if self.is_answer():
            return self._answer__apply_edit(*kargs, **kwargs)
        elif self.is_question():
            return self._question__apply_edit(*kargs, **kwargs)
        raise NotImplementedError

    def _answer__add_revision(self, author=None, revised_at=None, text=None, comment=None):
        #todo: this may be identical to Question.add_revision
        if None in (author, revised_at, text):
            raise Exception('arguments author, revised_at and text are required')
        rev_no = self.revisions.all().count() + 1
        if comment in (None, ''):
            if rev_no == 1:
                comment = const.POST_STATUS['default_version']
            else:
                comment = 'No.%s Revision' % rev_no
        return PostRevision.objects.create_answer_revision(
                                  answer=self,
                                  author=author,
                                  revised_at=revised_at,
                                  text=text,
                                  summary=comment,
                                  revision=rev_no
                                  )

    def _question__add_revision(
                self,
                author = None,
                is_anonymous = False,
                text = None,
                comment = None,
                revised_at = None
            ):
        if None in (author, text, comment):
            raise Exception('author, text and comment are required arguments')
        rev_no = self.revisions.all().count() + 1
        if comment in (None, ''):
            if rev_no == 1:
                comment = const.POST_STATUS['default_version']
            else:
                comment = 'No.%s Revision' % rev_no

        return PostRevision.objects.create_question_revision(
            question   = self,
            revision   = rev_no,
            title      = self.title,
            author     = author,
            is_anonymous = is_anonymous,
            revised_at = revised_at,
            tagnames   = self.tagnames,
            summary    = comment,
            text       = text
        )

    def add_revision(self, *kargs, **kwargs):
        if self.is_answer():
            return self._answer__add_revision(*kargs, **kwargs)
        elif self.is_question():
            return self._question__add_revision(*kargs, **kwargs)
        raise NotImplementedError

    def _answer__get_response_receivers(self, exclude_list = None):
        """get list of users interested in this response
        update based on their participation in the question
        activity

        exclude_list is required and normally should contain
        author of the updated so that he/she is not notified of
        the response
        """
        assert(exclude_list is not None)
        recipients = set()
        recipients.update(
                            self.get_author_list(
                                include_comments = True
                            )
                        )
        recipients.update(
                            self.question.get_author_list(
                                    include_comments = True
                                )
                        )
        for answer in self.question.answers.all():
            recipients.update(answer.get_author_list())

        recipients -= set(exclude_list)

        return list(recipients)

    def _question__get_response_receivers(self, exclude_list = None):
        """returns list of users who might be interested
        in the question update based on their participation
        in the question activity

        exclude_list is mandatory - it normally should have the
        author of the update so the he/she is not notified about the update
        """
        assert(exclude_list != None)
        recipients = set()
        recipients.update(
                            self.get_author_list(
                                    include_comments = True
                                )
                        )
        #do not include answer commenters here
        for a in self.answers.all():
            recipients.update(a.get_author_list())

        recipients -= set(exclude_list)
        return recipients

    def get_response_receivers(self, exclude_list = None):
        if self.is_answer():
            return self._answer__get_response_receivers(exclude_list)
        elif self.is_question():
            return self._question__get_response_receivers(exclude_list)
        raise NotImplementedError

    def get_question_title(self):
        if self.is_answer():
            return self.question.title
        elif self.is_question():
            if self.closed:
                attr = const.POST_STATUS['closed']
            elif self.deleted:
                attr = const.POST_STATUS['deleted']
            else:
                attr = None
            if attr is not None:
                return u'%s %s' % (self.title, attr)
            else:
                return self.title
        raise NotImplementedError
