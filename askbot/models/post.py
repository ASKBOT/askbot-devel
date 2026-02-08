from collections import defaultdict
import operator
import logging
from urllib.parse import quote as django_urlquote

from django.contrib.sitemaps import ping_google
from django.conf import settings as django_settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import html as html_utils
from django.utils import timezone
from django.utils.text import Truncator
from django.utils.translation import activate as activate_language
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.core import exceptions as django_exceptions
from django.core import cache
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType

import askbot

from askbot import signals
from askbot.utils.loading import load_plugin, load_function
from askbot.utils.slug import slugify
from askbot import const
from askbot.models.tag import MarkedTag
from askbot.models.tag import tags_match_some_wildcard
from askbot.models.fields import LanguageCodeField
from askbot.conf import settings as askbot_settings
from askbot import exceptions
from askbot.utils import markup
from askbot.utils.html import (get_word_count, has_moderated_tags,
                               moderate_tags, sanitize_html,
                               site_url)
from askbot.utils.celery_utils import defer_celery_task
from askbot.models.base import (AnonymousContent, BaseQuerySetManager,
                                DraftContent)

# TODO: maybe merge askbot.utils.markup and forum.utils.html
from askbot.utils.diff import textDiff as htmldiff
#from askbot.search import mysql


def default_html_moderator(post):
    """Moderates inline HTML items: images and/or links
    depending on what items are moderated per settings.

    Returns sanitized html with suspicious
    content edited out and replaced with warning signs.
    Moderators content is not sanitized.

    Latest revision is placed on the moderation queue.

    TODO: Make moderation work per-item: e.g. per link
    or per image.

    This function can be overridden by setting python path
    to the alternative function as a value of `ASKBOT_HTML_MODERATOR`
    in the settings.py, e.g:

    ASKBOT_HTML_MODERATOR = 'my_extension.html_moderator'
    """
    if not (askbot_settings.MODERATE_LINKS or askbot_settings.MODERATE_IMAGES):
        return post.html

    rev = post.current_revision

    author = rev.author
    not_admin = not author.is_administrator_or_moderator()
    if not_admin and has_moderated_tags(post.html):
        before = post.html
        after = moderate_tags(before)
        if after != before:
            rev.place_on_moderation_queue()
            return after

    return post.html


class PostToGroup(models.Model):
    post = models.ForeignKey('Post', on_delete=models.CASCADE)
    group = models.ForeignKey('Group', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('post', 'group')
        app_label = 'askbot'
        db_table = 'askbot_post_groups'


class PostQuerySet(models.query.QuerySet):
    """
    Custom query set subclass for :class:`~askbot.models.Post`
    """
    # TODO: we may not need this query set class,
    # as all methods on this class seem to want to
    # belong to Thread manager or Query set.
    def get_for_user(self, user):
        from askbot.models.user import Group
        if not askbot_settings.GROUPS_ENABLED:
            return self

        if user is None or user.is_anonymous:
            groups = [Group.objects.get_global_group()]
        else:
            groups = user.get_groups()

        return self.filter(groups__in=groups).distinct()

    def get_by_text_query(self, search_query):
        """returns a query set of questions,
        matching the full text query
        """
        return self.filter(
            models.Q(thread__title__icontains=search_query) |
            models.Q(text__icontains=search_query) |
            models.Q(thread__tagnames=search_query) |
            models.Q(thread__posts__text__icontains=search_query,
                     thread__posts__post_type='answer')
        )
        # TODO - goes to thread - we search whole threads
        # if getattr(django_settings, 'USE_SPHINX_SEARCH', False):
        #     matching_questions = Question.sphinx_search.query(search_query)
        #     question_ids = [q.id for q in matching_questions]
        #     return Question.objects.filter(deleted = False, id__in = question_ids)
        # if django_settings.DATABASE_ENGINE == 'mysql' and mysql.supports_full_text_search():
        #     return self.filter(
        #         models.Q(thread__title__search = search_query)\
        #         | models.Q(text__search = search_query)\
        #         | models.Q(thread__tagnames__search = search_query)\
        #         | models.Q(answers__text__search = search_query)
        #     )
        # elif 'postgresql_psycopg2' in askbot.get_database_engine_name():
        #     rank_clause = "ts_rank(question.text_search_vector, plainto_tsquery(%s))";
        #     search_query = '&'.join(search_query.split())
        #     extra_params = (search_query,)
        #     extra_kwargs = {
        #         'select': {'relevance': rank_clause},
        #         'where': ['text_search_vector @@ plainto_tsquery(%s)'],
        #         'params': extra_params,
        #         'select_params': extra_params,
        #         }
        #     return self.extra(**extra_kwargs)
        # else:
        #     #fallback to dumb title match search
        #     return self.filter(thread__title__icontains=search_query)

    def added_between(self, start, end):
        """questions added between ``start`` and ``end`` timestamps"""
        # TODO: goes to thread
        return self.filter(added_at__gt=start).exclude(added_at__gt=end)

    def get_questions_needing_reminder(self, user=None, activity_type=None,
                                       recurrence_delay=None):
        """returns list of questions that need a reminder,
        corresponding the given ``activity_type``
        ``user`` - is the user receiving the reminder
        ``recurrence_delay`` - interval between sending the
        reminders about the same question
        """
        # TODO: goes to thread
        from askbot.models import Activity  # avoid circular import
        question_list = list()
        for question in self:
            try:
                activity = Activity.objects.get(
                    user=user, question=question, activity_type=activity_type)
                now = timezone.now()
                if now < activity.active_at + recurrence_delay:
                    continue
            except Activity.DoesNotExist:
                activity = Activity(user=user, question=question,
                                    activity_type=activity_type,
                                    content_object=question)
            activity.active_at = timezone.now()
            activity.save()
            question_list.append(question)
        return question_list

    def get_author_list(self, **kwargs):
        # TODO: - this is duplication - answer manager also has this method
        # will be gone when models are consolidated
        # note that method get_question_and_answer_contributors is similar in function
        # todo: goes to thread
        authors = set()
        for question in self:
            authors.update(question.get_author_list(**kwargs))
        return list(authors)


class PostManager(BaseQuerySetManager):
    def get_queryset(self):
        return PostQuerySet(self.model)

    def get_questions(self, user=None):
        questions = self.filter(post_type='question')
        return questions.get_for_user(user)

    def get_answers(self, user=None):
        """returns query set of answer posts,
        optionally filtered to exclude posts of groups
        to which user does not belong"""
        answers = self.filter(post_type='answer')
        return answers.get_for_user(user)

    def get_comments(self):
        return self.filter(post_type='comment')

    def create_new_tag_wiki(self, text=None, author=None):
        return self.create_new(None,  # this post type is threadless
                               author, timezone.now(), text, wiki=True,
                               post_type='tag_wiki')

    def create_new(self, thread, author, added_at, text, parent=None,
                   wiki=False, is_private=False, email_notify=False,
                   post_type=None, by_email=False, ip_addr=None):
        # TODO: Some of this code will go to Post.objects.create_new

        assert(post_type in const.POST_TYPES)

        if thread:
            language_code = thread.language_code
        else:
            language_code = get_language()

        # .html field is denormalized by the save() call
        post = Post(post_type=post_type, thread=thread, parent=parent,
                    author=author, added_at=added_at, wiki=wiki,
                    text=text, language_code=language_code)

        if post.wiki:
            post.last_edited_by = post.author
            post.last_edited_at = added_at
            post.wikified_at = added_at

        post.save()  # saved so that revision can have post_id

        revision = post.add_revision(
            author=author,
            revised_at=added_at,
            text=text,
            comment=str(const.POST_STATUS['default_version']),
            by_email=by_email,
            ip_addr=ip_addr
        )

        # now we parse html
        parse_results = post.parse_and_save(author=author,
                                            is_private=is_private)

        # moderate inline content
        post.moderate_html()

        if revision.revision > 0:
            signals.post_updated.send(
                post=post,
                updated_by=author,
                newly_mentioned_users=parse_results['newly_mentioned_users'],
                timestamp=added_at,
                created=True,
                diff=parse_results['diff'],
                sender=post.__class__
            )
        return post

    # TODO: instead of this, have Thread.add_answer()
    def create_new_answer(self, thread, author, added_at, text, wiki=False,
                          is_private=False, email_notify=False, by_email=False,
                          ip_addr=None):
        answer = self.create_new(thread, author, added_at, text, wiki=wiki,
                                 is_private=is_private, post_type='answer',
                                 by_email=by_email, ip_addr=ip_addr)
        # set notification/delete
        if email_notify:
            thread.followed_by.add(author)
        else:
            thread.followed_by.remove(author)

        # update thread data
        # TODO: this totally belongs to some `Thread` class method
        if answer.is_approved():
            thread.answer_count += 1
            thread.set_last_activity_info(last_activity_at=added_at,
                                          last_activity_by=author)
            thread.save()
        return answer

    def precache_comments(self, for_posts, visitor):
        """
        Fetches comments for given posts, and stores them in post._cached_comments
        If visitor is authenticated, annotatets posts with ``upvoted_by_user`` parameter.
        If visitor is authenticated, adds own comments that are in moderation.
        """
        qs = Post.objects.get_comments()\
            .filter(parent__in=for_posts)\
            .select_related('author')

        if visitor.is_anonymous:
            comments = list(qs.order_by('added_at'))
        else:
            upvoted_by_user = list(qs.filter(votes__user=visitor).distinct())
            not_upvoted_by_user = list(qs.exclude(votes__user=visitor).distinct())

            for c in upvoted_by_user:
                c.upvoted_by_user = 1  # numeric value to maintain compatibility with previous version of this code

            comments = upvoted_by_user + not_upvoted_by_user
            comments.sort(key=operator.attrgetter('added_at'))

        # filter out comments that user should not see
        premoderation = askbot_settings.CONTENT_MODERATION_MODE == 'premoderation'
        if premoderation and visitor.is_authenticated:
            comments = [comment for comment in comments if (comment.approved or comment.author_id == visitor.pk)]
            
        post_map = defaultdict(list)
        for cm in comments:
            post_map[cm.parent_id].append(cm)

        for post in for_posts:
            post.set_cached_comments(post_map[post.id])

        # Old Post.get_comment(self, visitor=None) method:
        #        if visitor.is_anonymous:
        #            return self.comments.order_by('added_at')
        #        else:
        #            upvoted_by_user = list(self.comments.filter(votes__user=visitor).distinct())
        #            not_upvoted_by_user = list(self.comments.exclude(votes__user=visitor).distinct())
        #
        #            for c in upvoted_by_user:
        #                c.upvoted_by_user = 1  # numeric value to maintain compatibility with previous version of this code
        #
        #            comments = upvoted_by_user + not_upvoted_by_user
        #            comments.sort(key=operator.attrgetter('added_at'))
        #
        #            return comments


class MockPost(object):
    """Used for special purposes, e.g. to fill
    out the js templates for the posts made via ajax
    """
    def __init__(self, post_type=None, author=None):
        from askbot.models.user import MockUser
        self.post_type = post_type
        self.score = 0
        self.id = 0
        self.author = MockUser()
        self.summary = ''
        self.added_at = timezone.now()

    def needs_moderation(self):
        return False

    def get_post_type_display(self):
        return self.post_type


POST_RENDERERS_MAP = django_settings.ASKBOT_POST_RENDERERS
def get_post_renderer_type(post_type):
    have_simple_comment = (
        post_type == 'comment' and
        askbot_settings.COMMENTS_EDITOR_TYPE == 'plain-text'
    )
    if have_simple_comment:
        return 'plain-text'
    else:
        return askbot_settings.EDITOR_TYPE


class Post(models.Model):
    post_type = models.CharField(max_length=255, db_index=True)

    # NOTE: if these fields are deleted - then jive import needs fixing!!!
    old_question_id = models.PositiveIntegerField(null=True, blank=True,
                                                  default=None, unique=True)
    old_answer_id = models.PositiveIntegerField(null=True, blank=True,
                                                default=None, unique=True)
    old_comment_id = models.PositiveIntegerField(null=True, blank=True,
                                                 default=None, unique=True)

    # Answer or Question for Comment
    parent = models.ForeignKey('Post', blank=True, null=True,
                               related_name='comments',
                               on_delete=models.CASCADE)
    thread = models.ForeignKey('Thread', blank=True, null=True, default=None,
                               related_name='posts',
                               on_delete=models.CASCADE)
    # nullable b/c we have to first save post and then add link to current
    # revision (which has a non-nullable fk to post)
    current_revision = models.ForeignKey('PostRevision', blank=True, null=True,
                                         related_name='rendered_posts',
                                         on_delete=models.CASCADE)
    # used for group-private posts
    groups = models.ManyToManyField('Group', through='PostToGroup',
                                    related_name='group_posts')

    author = models.ForeignKey(User, related_name='posts', on_delete=models.CASCADE)
    added_at = models.DateTimeField(default=timezone.now)

    # endorsed == accepted as best in the case of answer
    # use word 'endorsed' to differentiate from 'approved', which
    # is used for the moderation
    # note: accepted answer is also denormalized on the Thread model
    endorsed = models.BooleanField(default=False, db_index=True)
    endorsed_by = models.ForeignKey(User, null=True, blank=True,
                                    related_name='endorsed_posts',
                                    on_delete=models.CASCADE)
    endorsed_at = models.DateTimeField(null=True, blank=True)

    # denormalized data: the core approval of the posts is made
    # in the revisions. In the revisions there is more data about
    # approvals - by whom and when
    approved = models.BooleanField(default=True, db_index=True)

    deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(User, null=True, blank=True,
                                   related_name='deleted_posts',
                                   on_delete=models.CASCADE)

    marked_as_spam = models.BooleanField(default=False, db_index=True)
    marked_as_spam_by = models.ForeignKey(User, null=True, blank=True,
                                          on_delete=models.SET_NULL)
    marked_as_spam_at = models.DateTimeField(null=True, blank=True)

    wiki = models.BooleanField(default=False)
    wikified_at = models.DateTimeField(null=True, blank=True)

    locked = models.BooleanField(default=False)
    locked_by = models.ForeignKey(User, null=True, blank=True,
                                  related_name='locked_posts',
                                  on_delete=models.CASCADE)
    locked_at = models.DateTimeField(null=True, blank=True)

    points = models.IntegerField(default=0, db_column='score')
    vote_up_count = models.IntegerField(default=0)
    vote_down_count = models.IntegerField(default=0)

    comment_count = models.PositiveIntegerField(default=0)
    offensive_flag_count = models.SmallIntegerField(default=0)

    last_edited_at = models.DateTimeField(null=True, blank=True)
    last_edited_by = models.ForeignKey(User, null=True, blank=True, related_name='last_edited_posts', on_delete=models.CASCADE)

    html = models.TextField(null=True)  # html rendition of the latest revision
    text = models.TextField(null=True)  # denormalized copy of latest revision
    language_code = LanguageCodeField()

    # Denormalised data
    summary = models.TextField(null=True)

    # note: anonymity here applies to question only, but
    # the field will still go to thread
    # maybe we should rename it to is_question_anonymous
    # we might have to duplicate the is_anonymous on the Post,
    # if we are to allow anonymous answers
    # the reason is that the title and tags belong to thread,
    # but the question body to Post
    is_anonymous = models.BooleanField(default=False)

    objects = PostManager()

    class Meta:
        ordering = [ '-last_edited_at', '-points' ]
        app_label = 'askbot'
        db_table = 'askbot_post'

    # property to support legacy themes in case there are.
    @property
    def score(self):
        return int(self.points)

    @score.setter
    def score(self, number):
        if number:
            self.points = int(number)

    def as_tweet(self):
        """a naive tweet representation of post
        todo: add mentions to relevant people
        """
        url = site_url(self.get_absolute_url(no_slug=True))
        if self.post_type == 'question':
            tweet = askbot_settings.WORDS_QUESTION_SINGULAR + ': '
        elif self.post_type == 'answer':
            tweet = askbot_settings.WORDS_ANSWER_SINGULAR + ': '

        chars_left = 140 - (len(url) + len(tweet) + 1)
        title_str = self.thread.title[:chars_left]
        return tweet + title_str + ' ' + url

    def parse_post_text(self):
        """typically post has a field to store raw source text
        in comment it is called .comment, in Question and Answer it is
        called .text
        also there is another field called .html (consistent across models)
        so the goal of this function is to render raw text into .html
        and extract any metadata given stored in source (currently
        this metadata is limited by twitter style @mentions
        but there may be more in the future

        function returns a dictionary with the following keys
        html
        newly_mentioned_users - list of <User> objects
        removed_mentions - list of mention <Activity> objects - for removed ones
        """

        text_converter = self.get_text_converter()
        text = text_converter(self.text)

        # TODO: add markdown parser call conditional on self.use_markdown flag
        post_html = text
        mentioned_authors = list()
        removed_mentions = list()
        if '@' in text:
            op = self.get_origin_post()

            if op.id:
                anticipated_authors = op.get_author_list(include_comments=True,
                                                         recursive=True)
            else:
                anticipated_authors = list()

            extra_name_seeds = markup.extract_mentioned_name_seeds(text)

            extra_authors = set()
            for name_seed in extra_name_seeds:
                extra_authors.update(
                    User.objects.filter(username__istartswith=name_seed))

            # it is important to preserve order here so that authors of post
            # get mentioned first
            anticipated_authors += list(extra_authors)

            mentioned_authors, post_html = markup.mentionize_text(
                text, anticipated_authors)

            # TODO: stuff below possibly does not belong here
            # find mentions that were removed and identify any previously
            # entered mentions so that we can send alerts on only new ones
            from askbot.models.user import Activity
            if self.pk is not None:
                # only look for previous mentions if post was already saved before
                prev_mention_qs = Activity.objects.get_mentions(
                    mentioned_in=self)
                new_set = set(mentioned_authors)
                for prev_mention in prev_mention_qs:

                    user = prev_mention.get_mentioned_user()
                    if user is None:
                        continue
                    if user in new_set:
                        # don't report mention twice
                        new_set.remove(user)
                    else:
                        removed_mentions.append(prev_mention)
                mentioned_authors = list(new_set)

        data = {
            'html': post_html,
            'newly_mentioned_users': mentioned_authors,
            'removed_mentions': removed_mentions,
        }
        return data

    # TODO: when models are merged, it would be great to remove author parameter
    def parse_and_save(self, author=None, **kwargs):
        """converts .text version of post to .html
        using appropriate converter.
        @mentions are rendered as well as internal links.
        """
        assert(author is not None)

        last_revision = self.html
        data = self.parse_post_text()

        # TODO: possibly remove feature of posting links
        # depending on user's reputation
        self.html = author.fix_html_links(data['html'])

        # a hack allowing to save denormalized .summary field for questions
        if hasattr(self, 'summary'):
            self.summary = self.get_snippet()

        newly_mentioned_users = set(data['newly_mentioned_users']) - set([author])
        removed_mentions = data['removed_mentions']

        # delete removed mentions
        for rm in removed_mentions:
            rm.delete()

        created = self.pk is None

        is_private = kwargs.pop('is_private', False)
        group_id = kwargs.pop('group_id', None)

        #this save must precede saving the mention activity
        #as well as assigning groups to the post
        #because generic relation needs primary key of the related object
        super(Post, self).save(**kwargs)

        # TODO: move this group stuff out of this function
        if self.is_comment():
            # copy groups from the parent post into the comment
            groups = self.parent.groups.all()
            self.add_to_groups(groups)
        elif is_private or group_id:
            self.make_private(author, group_id=group_id)
        elif self.thread_id:  # is connected to thread
            # inherit privacy scope from thread
            thread_groups = self.thread.groups.all()
            self.add_to_groups(thread_groups)
        else:
            self.make_public()

        if last_revision:
            diff = htmldiff(
                        sanitize_html(last_revision),
                        sanitize_html(self.html)
                    )
        else:
            diff = sanitize_html(self.get_snippet())

        timestamp = self.get_time_of_last_edit()

        try:
            from askbot.conf import settings as askbot_settings
            if askbot_settings.GOOGLE_SITEMAP_CODE != '':
                ping_google()
        except Exception:
            logging.debug('cannot ping google - did you register with them?')

        return {'diff': diff, 'newly_mentioned_users': newly_mentioned_users}

    def render(self):
        """Rerenders post html and snippet, no saving."""
        self.html = self.parse_post_text()['html']
        self.summary = self.get_snippet()

    def recount_comments(self):
        """Updates denormalized value `Post.comment_count` according to the
        number of comments in the database"""
        self.comment_count = self.comments.filter(deleted=False, approved=True).count()

    def is_question(self):
        return self.post_type == 'question'

    def is_answer(self):
        return self.post_type == 'answer'

    def is_comment(self):
        return self.post_type == 'comment'

    def is_qa_content(self):
        return self.post_type in ('question', 'answer', 'comment')

    def is_tag_wiki(self):
        return self.post_type == 'tag_wiki'

    def is_reject_reason(self):
        return self.post_type == 'reject_reason'

    def get_comments_count(self, user):
        """Returns number of comments under teh post that can be
        seen by the user"""
        if not user or user.is_anonymous:
            return self.comment_count

        return self.comment_count + int(self.has_moderated_comment(user))

    def get_flag_activity_object(self, user):
        """Returns flag activity object, preferrably initialized by the user,
        If user is admin or mod, return any flag object.
        Raises an exception, if object does not exist.
        """
        from askbot.models import Activity
        try:
            return Activity.objects.get(object_id=self.pk,
                                        content_type=ContentType.objects.get_for_model(self),
                                        user_id=user.pk,
                                        activity_type=const.TYPE_ACTIVITY_MARK_OFFENSIVE)
        except Activity.DoesNotExist:
            if not user.is_administrator_or_moderator:
                raise

            return Activity.objects.get(object_id=self.pk,
                                        content_type=ContentType.objects.get_for_model(self),
                                        activity_type=const.TYPE_ACTIVITY_MARK_OFFENSIVE)

    def get_last_edited_date(self):
        """returns date of last edit or date of creation
        if there were no edits"""
        return self.last_edited_at or self.added_at

    def get_latest_revision_diff(self, ins_start=None, ins_end=None,
                                 del_start=None, del_end=None):
        # returns formatted html diff of the latest two revisions
        revisions = self.revisions.exclude(revision=0).order_by('-id')
        if revisions.count() < 2:
            return ''

        revisions = revisions[:2]
        return htmldiff(sanitize_html(revisions[1].html),
                        sanitize_html(revisions[0].html),
                        ins_start=ins_start,
                        ins_end=ins_end,
                        del_start=del_start,
                        del_end=del_end)

    def get_moderators(self):
        """returns query set of users who are site administrators
        and moderators"""
        #if askbot_settings.GROUPS_ENABLED:
        #    post_groups = self.groups.all()
        #    user_filter = user_filter & models.Q(
        #                                group_membership__group__in=post_groups
        #                            )
        return User.objects.filter(askbot_profile__status__in=('m', 'd')).distinct()

    def get_post_type_display(self):
        """Returns localized post type"""
        if self.is_comment():
            return _('comment')
        if self.is_answer():
            return _('answer')
        if self.is_question():
            return _('question')

        return _('piece of content')

    def get_previous_answer(self, user=None):
        """returns a previous answer to a given answer;
        only works on the "answer" post types"""
        assert(self.post_type == 'answer')
        all_answers = self.thread.get_answers(user=user)

        matching_answers = all_answers.filter(
                        added_at__lt=self.added_at,
                    ).order_by('-added_at')

        if len(matching_answers) == 0:
            return None

        answer = matching_answers[0]

        if answer.id == self.id:
            return None
        if answer.added_at > self.added_at:
            return None

        return answer

    def get_text_converter(self):
        """returns text converter, which may
        be overridden by setting
        ASKBOT_POST_RENDERERS (look for format in the source code)
        """
        renderer_type = get_post_renderer_type(self.post_type)
        try:
            renderer_path = POST_RENDERERS_MAP[renderer_type]
        except KeyError:
            raise NotImplementedError

        return load_function(renderer_path)

    def has_group(self, group):
        """true if post belongs to the group"""
        return self.groups.filter(id=group.id).exists()

    def has_moderated_comment(self, user):
        """`True` if post has moderated comment authored by user"""
        if not user:
            return False

        if user.is_anonymous:
            return False

        cached_comments = getattr(self, '_cached_comments', None)
        if cached_comments:
            for comment in cached_comments:
                if comment.author_id == user.pk:
                    if not comment.approved:
                        return True
            return False

        return Post.objects.filter(
            parent=self,
            post_type='comment',
            author=user,
            approved=False
        ).exists()
    
    def add_to_groups(self, groups):
        """associates post with groups"""
        # TODO: use bulk-creation
        for group in groups:
            PostToGroup.objects.get_or_create(post=self, group=group)
        if self.is_answer() or self.is_question():
            comments = self.comments.all()
            for group in groups:
                for comment in comments:
                    PostToGroup.objects.get_or_create(post=comment, group=group)

    def remove_from_groups(self, groups):
        PostToGroup.objects.filter(post=self, group__in=groups).delete()
        if self.is_answer() or self.is_question():
            comment_ids = self.comments.all().values_list('id', flat=True)
            PostToGroup.objects.filter(
                        post__id__in=comment_ids,
                        group__in=groups
                    ).delete()

    def issue_update_notifications(self, updated_by=None, notify_sets=None,
                                   activity_type=None, suppress_email=False,
                                   timestamp=None, diff=None):
        """Called when a post is updated. Arguments:

        * ``notify_sets`` - result of ``Post.get_notify_sets()`` method

        The method does two things:

        * records "red envelope" recipients of the post
        * sends email alerts to all subscribers to the post
        """
        assert(activity_type is not None)
        if diff:
            summary = diff
        else:
            summary = self.get_snippet()

        from askbot.models import Activity
        update_activity = Activity(
                        user=updated_by,
                        active_at=timestamp,
                        content_object=self.current_revision,
                        activity_type=activity_type,
                        question=self.get_origin_post(),
                        summary=summary
                    )
        update_activity.save()

        update_activity.add_recipients(notify_sets['for_inbox'])

        # create new mentions (barring the double-adds)
        from askbot.models import Activity
        for u in notify_sets['for_mentions'] - notify_sets['for_inbox']:
            Activity.objects.create_new_mention(
                                    mentioned_whom=u,
                                    mentioned_in=self,
                                    mentioned_by=updated_by,
                                    mentioned_at=timestamp
                                )

        for user in (notify_sets['for_inbox'] | notify_sets['for_mentions']):
            user.update_response_counts()

        # shortcircuit if the email alerts are disabled
        if suppress_email or not askbot_settings.ENABLE_EMAIL_ALERTS:
            return

        if not askbot_settings.INSTANT_EMAIL_ALERT_ENABLED:
            return

        # TODO: fix this temporary spam protection plug
        if askbot_settings.MIN_REP_TO_TRIGGER_EMAIL:
            if not (updated_by.is_administrator() or updated_by.is_moderator()):
                if updated_by.reputation < askbot_settings.MIN_REP_TO_TRIGGER_EMAIL:
                    for_email = [u for u in notify_sets['for_email'] if u.is_administrator()]
                    notify_sets['for_email'] = for_email

        if not getattr(django_settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            cache_key = 'instant-notification-%d-%d' % (self.thread.id, updated_by.id)
            if cache.cache.get(cache_key):
                return
            cache.cache.set(cache_key, True, django_settings.NOTIFICATION_DELAY_TIME)

        from askbot.tasks import send_instant_notifications_about_activity_in_post
        recipient_ids = [user.id for user in notify_sets['for_email']]
        defer_celery_task(
            send_instant_notifications_about_activity_in_post,
            args=(
                update_activity.pk,
                self.id,
                recipient_ids
            ),
            countdown=django_settings.NOTIFICATION_DELAY_TIME
        )

    def delete_update_notifications(self, keep_activity):
        """reverse of issue update notifications
        With second argument `False` Activities and ActivityAuditStatus
        records are deleted, with `True` only ActivityAuditStatus items
        are deleted
        """
        # Find revisions of current post
        # The reason is that notifications are bound to revisions
        # not the posts themselves
        self_rev_ids = set(self.revisions.values_list('pk', flat=True))

        # Find revisions of child posts
        child_posts = Post.objects.filter(parent=self)
        child_post_ids = child_posts.values_list('pk', flat=True)
        child_revs = PostRevision.objects.filter(post__pk__in=child_post_ids)
        child_rev_ids = set(child_revs.values_list('pk', flat=True))

        rev_ids = list(self_rev_ids | child_rev_ids)

        from askbot.tasks import delete_update_notifications_task
        task_args = (rev_ids, keep_activity)
        defer_celery_task(delete_update_notifications_task, args=task_args)

    def make_private(self, user, group_id=None):
        """makes post private within user's groups
        todo: this is a copy-paste in thread and post
        """
        from askbot.models.user import Group
        if group_id:
            group = Group.objects.get(id=group_id)
            groups = [group]
            self.add_to_groups(groups)

            global_group = Group.objects.get_global_group()
            if group != global_group:
                self.remove_from_groups((global_group,))
        else:
            if self.thread_id and self.is_question() is False:
                # for thread-related answers and comments we base
                # privacy scope on thread + add a personal group
                personal_groups = user.get_groups(private=True)
                thread_groups = self.thread.get_groups_shared_with()
                groups = set(personal_groups) | set(thread_groups)
            else:
                groups = user.get_groups(private=True)

            self.add_to_groups(groups)
            self.remove_from_groups((Group.objects.get_global_group(),))

        if len(groups) == 0:
            message = _('Sharing did not work, because group is unknown')
            user.message_set.create(message=message)

    def make_public(self):
        """removes the privacy mark from users groups"""
        from askbot.models.user import Group
        groups = (Group.objects.get_global_group(),)
        self.add_to_groups(groups)

    def merge_post(self, post, user=None):
        """merge with other post"""
        # take latest revision of current post R1
        rev = self.get_latest_revision()
        orig_text = rev.text
        for rev in post.revisions.all().order_by('revision'):
            # for each revision of other post Ri
            # append content of Ri to R1 and use author
            new_text = orig_text + '\n\n' + rev.text
            self.apply_edit(edited_at=timezone.now(),
                            edited_by=user,
                            text=new_text,
                            comment=_('merged revision'),
                            by_email=False,
                            edit_anonymously=rev.is_anonymous,
                            suppress_email=True,
                            ip_addr=rev.ip_addr)

        if post.is_question() or post.is_answer():
            comments = Post.objects.get_comments().filter(parent=post)
            comments.update(parent=self)
            self.recount_comments()

        # TODO: implement redirects
        if post.is_question():
            self.old_question_id = post.id
        elif post.is_answer():
            self.old_answer_id = post.id
        elif post.is_comment():
            self.old_comment_id = post.id

        self.save()
        post.delete()

    def moderate_html(self):
        """moderate inline content, such
        as links and images"""
        moderate = load_plugin('ASKBOT_HTML_MODERATOR',
                               'askbot.models.post.default_html_moderator')

        before = self.html
        after = moderate(self)
        if after != before:
            self.html = after
            self.summary = self.get_snippet()
            self.save()

    def is_private(self):
        """true, if post belongs to the global group"""
        if askbot_settings.GROUPS_ENABLED:
            from askbot.models.user import Group
            group = Group.objects.get_global_group()
            return not self.groups.filter(id=group.id).exists()
        return False

    def set_runtime_needs_moderation(self):
        """Used at runtime only, the value is not
        stored in the database"""
        self._is_approved = False

    def set_is_approved(self, is_approved):
        """sets denormalized value of whether post/thread is
        approved"""
        self.approved = is_approved
        self.save()
        if self.is_question():
            self.thread.approved = is_approved
            self.thread.save()

    def is_approved(self):
        """``False`` only when moderation is ``True`` and post
        ``self.approved is False``
        """
        if getattr(self, '_is_approved', True) == False:
            return False

        if askbot_settings.CONTENT_MODERATION_MODE == 'premoderation':
            if self.approved:
                return True
            if self.revisions.filter(revision=0).count() == 1:
                return False
        return True

    def needs_moderation(self):
        # TODO: do we need this, can't we just use is_approved()?
        return not self.is_approved()

    def get_absolute_url(self, no_slug=False, question_post=None,
                         language=None, thread=None):
        from askbot.utils.slug import slugify
        # TODO: the url generation function is pretty bad -
        # the trailing slash is entered in three places here + in urls.py
        if not hasattr(self, '_thread_cache') and thread:
            self._thread_cache = thread

        if askbot.is_multilingual():
            request_language = get_language()
            activate_language(language or self.language_code)

        if self.is_answer():
            if not question_post:
                question_post = self.thread._question_post()
            if no_slug:
                url = '%(base)s?answer=%(id)d#post-id-%(id)d' % {
                    'base': reverse('question', args=[question_post.id]),
                    'id': self.id
                }
            else:
                url = '%(base)s%(slug)s/?answer=%(id)d#post-id-%(id)d' % {
                    'base': reverse('question', args=[question_post.id]),
                    'slug': django_urlquote(slugify(self.thread.title)),
                    'id': self.id
                }
        elif self.is_question():
            url = reverse('question', args=[self.id])
            if thread:
                url += django_urlquote(slugify(thread.title)) + '/'
            elif no_slug is False:
                url += django_urlquote(self.slug) + '/'
        elif self.is_comment():
            origin_post = self.get_origin_post()
            url = '%(url)s?comment=%(id)d#post-id-%(id)d' % \
                {'url': origin_post.get_absolute_url(thread=thread), 'id': self.id}
        else:
            raise NotImplementedError

        if askbot.is_multilingual():
            activate_language(request_language)

        return url

    def delete(self, **kwargs):
        """deletes comment and concomitant response activity
        records, as well as mention records, while preserving
        integrity or response counts for the users
        """
        if self.is_comment():
            # TODO: implement a custom delete method on these
            # all this should pack into Activity.responses.filter( somehow ).delete()
            # activity_types = const.RESPONSE_ACTIVITY_TYPES_FOR_DISPLAY
            # activity_types += (const.TYPE_ACTIVITY_MENTION,)
            # TODO: not very good import in models of other models
            # TODO: potentially a circular import
            from askbot.models.user import Activity
            comment_content_type = ContentType.objects.get_for_model(self)
            activities = Activity.objects.filter(
                                content_type=comment_content_type,
                                object_id=self.id)
                                # activity_type__in = activity_types

            recipients = set()
            for activity in activities:
                for user in activity.recipients.all():
                    recipients.add(user)

            # activities need to be deleted before the response
            # counts are updated
            activities.delete()

            for user in recipients:
                user.update_response_counts()

        super(Post, self).delete(**kwargs)

    def __str__(self):
        if self.is_question():
            return self.thread.title
        else:
            return self.html

    def save(self, *args, **kwargs):
        super(Post, self).save(*args, **kwargs)
        if self.is_answer() and 'postgres' in askbot.get_database_engine_name():
            # hit the database to trigger update of full text search vector
            self.thread._question_post().save()

    def _get_slug(self):
        if not self.is_question():
            raise NotImplementedError
        return slugify(self.thread.title)
    slug = property(_get_slug)

    def get_text_content(self, title=None, body_text=None, tags=None):
        """Returns text content of the post.
        Parts can be overrridden by the optional parameters.
        This method was created for purposes of the spam classification"""
        if self.is_question():
            title = title or self.thread.title
            tags = tags or self.thread.tagnames
            body_text = body_text or self.text
            return '{}\n\n{}\n\n{}'.format(title, tags, body_text)
        return body_text or self.text

    def get_snippet(self, max_length=None):
        """returns an abbreviated HTML snippet of the content
        or full content, depending on how long it is
        todo: remove the max_length parameter
        """
        if max_length is None:
            if self.post_type == 'comment':
                max_words = askbot_settings.MIN_WORDS_TO_WRAP_COMMENTS
            else:
                max_words = askbot_settings.MIN_WORDS_TO_WRAP_POSTS
        else:
            max_words = int(max_length/5)

        from askbot.utils.html import sanitize_html
        truncated = sanitize_html(Truncator(self.html).words(max_words, truncate=' ...', html=True))
        new_count = get_word_count(truncated)
        orig_count = get_word_count(self.html)
        if new_count + 1 < orig_count:
            expander = '<span class="js-expander"> <a>(' + _('more') + ')</a></span>'
            if truncated.endswith('</p>'):
                # better put expander inside the paragraph
                snippet = truncated[:-4] + expander + '</p>'
            else:
                snippet = truncated + expander
            # it is important to have div here, so that we can make
            # the expander work
            return '<div class="js-snippet">' + snippet + '</div>'

        return self.html

    def filter_authorized_users(self, candidates):
        """returns list of users who are allowed to see this post"""
        if not askbot_settings.GROUPS_ENABLED:
            return candidates
        else:
            if len(candidates) == 0:
                return candidates
            # get post groups
            groups = list(self.groups.all())

            if len(groups) == 0:
                logging.critical('post %d is groupless' % self.id)
                return list()

            # load group memberships for the candidates
            from askbot.models.user import GroupMembership
            memberships = GroupMembership.objects.filter(
                                            user__in=candidates,
                                            group__in=groups)
            user_ids = set(memberships.values_list('user__id', flat=True))

            # scan through the user ids and see which are group members
            filtered_candidates = set()
            for candidate in candidates:
                if candidate.id in user_ids:
                    filtered_candidates.add(candidate)

            return filtered_candidates

    def set_cached_comments(self, comments):
        """caches comments in the lifetime of the object
        does not talk to the actual cache system
        """
        self._cached_comments = comments

    def get_cached_comments(self):
        try:
            return self._cached_comments
        except AttributeError:
            self._cached_comments = list()
            return self._cached_comments

    def add_cached_comment(self, comment): #pylint: disable=missing-docstring
        comments = self.get_cached_comments()
        if comment not in comments:
            comments.append(comment)

        def get_timestamp(item): #pylint: disable=missing-docstring
            return item.added_at

        self.set_cached_comments(sorted(comments, key=get_timestamp))

    def reverse_cached_comments(self):
        self.get_cached_comments().reverse()

    def add_comment(self, comment=None, user=None, added_at=None,
                    by_email=False, ip_addr=None):
        if added_at is None:
            added_at = timezone.now()
        if None in (comment, user):
            raise Exception('arguments comment and user are required')

        comment_post = self.__class__.objects.create_new(
                                                self.thread,
                                                user,
                                                added_at,
                                                comment,
                                                parent=self,
                                                post_type='comment',
                                                by_email=by_email,
                                                ip_addr=ip_addr,
                                            )
        if comment_post.is_approved():
            self.recount_comments()
            self.save()

        if askbot_settings.COMMENT_EDITING_BUMPS_THREAD:
            # TODO: fix send_email_alerts command so that
            # excessive emails are not sent
            self.thread.set_last_activity_info(added_at, user)

        return comment_post

    def get_global_tag_based_subscribers(self, tag_mark_reason=None,
                                         subscription_records=None):
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
        elif tag_mark_reason == 'subscribed':
            email_tag_filter_strategy = const.INCLUDE_SUBSCRIBED
            user_set_getter = User.objects.filter
        else:
            raise ValueError('Uknown value of tag mark reason %s' % tag_mark_reason)

        # part 1 - find users who follow or not ignore the set of tags
        tag_names = self.get_tag_names()
        tag_selections = MarkedTag.objects.filter(
                                        tag__name__in=tag_names,
                                        tag__language_code=get_language(),
                                        reason=tag_mark_reason)
        subscribers = set(
            user_set_getter(
                tag_selections__in=tag_selections
            ).filter(
                askbot_profile__email_tag_filter_strategy=email_tag_filter_strategy,
                notification_subscriptions__in=subscription_records
            )
        )

        # part 2 - find users who follow or not ignore tags via wildcard selections
        # inside there is a potentially time consuming loop
        if askbot_settings.USE_WILDCARD_TAGS:
            # TODO: fix this
            # this branch will not scale well
            # because we have to loop through the list of users
            # in python
            if tag_mark_reason == 'good':
                empty_wildcard_filter = {'askbot_profile__interesting_tags__exact': ''}
                wildcard_tags_attribute = 'interesting_tags'
                update_subscribers = lambda the_set, item: the_set.add(item)
            elif tag_mark_reason == 'bad':
                empty_wildcard_filter = {'askbot_profile__ignored_tags__exact': ''}
                wildcard_tags_attribute = 'ignored_tags'
                update_subscribers = lambda the_set, item: the_set.discard(item)
            elif tag_mark_reason == 'subscribed':
                empty_wildcard_filter = {'askbot_profile__subscribed_tags__exact': ''}
                wildcard_tags_attribute = 'subscribed_tags'
                update_subscribers = lambda the_set, item: the_set.add(item)

            potential_wildcard_subscribers = User.objects.filter(
                notification_subscriptions__in=subscription_records
            ).filter(
                askbot_profile__email_tag_filter_strategy=email_tag_filter_strategy
            ).exclude(
                **empty_wildcard_filter  # need this to limit size of the loop
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

        from askbot.models.user import EmailFeedSetting
        global_subscriptions = EmailFeedSetting.objects.filter(
            feed_type='q_all',
            frequency='i'
        )

        # segment of users who have tag filter turned off
        global_subscribers = User.objects.filter(
            models.Q(askbot_profile__email_tag_filter_strategy=const.INCLUDE_ALL) &
            models.Q(notification_subscriptions__feed_type='q_all',
                     notification_subscriptions__frequency='i')
        )
        subscriber_set.update(global_subscribers)

        # segment of users who want emails on selected questions only
        if askbot_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED:
            good_mark_reason = 'subscribed'
        else:
            good_mark_reason = 'good'
        subscriber_set.update(
            self.get_global_tag_based_subscribers(
                subscription_records=global_subscriptions,
                tag_mark_reason=good_mark_reason
            )
        )

        # segment of users who want to exclude ignored tags
        subscriber_set.update(
            self.get_global_tag_based_subscribers(
                subscription_records=global_subscriptions,
                tag_mark_reason='bad'
            )
        )
        return subscriber_set

    def _qa__get_instant_notification_subscribers(
            self, potential_subscribers=None, mentioned_users=None,
            exclude_list=None):
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
        * authors or any answers who subscribe to instant updates
          on the questions which they answered
        """
        subscriber_set = set()

        # 1) mention subscribers - common to questions and answers
        from askbot.models.user import EmailFeedSetting
        if mentioned_users:
            mention_subscribers = EmailFeedSetting.objects.filter_subscribers(
                potential_subscribers=mentioned_users,
                feed_type='m_and_c',
                frequency='i'
            )
            subscriber_set.update(mention_subscribers)

        origin_post = self.get_origin_post()

        # 2) individually selected - make sure that users
        # are individual subscribers to this question
        # TODO: The line below works only if origin_post is Question !
        selective_subscribers = origin_post.thread.followed_by.all()

        if selective_subscribers:
            selective_subscribers = EmailFeedSetting.objects.filter_subscribers(
                potential_subscribers=selective_subscribers,
                feed_type='q_sel',
                frequency='i'
            )
            subscriber_set.update(selective_subscribers)

        # 3) whole forum subscribers
        global_subscribers = origin_post.get_global_instant_notification_subscribers()
        subscriber_set.update(global_subscribers)

        # 4) question asked by me (todo: not "edited_by_me" ???)
        question_author = origin_post.author
        if EmailFeedSetting.objects.filter(
            subscriber=question_author,
            frequency='i',
            feed_type='q_ask'
        ).exists():
            subscriber_set.add(question_author)

        # 4) questions answered by me -make sure is that people
        # are authors of the answers to this question
        # TODO: replace this with a query set method
        answer_authors = set()
        for answer in origin_post.thread.posts.get_answers().all():
            authors = answer.get_author_list()
            answer_authors.update(authors)

        if answer_authors:
            answer_subscribers = EmailFeedSetting.objects.filter_subscribers(
                potential_subscribers=answer_authors,
                frequency='i',
                feed_type='q_ans',
            )
            subscriber_set.update(answer_subscribers)

        return subscriber_set - set(exclude_list)

    def _comment__get_instant_notification_subscribers(
            self, potential_subscribers=None, mentioned_users=None,
            exclude_list=None):
        """get list of users who want instant notifications about comments

        argument potential_subscribers is required as it saves on db hits

        Here is the list of people who will receive the notifications:

        * mentioned users
        * of response receivers
          (see :meth:`~askbot.models.meta.Comment.get_response_receivers`) -
          those who subscribe for the instant
          updates on comments and @mentions
        * all who follow the question explicitly
        * all global subscribers
          (tag filtered, and subject to personalized settings)
        """
        subscriber_set = set()

        if potential_subscribers:
            potential_subscribers = set(potential_subscribers)
        else:
            potential_subscribers = set()

        if mentioned_users:
            potential_subscribers.update(mentioned_users)

        from askbot.models.user import EmailFeedSetting
        if potential_subscribers:
            comment_subscribers = EmailFeedSetting.objects.filter_subscribers(
                                        potential_subscribers=potential_subscribers,
                                        feed_type='m_and_c',
                                        frequency='i')
            subscriber_set.update(comment_subscribers)

        origin_post = self.get_origin_post()
        # TODO: The line below works only if origin_post is Question !
        selective_subscribers = origin_post.thread.followed_by.all()
        if selective_subscribers:
            selective_subscribers=EmailFeedSetting.objects.filter_subscribers(
                                    potential_subscribers=selective_subscribers,
                                    feed_type='q_sel',
                                    frequency='i')
            for subscriber in selective_subscribers:
                if origin_post.passes_tag_filter_for_user(subscriber):
                    subscriber_set.add(subscriber)

            subscriber_set.update(selective_subscribers)

        global_subscribers = origin_post.get_global_instant_notification_subscribers()
        subscriber_set.update(global_subscribers)

        return subscriber_set - set(exclude_list)

    def get_instant_notification_subscribers(
            self, potential_subscribers=None, mentioned_users=None,
            exclude_list=None):
        if self.is_question() or self.is_answer():
            subscribers = self._qa__get_instant_notification_subscribers(
                potential_subscribers=potential_subscribers,
                mentioned_users=mentioned_users,
                exclude_list=exclude_list
            )
        elif self.is_comment():
            subscribers = self._comment__get_instant_notification_subscribers(
                potential_subscribers=potential_subscribers,
                mentioned_users=mentioned_users,
                exclude_list=exclude_list
            )
        elif self.is_tag_wiki() or self.is_reject_reason():
            return set()
        else:
            raise NotImplementedError

        # if askbot_settings.GROUPS_ENABLED and self.is_effectively_private():
        # for subscriber in subscribers:
        subscribers = self.filter_authorized_users(subscribers)

        # filter subscribers by language
        if askbot.is_multilingual():
            language = self.thread.language_code
            filtered_subscribers = list()
            for subscriber in subscribers:
                subscriber_languages = subscriber.get_languages()
                if language in subscriber_languages:
                    filtered_subscribers.append(subscriber)
            return filtered_subscribers
        else:
            return subscribers

    def get_notify_sets(self, mentioned_users=None, exclude_list=None):
        """returns three lists of users in a dictionary with keys:
        * 'for_inbox' - users for which to add inbox items
        * 'for_mentions' - for whom mentions are added
        * 'for_email' - to whom email notifications should be sent
        """
        result = dict()
        result['for_mentions'] = set(mentioned_users) - set(exclude_list)
        # what users are included depends on the post type
        # for example for question - all Q&A contributors
        # are included, for comments only authors of comments and parent
        # post are included
        result['for_inbox'] = self.get_response_receivers(exclude_list=exclude_list)

        if not askbot_settings.ENABLE_EMAIL_ALERTS:
            result['for_email'] = set()
        else:
            # TODO: weird thing is that only comments need the recipients
            # TODO: debug these calls and then uncomment in the repo
            # argument to this call
            result['for_email'] = self.get_instant_notification_subscribers(
                potential_subscribers=result['for_inbox'],
                mentioned_users=result['for_mentions'],
                exclude_list=exclude_list)
        return result

    def cache_latest_revision(self, rev):
        setattr(self, '_last_rev_cache', rev)

    def get_latest_revision(self, visitor=None):
        """Returns the latest revision the `visitor` is allowed to see."""
        if hasattr(self, '_last_rev_cache'):
            return self._last_rev_cache

        rev = self.revisions.order_by('-id')[0]
        if not rev.can_be_seen_by(visitor):
            rev = self.revisions.exclude(revision=0).order_by('-id')[0]

        self.cache_latest_revision(rev)
        return rev

    def get_earliest_revision(self, visitor=None):
        """Returns the earliest revision the `visitor` is allowed to see."""
        if hasattr(self, '_first_rev_cache'):
            return self._first_rev_cache

        rev = self.revisions.order_by('id')[0]
        if not rev.can_be_seen_by(visitor):
            rev = self.revisions.exclude(revision=0).order_by('id')[0]

        setattr(self, '_first_rev_cache', rev)
        return rev

    def get_latest_revision_number(self):
        """Returns order number of the latest revision"""
        try:
            return self.get_latest_revision().revision
        except IndexError:
            return 0

    def get_time_of_last_edit(self):
        if self.is_comment():
            return self.added_at

        if self.last_edited_at:
            return self.last_edited_at
        else:
            return self.added_at

    def get_author_list(self, include_comments=False, recursive=False,
                        exclude_list=None):

        # TODO: there may be a better way to do these queries
        authors = set()
        #authors.update([r.author for r in self.revisions.all()])
        #TODO : add all authors of merged posts, but for that authors
        #must be reflected on merge revisions, currently author of merge
        #revision is user who made the merge
        authors.add(self.author)
        if include_comments:
            authors.update([c.author for c in self.comments.all()])
        if recursive and self.is_question(): #hasattr(self, 'answers'):
            #for a in self.answers.exclude(deleted = True):
            for a in self.thread.posts.get_answers().exclude(deleted=True):
                authors.update(a.get_author_list(include_comments=include_comments ))
        if exclude_list:
            authors -= set(exclude_list)
        return list(authors)

    def passes_tag_filter_for_user(self, user):

        question = self.get_origin_post()
        if user.email_tag_filter_strategy == const.INCLUDE_INTERESTING:
            # at least some of the tags must be marked interesting
            return user.has_affinity_to_question(question, affinity_type='like')
        elif user.email_tag_filter_strategy == const.EXCLUDE_IGNORED:
            return not user.has_affinity_to_question(
                question, affinity_type='dislike')
        elif user.email_tag_filter_strategy == const.INCLUDE_ALL:
            return True
        elif user.email_tag_filter_strategy == const.INCLUDE_SUBSCRIBED:
            return user.has_affinity_to_question(question, affinity_type='like')
        else:
            raise ValueError(
                'unexpected User.email_tag_filter_strategy %s'
                % user.email_tag_filter_strategy
            )

    def post_get_last_update_info(self):  # TODO: rename this subroutine
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
                    who = c.author
        return when, who

    def tagname_meta_generator(self):
        return ','.join([str(tag) for tag in self.get_tag_names()])

    def get_parent_post(self):
        """returns parent post or None
        if there is no parent, as it is in the case of question post"""
        if self.post_type == 'comment':
            return self.parent
        elif self.post_type == 'answer':
            return self.get_origin_post()
        else:
            return None

    def get_parent_post_chain(self):
        parent = self.get_parent_post()
        parents = list()
        if parent:
            parents.append(parent)
            parents.extend(parent.get_parent_post_chain())
        return parents

    def get_origin_post(self):
        if self.is_question():
            return self
        if self.is_tag_wiki() or self.is_reject_reason():
            return None
        else:
            return self.thread._question_post()

    def _repost_as_question(self, new_title=None):
        """posts answer as question, together with all the comments
        while preserving time stamps and authors
        does not delete the answer itself though
        """
        if not self.is_answer():
            raise NotImplementedError
        revisions = self.revisions.all().order_by('revised_at')
        rev0 = revisions[0]
        new_question = rev0.author.post_question(
            title=new_title, body_text=rev0.text,
            tags=self.question.thread.tagnames, wiki=self.question.wiki,
            is_anonymous=self.question.is_anonymous, timestamp=rev0.revised_at)
        if len(revisions) > 1:
            for rev in revisions[1:]:
                rev.author.edit_question(
                    question=new_question, body_text=rev.text,
                    revision_comment=rev.summary, timestamp=rev.revised_at)
        for comment in self.comments.all():
            comment.content_object = new_question
            comment.save()
        return new_question

    def _repost_as_answer(self, question=None):
        """posts question as answer to another question,
        but does not delete the question,
        but moves all the comments to the new answer"""
        if not self.is_question():
            raise NotImplementedError
        revisions = self.revisions.all().order_by('revised_at')
        rev0 = revisions[0]
        new_answer = rev0.author.post_answer(
            question=question, body_text=rev0.text, wiki=self.wiki,
            timestamp=rev0.revised_at)
        if len(revisions) > 1:
            for rev in revisions:
                rev.author.edit_answer(
                    answer=new_answer, body_text=rev.text,
                    revision_comment=rev.summary, timestamp=rev.revised_at)
        for comment in self.comments.all():
            comment.content_object = new_answer
            comment.save()
        return new_answer

    def swap_with_question(self, new_title=None):
        """swaps answer with the question it belongs to and
        sets the title of question to ``new_title``
        """
        if not self.is_answer():
            raise NotImplementedError
        # 1) make new question by using new title, tags of old question
        #    and the answer body, as well as the authors of all revisions
        #    and repost all the comments
        new_question = self._repost_as_question(new_title=new_title)

        # 2) post question (all revisions and comments) as answer
        new_answer = self.question._repost_as_answer(question=new_question)

        # 3) assign all remaining answers to the new question
        self.question.answers.update(question=new_question)
        self.question.delete()
        self.delete()
        return new_question

    def get_user_vote(self, user):
        if not self.is_answer():
            raise NotImplementedError

        if user.is_anonymous:
            return None

        votes = self.votes.filter(user=user)
        if votes and votes.count() > 0:
            return votes[0]
        else:
            return None

    def _question__assert_is_visible_to(self, user):
        """raises QuestionHidden"""
        if self.is_approved() is False:
            if user != self.author:
                raise exceptions.QuestionHidden(_('Sorry, this content is not available'))
        if self.deleted:
            message = _('Sorry, this content is no longer available')
            if user.is_anonymous:
                raise exceptions.QuestionHidden(message)
            try:
                user.assert_can_see_deleted_post(self)
            except django_exceptions.PermissionDenied:
                raise exceptions.QuestionHidden(message)

    def _answer__assert_is_visible_to(self, user):
        """raises QuestionHidden or AnswerHidden"""
        try:
            self.thread._question_post().assert_is_visible_to(user)
        except exceptions.QuestionHidden:
            message = _('Sorry, this content is no longer available')
            raise exceptions.QuestionHidden(message)
        if self.deleted:
            message = _('Sorry, this content is no longer available')
            if user.is_anonymous:
                raise exceptions.AnswerHidden(message)
            try:
                user.assert_can_see_deleted_post(self)
            except django_exceptions.PermissionDenied:
                raise exceptions.AnswerHidden(message)

    def _comment__assert_is_visible_to(self, user):
        """raises QuestionHidden or AnswerHidden"""
        try:
            self.parent.assert_is_visible_to(user)
        except exceptions.QuestionHidden:
            message = _('Sorry, this comment is no longer available')
            raise exceptions.QuestionHidden(message)
        except exceptions.AnswerHidden:
            message = _('Sorry, this comment is no longer available')
            raise exceptions.AnswerHidden(message)

    def assert_is_visible_to_user_groups(self, user):
        """raises permission denied of the post
        is hidden due to group memberships"""
        assert(self.is_comment() == False)
        post_groups = self.groups.all()
        global_group_name = askbot_settings.GLOBAL_GROUP_NAME
        if post_groups.filter(name=global_group_name).count() == 1:
            return

        if self.is_question(): # TODO maybe merge the "hidden" exceptions
            exception = exceptions.QuestionHidden
        elif self.is_answer():
            exception = exceptions.AnswerHidden
        else:
            raise NotImplementedError

        message = _('This post is temporarily not available')
        if user.is_anonymous:
            raise exception(message)
        else:
            user_groups_ids = user.get_groups().values_list('id', flat=True)
            if post_groups.filter(id__in=user_groups_ids).count() == 0:
                raise exception(message)

    def assert_is_visible_to(self, user):
        if self.is_comment() == False and askbot_settings.GROUPS_ENABLED:
            self.assert_is_visible_to_user_groups(user)
        if self.is_question():
            return self._question__assert_is_visible_to(user)
        elif self.is_answer():
            return self._answer__assert_is_visible_to(user)
        elif self.is_comment():
            return self._comment__assert_is_visible_to(user)
        raise NotImplementedError

    def get_updated_activity_type(self, created):
        if self.is_answer():
            if created:
                return const.TYPE_ACTIVITY_ANSWER
            return const.TYPE_ACTIVITY_UPDATE_ANSWER
        elif self.is_question():
            if created:
                return const.TYPE_ACTIVITY_ASK_QUESTION
            return const.TYPE_ACTIVITY_UPDATE_QUESTION
        elif self.is_comment():
            if self.parent.post_type == 'question':
                return const.TYPE_ACTIVITY_COMMENT_QUESTION
            elif self.parent.post_type == 'answer':
                return const.TYPE_ACTIVITY_COMMENT_ANSWER
            #todo - what if there is other parent post
            #we might support nested comments at some point
        elif self.is_tag_wiki():
            return const.TYPE_ACTIVITY_UPDATE_TAG_WIKI
        elif self.is_reject_reason():
            return const.TYPE_ACTIVITY_CREATE_REJECT_REASON
        raise NotImplementedError

    def get_tag_names(self):
        return self.thread.get_tag_names()

    def apply_edit(
                    self,
                    edited_at=None,
                    edited_by=None,
                    text=None,
                    comment=None,
                    wiki=False,
                    edit_anonymously=False,
                    is_private=False,
                    by_email=False,
                    suppress_email=False,
                    ip_addr=None,
                ):
        latest_rev = self.get_latest_revision(edited_by)

        if text is None:
            text = latest_rev.text
        if edited_at is None:
            edited_at = timezone.now()
        if edited_by is None:
            raise Exception('edited_by is required')

        self.last_edited_at = edited_at
        self.last_edited_by = edited_by
        # self.html is denormalized in save()
        self.text = text
        if edit_anonymously:
            self.is_anonymous = edit_anonymously
        # else:
        # pass - we remove anonymity via separate function call

        # wiki is an eternal trap whence there is no exit
        if not self.wiki and wiki:
            self.wiki = True

        # must add or update revision before saving the answer
        if latest_rev.revision == 0:
            # if post has only 0 revision, we just update the
            # latest revision data
            latest_rev.text = text
            latest_rev.revised_at = edited_at
            latest_rev.save()
        else:
            # otherwise we create a new revision
            latest_rev = self.add_revision(
                author=edited_by,
                revised_at=edited_at,
                text=text,
                comment=comment,
                by_email=by_email,
                ip_addr=ip_addr,
                is_anonymous=edit_anonymously
            )

        if latest_rev.revision > 0 or not self.approved:
            parse_results = self.parse_and_save(author=edited_by,
                                                is_private=is_private)

            self.moderate_html()

            signals.post_updated.send(
                post=self,
                updated_by=edited_by,
                newly_mentioned_users=parse_results['newly_mentioned_users'],
                suppress_email=suppress_email,
                timestamp=edited_at,
                created=False,
                diff=parse_results['diff'],
                sender=self.__class__
            )

        if self.is_comment() and askbot_settings.COMMENT_EDITING_BUMPS_THREAD:
            self.thread.set_last_activity_info(
                            last_activity_at=edited_at,
                            last_activity_by=edited_by
                        )

        return latest_rev

    def __add_revision(
                    self,
                    author=None,
                    revised_at=None,
                    text=None,
                    comment=None,
                    by_email=False,
                    ip_addr=None,
                    is_anonymous=False
                ):
        #todo: this may be identical to Question.add_revision
        if None in (author, revised_at, text):
            raise Exception('arguments author, revised_at and text are required')
        return PostRevision.objects.create(
            post=self,
            author=author,
            revised_at=revised_at,
            text=text,
            summary=comment,
            by_email=by_email,
            ip_addr=ip_addr,
            is_anonymous=is_anonymous
        )

    def _question__add_revision(self, author=None, is_anonymous=False,
                                text=None, comment=None, revised_at=None,
                                by_email=False, email_address=None,
                                ip_addr=None):
        if None in (author, text):
            raise Exception('author, text and comment are required arguments')

        return PostRevision.objects.create(
            post=self,
            title=self.thread.title,
            author=author,
            is_anonymous=is_anonymous,
            revised_at=revised_at,
            tagnames=self.thread.tagnames,
            summary=str(comment),
            text=text,
            by_email=by_email,
            email_address=email_address,
            ip_addr=ip_addr
        )

    def add_revision(self, *kargs, **kwargs):
        # TODO: unify these
        if self.post_type in ('answer', 'comment', 'tag_wiki', 'reject_reason'):
            return self.__add_revision(*kargs, **kwargs)
        elif self.is_question():
            return self._question__add_revision(*kargs, **kwargs)
        raise NotImplementedError

    def _answer__get_response_receivers(self, exclude_list=None):
        """get list of users interested in this response
        update based on their participation in the question
        activity

        exclude_list is required and normally should contain
        author of the updated so that he/she is not notified of
        the response
        """
        assert(exclude_list is not None)
        recipients = set()
        recipients.update(self.get_author_list(include_comments=True))
        question = self.thread._question_post()
        recipients.update(question.get_author_list(include_comments=True))
        for answer in question.thread.posts.get_answers().all():
            recipients.update(answer.get_author_list())

        return recipients - set(exclude_list)

    def _question__get_response_receivers(self, exclude_list=None):
        """returns list of users who might be interested
        in the question update based on their participation
        in the question activity

        exclude_list is mandatory - it normally should have the
        author of the update so the he/she is not notified about the update
        """
        assert(exclude_list is not None)
        recipients = set()
        recipients.update(self.get_author_list(include_comments=True))
        # do not include answer commenters here
        for a in self.thread.posts.get_answers().all():
            recipients.update(a.get_author_list())

        return recipients - set(exclude_list)

    def _comment__get_response_receivers(self, exclude_list=None):
        """Response receivers are commenters of the
        same post and the authors of the post itself.
        """
        assert(exclude_list is not None)
        users = set()
        # get authors of parent object and all associated comments
        users.update(self.parent.get_author_list(include_comments=True))
        return users - set(exclude_list)

    def get_response_receivers(self, exclude_list=None):
        """returns a list of response receiving users
        who see the on-screen notifications
        """
        if self.is_answer():
            receivers = self._answer__get_response_receivers(exclude_list)
        elif self.is_question():
            receivers = self._question__get_response_receivers(exclude_list)
        elif self.is_comment():
            receivers = self._comment__get_response_receivers(exclude_list)
        elif self.is_tag_wiki() or self.is_reject_reason():
            return set()  # TODO: who should get these?
        else:
            raise NotImplementedError

        return self.filter_authorized_users(receivers)

    def get_question_title(self):
        if self.is_question():
            if self.thread.closed:
                attr = const.POST_STATUS['closed']
            elif self.deleted:
                attr = const.POST_STATUS['deleted']
            else:
                attr = None
            if attr is not None:
                return '%s %s' % (self.thread.title, str(attr))
            else:
                return self.thread.title
        raise NotImplementedError

    def get_page_number(self, answer_posts):
        """When question has many answers, answers are
        paginated. This function returns number of the page
        on which the answer will be shown, using the default
        sort order. The result may depend on the visitor."""
        if not self.is_answer() and not self.is_comment():
            raise NotImplementedError

        if self.is_comment():
            post = self.parent
            if post.is_question():
                # first page of answers since it's the question comment
                return 1
        else:
            post = self

        order_number = 0
        for answer_post in answer_posts:
            if post == answer_post:
                break
            order_number += 1
        return int(order_number/const.ANSWERS_PAGE_SIZE) + 1

    def get_order_number(self):
        if not self.is_comment():
            raise NotImplementedError
        return self.parent.comments.filter(added_at__lt=self.added_at).count() + 1

    def is_upvoted_by(self, user):
        from askbot.models.repute import Vote
        return Vote.objects.filter(user=user, voted_post=self, vote=Vote.VOTE_UP).exists()

    def is_last(self):
        """True if there are no newer comments on
        the related parent object
        """
        if not self.is_comment():
            raise NotImplementedError
        return not Post.objects.get_comments().filter(
            added_at__gt=self.added_at,
            parent=self.parent
        ).exists()

    def hack_template_marker(self, name):
        list(Post.objects.filter(text=name))


class PostRevisionManager(models.Manager):
    def create(self, *args, **kwargs):
        # clean the "summary" field
        kwargs.setdefault('summary', '')
        if kwargs['summary'] is None:
            kwargs['summary'] = ''

        author = kwargs['author']
        post = kwargs['post']

        moderate_email = False
        if kwargs.get('email'):
            from askbot.models.reply_by_email import emailed_content_needs_moderation
            moderate_email = emailed_content_needs_moderation(kwargs['email'])

        is_content = post.is_question() or post.is_answer() or post.is_comment()
        needs_moderation = is_content and (author.needs_moderation() or moderate_email)

        needs_premoderation = askbot_settings.CONTENT_MODERATION_MODE == 'premoderation' \
            and needs_moderation

        # 0 revision is not shown to the users
        if needs_premoderation:
            kwargs.update({
                'approved': False,
                'approved_by': None,
                'approved_at': None,
                'revision': 0,
                'summary': kwargs['summary'] or _('Suggested edit')
            })

            # see if we have earlier revision with number 0
            try:
                pending_revs = post.revisions.filter(revision=0)
                assert(len(pending_revs) == 1)
                pending_revs.update(**kwargs)
                revision = pending_revs[0]
            except AssertionError:
                revision = super(PostRevisionManager, self).create(*args, **kwargs)
        else:
            kwargs['revision'] = post.get_latest_revision_number() + 1
            revision = super(PostRevisionManager, self).create(*args, **kwargs)

            # set default summary
            if revision.summary == '':
                if revision.revision == 1:
                    revision.summary = str(const.POST_STATUS['default_version'])
                else:
                    revision.summary = 'No.%s Revision' % revision.revision
            revision.save()

            signals.post_revision_published.send(None, revision=revision)

        # audit or pre-moderation modes require placement of the post on the
        # moderation queue
        if needs_moderation:
            revision.place_on_moderation_queue()

        # set current "rendered" revision for soft moderation,
        # for autoapproved revision and premoderated revision
        # of new post
        if not needs_premoderation:
            post.current_revision = revision
            post.save()
        elif post.revisions.count() == 1:
            post.current_revision = revision
            post.save()
        # don't advance current revision if we
        # have premoderated revision and have previously
        # approved revisions

        revision.post.cache_latest_revision(revision)

        # maybe add language of the post to the user's languages
        langs = set(author.get_languages())
        if post.language_code not in langs:
            langs.add(post.language_code)
            author.set_languages(langs)
            author.save()

        return revision


class PostRevision(models.Model):
    QUESTION_REVISION_TEMPLATE_NO_TAGS = (
        '<h3>%(title)s</h3>\n'
        '<div class="text">%(html)s</div>\n'
    )

    post = models.ForeignKey('askbot.Post', related_name='revisions',
                             null=True, blank=True, on_delete=models.CASCADE)
    revision = models.PositiveIntegerField()
    author = models.ForeignKey('auth.User', related_name='%(class)ss', on_delete=models.CASCADE)
    revised_at = models.DateTimeField()
    summary = models.CharField(max_length=300, blank=True)
    text = models.TextField(blank=True)

    approved = models.BooleanField(default=False, db_index=True)
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    approved_at = models.DateTimeField(null=True, blank=True)

    by_email = models.BooleanField(default=False)  # true, if edited by email
    email_address = models.EmailField(null=True, blank=True)

    # Question-specific fields
    title = models.CharField(max_length=300, blank=True, default='')
    tagnames = models.CharField(max_length=125, blank=True, default='')
    is_anonymous = models.BooleanField(default=False)
    ip_addr = models.GenericIPAddressField(max_length=45, default='0.0.0.0', db_index=True)

    objects = PostRevisionManager()

    class Meta:
        # INFO: This `unique_together` constraint might be problematic for
        #       databases in which
        #       2+ NULLs cannot be stored in an UNIQUE column.
        #       As far as I know MySQL, PostgreSQL and SQLite allow that so
        #       we're on the safe side.
        unique_together = ('post', 'revision')
        ordering = ('-revision',)
        app_label = 'askbot'
        verbose_name = _("post revision")
        verbose_name_plural = _("post revisions")

    def can_be_seen_by(self, user):
        """Returns `True` if user can see revision.

        Group membership checks are not done here,
        because we want this method to not incur additional DB queries.

        Therefore, this method  should not be used directly,
        but only after the parent posts are filtered by groups.
        """
        is_published = self.revision != 0

        if is_published:
            return True
        
        if not user or user.is_anonymous:
            return False

        # revision is moderated, can be seen by mods or revision authors
        return user.is_admin_or_mod() or self.author_id == user.pk
        

    def place_on_moderation_queue(self):
        """Creates moderation queue
        Activity items with recipients
        """
        if self.post.revisions.count() == 1:
            if self.revision == 0:
                # call below hides post from the display to the general public
                self.post.set_is_approved(False)
            activity_type = const.TYPE_ACTIVITY_MODERATED_NEW_POST
        else:
            activity_type = const.TYPE_ACTIVITY_MODERATED_POST_EDIT

        # Activity instance is the actual queue item
        from askbot.models import Activity
        content_type = ContentType.objects.get_for_model(self)
        try:
            activity = Activity.objects.get(
                                        activity_type=activity_type,
                                        object_id=self.id,
                                        content_type=content_type
                                    )
        except Activity.DoesNotExist:
            activity = Activity(
                            user=self.author,
                            content_object=self,
                            activity_type=activity_type,
                            question=self.get_origin_post()
                        )
            activity.save()

        activity.add_recipients(self.post.get_moderators())

        # give message to the poster
        # TODO: move this out as signal handler
        if askbot_settings.CONTENT_MODERATION_MODE == 'premoderation':
            if self.by_email:
                # TODO: move this to the askbot.mail module
                from askbot.mail import send_mail
                email_context = {
                    'site': askbot_settings.APP_SHORT_NAME
                }
                body_text = _(
                    'Thank you for your post to %(site)s. '
                    'It will be published after the moderators review.'
                ) % email_context
                send_mail(
                    subject_line=_('your post to %(site)s') % email_context,
                    body_text=body_text,
                    recipient_list=[self.author.email],
                )

            else:
                message = _(
                    'Your post was placed on the moderation queue '
                    'and will be published after the moderator approval.'
                )
                self.author.message_set.create(message=message)

    def should_notify_author_about_publishing(self, was_approved=False):
        """True if author should get email about making own post"""
        if was_approved and not self.by_email:
            return False

        schedule = askbot_settings.SELF_NOTIFY_EMAILED_POST_AUTHOR_WHEN
        if schedule == const.NEVER:
            return False
        if schedule == const.FOR_FIRST_REVISION:
            return self.revision == 1
        if schedule == const.FOR_ANY_REVISION:
            return True
        raise ValueError()

    def __str__(self):
        return '%s - revision %s of %s' % (self.post.post_type, self.revision,
                                            self.title)

    def parent(self):
        return self.post

    def clean(self):
        "Internal cleaning method, called from self.save() by self.full_clean()"
        if not self.post:
            raise ValidationError('Post field has to be set.')

    def save(self, **kwargs):
        if not self.ip_addr:
            self.ip_addr = '0.0.0.0'
        self.full_clean()
        super(PostRevision, self).save(**kwargs)

    def get_absolute_url(self):

        if askbot.is_multilingual():
            request_language = get_language()
            activate_language(self.post.language_code)

        if self.post.is_question():
            url = reverse('question_revisions', args=(self.post.id,))
        elif self.post.is_answer():
            url = reverse('answer_revisions', kwargs={'id': self.post.id})
        else:
            url = self.post.get_absolute_url()

        if askbot.is_multilingual():
            activate_language(request_language)

        return url

    def get_action_label(self):
        if self.revision == 0:
            return _('proposed an edit')
        if self.revision == 1:
            if self.post.post_type == 'question':
                return html_utils.escape(askbot_settings.WORDS_ASKED)
            if self.post.post_type == 'answer':
                return html_utils.escape(askbot_settings.WORDS_ANSWERED)
            return _('posted')
        return _('updated')

    def get_question_title(self):
        # INFO: ack-grepping shows that it's only used for Questions,
        #       so there's no code for Answers
        return self.question.thread.title

    def get_origin_post(self):
        """Same as Post.get_origin_post()"""
        return self.post.get_origin_post()

    def get_original_post_author(self):
        """Returns original author of the post"""
        if self.post.post_type in ('question', 'answer'):
            return self.post.author
        return None

    @property
    def html(self, **kwargs):
        sanitized_html = markup.markdown_input_converter(self.text)
        if self.post.is_question():
            return sanitize_html(self.QUESTION_REVISION_TEMPLATE_NO_TAGS % {
                'title': self.title,
                'html': sanitized_html
            })
        return sanitized_html

    def get_snippet(self, max_length=120):
        """a little simpler than as Post.get_snippet"""
        return '<p>' + html_utils.strip_tags(self.html)[:max_length] + '</p>'


class PostFlagReason(models.Model):
    added_at = models.DateTimeField()
    author = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    title = models.CharField(max_length=128)
    details = models.ForeignKey(Post, related_name='post_reject_reasons', on_delete=models.CASCADE)

    class Meta:
        app_label = 'askbot'
        verbose_name = _("post flag reason")
        verbose_name_plural = _("post flag reasons")


class DraftAnswer(DraftContent):
    """Provides space for draft answers,
    note that unlike ``AnonymousAnswer`` the foreign key
    is going to ``Thread`` as it should.
    """
    thread = models.ForeignKey('Thread', related_name='draft_answers', on_delete=models.CASCADE)
    author = models.ForeignKey(User, related_name='draft_answers', on_delete=models.CASCADE)

    class Meta:
        app_label = 'askbot'


class AnonymousAnswer(AnonymousContent):
    """Todo: re-route the foreign key to ``Thread``"""
    question = models.ForeignKey(Post, related_name='anonymous_answers', on_delete=models.CASCADE)

    def publish(self, user):
        added_at = timezone.now()
        try:
            user.assert_can_post_text(self.text)

        except django_exceptions.PermissionDenied:
            # delete previous draft questions (only one is allowed anyway)
            thread = self.question.thread
            prev_drafts = DraftAnswer.objects.filter(author=user, thread=thread)
            prev_drafts.delete()
            # convert this question to draft
            DraftAnswer.objects.create(thread=thread, author=user,
                                       text=self.text)

        else:
            Post.objects.create_new_answer(
                thread=self.question.thread, author=user, added_at=added_at,
                wiki=self.wiki, text=self.text, ip_addr=self.ip_addr)
            self.question.thread.reset_cached_data()

        finally:
            self.delete()
