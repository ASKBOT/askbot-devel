import datetime
import operator
import re

from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.core import cache  # import cache, not from cache import cache, to be able to monkey-patch cache.cache in test cases
from django.core.urlresolvers import reverse
from django.utils.hashcompat import md5_constructor
from django.utils.translation import ugettext as _

import askbot
import askbot.conf
from askbot.models.tag import Tag
from askbot.models.base import AnonymousContent
from askbot.models.post import Post, PostRevision
from askbot.models import signals
from askbot import const
from askbot.utils.lists import LazyList
from askbot.utils import mysql
from askbot.utils.slug import slugify
from askbot.skins.loaders import get_template #jinja2 template loading enviroment
from askbot.search.state_manager import DummySearchState


class ThreadManager(models.Manager):
    def get_tag_summary_from_threads(self, threads):
        """returns a humanized string containing up to
        five most frequently used
        unique tags coming from the ``threads``.
        Variable ``threads`` is an iterable of
        :class:`~askbot.models.Thread` model objects.

        This is not implemented yet as a query set method,
        because it is used on a list.
        """
        # TODO: In Python 2.6 there is collections.Counter() thing which would be very useful here
        # TODO: In Python 2.5 there is `defaultdict` which already would be an improvement
        tag_counts = dict()
        for thread in threads:
            for tag_name in thread.get_tag_names():
                if tag_name in tag_counts:
                    tag_counts[tag_name] += 1
                else:
                    tag_counts[tag_name] = 1
        tag_list = tag_counts.keys()
        tag_list.sort(key=lambda t: tag_counts[t], reverse=True)

        #note that double quote placement is important here
        if len(tag_list) == 1:
            last_topic = '"'
        elif len(tag_list) <= 5:
            last_topic = _('" and "%s"') % tag_list.pop()
        else:
            tag_list = tag_list[:5]
            last_topic = _('" and more')

        return '"' + '", "'.join(tag_list) + last_topic

    def create(self, *args, **kwargs):
        raise NotImplementedError

    def create_new(self, title, author, added_at, wiki, text, tagnames=None, is_anonymous=False):
        # TODO: Some of this code will go to Post.objects.create_new

        thread = super(
            ThreadManager,
            self
        ).create(
            title=title,
            tagnames=tagnames,
            last_activity_at=added_at,
            last_activity_by=author
        )

        question = Post(
            post_type='question',
            thread=thread,
            author = author,
            added_at = added_at,
            wiki = wiki,
            is_anonymous = is_anonymous,
            #html field is denormalized in .save() call
            text = text,
            #summary field is denormalized in .save() call
        )
        if question.wiki:
            #DATED COMMENT
            #todo: this is confusing - last_edited_at field
            #is used as an indicator whether question has been edited
            #but in principle, post creation should count as edit as well
            question.last_edited_by = question.author
            question.last_edited_at = added_at
            question.wikified_at = added_at

        question.parse_and_save(author = author)

        question.add_revision(
            author = author,
            is_anonymous = is_anonymous,
            text = text,
            comment = const.POST_STATUS['default_version'],
            revised_at = added_at,
        )

        # INFO: Question has to be saved before update_tags() is called
        thread.update_tags(tagnames = tagnames, user = author, timestamp = added_at)

        return thread

    def get_for_query(self, search_query, qs=None):
        """returns a query set of questions,
        matching the full text query
        """
        if not qs:
            qs = self.all()
#        if getattr(settings, 'USE_SPHINX_SEARCH', False):
#            matching_questions = Question.sphinx_search.query(search_query)
#            question_ids = [q.id for q in matching_questions]
#            return qs.filter(posts__post_type='question', posts__deleted=False, posts__self_question_id__in=question_ids)
        if askbot.get_database_engine_name().endswith('mysql') \
            and mysql.supports_full_text_search():
            return qs.filter(
                models.Q(title__search = search_query) |
                models.Q(tagnames__search = search_query) |
                models.Q(posts__deleted=False, posts__text__search = search_query)
            )
        elif 'postgresql_psycopg2' in askbot.get_database_engine_name():
            rank_clause = "ts_rank(askbot_thread.text_search_vector, plainto_tsquery(%s))"
            search_query = '&'.join(search_query.split())
            extra_params = (search_query,)
            extra_kwargs = {
                'select': {'relevance': rank_clause},
                'where': ['askbot_thread.text_search_vector @@ plainto_tsquery(%s)'],
                'params': extra_params,
                'select_params': extra_params,
            }
            return qs.extra(**extra_kwargs)
        else:
            return qs.filter(
                models.Q(title__icontains=search_query) |
                models.Q(tagnames__icontains=search_query) |
                models.Q(posts__deleted=False, posts__text__icontains = search_query)
            )


    def run_advanced_search(self, request_user, search_state):  # TODO: !! review, fix, and write tests for this
        """
        all parameters are guaranteed to be clean
        however may not relate to database - in that case
        a relvant filter will be silently dropped

        """
        from askbot.conf import settings as askbot_settings # Avoid circular import

        # TODO: add a possibility to see deleted questions
        qs = self.filter(posts__post_type='question', posts__deleted=False) # (***) brings `askbot_post` into the SQL query, see the ordering section below

        meta_data = {}

        if search_state.stripped_query:
            qs = self.get_for_query(search_query=search_state.stripped_query, qs=qs)
        if search_state.query_title:
            qs = qs.filter(title__icontains = search_state.query_title)
        if search_state.query_users:
            query_users = User.objects.filter(username__in=search_state.query_users)
            if query_users:
                qs = qs.filter(posts__post_type='question', posts__author__in=query_users) # TODO: unify with search_state.author ?

        tags = search_state.unified_tags()
        for tag in tags:
            qs = qs.filter(tags__name=tag) # Tags or AND-ed here, not OR-ed (i.e. we fetch only threads with all tags)

        if search_state.scope == 'unanswered':
            qs = qs.filter(closed = False) # Do not show closed questions in unanswered section
            if askbot_settings.UNANSWERED_QUESTION_MEANING == 'NO_ANSWERS':
                qs = qs.filter(answer_count=0) # TODO: expand for different meanings of this
            elif askbot_settings.UNANSWERED_QUESTION_MEANING == 'NO_ACCEPTED_ANSWERS':
                qs = qs.filter(accepted_answer__isnull=True)
            elif askbot_settings.UNANSWERED_QUESTION_MEANING == 'NO_UPVOTED_ANSWERS':
                raise NotImplementedError()
            else:
                raise Exception('UNANSWERED_QUESTION_MEANING setting is wrong')

        elif search_state.scope == 'favorite':
            favorite_filter = models.Q(favorited_by=request_user)
            if 'followit' in settings.INSTALLED_APPS:
                followed_users = request_user.get_followed_users()
                favorite_filter |= models.Q(posts__post_type__in=('question', 'answer'), posts__author__in=followed_users)
            qs = qs.filter(favorite_filter)

        #user contributed questions & answers
        if search_state.author:
            try:
                # TODO: maybe support selection by multiple authors
                u = User.objects.get(id=int(search_state.author))
            except User.DoesNotExist:
                meta_data['author_name'] = None
            else:
                qs = qs.filter(posts__post_type__in=('question', 'answer'), posts__author=u, posts__deleted=False)
                meta_data['author_name'] = u.username

        #get users tag filters
        if request_user and request_user.is_authenticated():
            #mark questions tagged with interesting tags
            #a kind of fancy annotation, would be nice to avoid it
            interesting_tags = Tag.objects.filter(user_selections__user=request_user, user_selections__reason='good')
            ignored_tags = Tag.objects.filter(user_selections__user=request_user, user_selections__reason='bad')

            meta_data['interesting_tag_names'] = [tag.name for tag in interesting_tags]
            meta_data['ignored_tag_names'] = [tag.name for tag in ignored_tags]

            if request_user.display_tag_filter_strategy == const.INCLUDE_INTERESTING and (interesting_tags or request_user.has_interesting_wildcard_tags()):
                #filter by interesting tags only
                interesting_tag_filter = models.Q(tags__in=interesting_tags)
                if request_user.has_interesting_wildcard_tags():
                    interesting_wildcards = request_user.interesting_tags.split()
                    extra_interesting_tags = Tag.objects.get_by_wildcards(interesting_wildcards)
                    interesting_tag_filter |= models.Q(tags__in=extra_interesting_tags)
                qs = qs.filter(interesting_tag_filter)

            # get the list of interesting and ignored tags (interesting_tag_names, ignored_tag_names) = (None, None)
            if request_user.display_tag_filter_strategy == const.EXCLUDE_IGNORED and (ignored_tags or request_user.has_ignored_wildcard_tags()):
                #exclude ignored tags if the user wants to
                qs = qs.exclude(tags__in=ignored_tags)
                if request_user.has_ignored_wildcard_tags():
                    ignored_wildcards = request_user.ignored_tags.split()
                    extra_ignored_tags = Tag.objects.get_by_wildcards(ignored_wildcards)
                    qs = qs.exclude(tags__in = extra_ignored_tags)

            if askbot_settings.USE_WILDCARD_TAGS:
                meta_data['interesting_tag_names'].extend(request_user.interesting_tags.split())
                meta_data['ignored_tag_names'].extend(request_user.ignored_tags.split())

        QUESTION_ORDER_BY_MAP = {
            'age-desc': '-added_at',
            'age-asc': 'added_at',
            'activity-desc': '-last_activity_at',
            'activity-asc': 'last_activity_at',
            'answers-desc': '-answer_count',
            'answers-asc': 'answer_count',
            'votes-desc': '-score',
            'votes-asc': 'score',

            'relevance-desc': '-relevance', # special Postgresql-specific ordering, 'relevance' quaso-column is added by get_for_query()
        }
        orderby = QUESTION_ORDER_BY_MAP[search_state.sort]
        qs = qs.extra(order_by=[orderby])

        # HACK: We add 'ordering_key' column as an alias and order by it, because when distict() is used,
        #       qs.extra(order_by=[orderby,]) is lost if only `orderby` column is from askbot_post!
        #       Removing distinct() from the queryset fixes the problem, but we have to use it here.
        # UPDATE: Apparently we don't need distinct, the query don't duplicate Thread rows!
        # qs = qs.extra(select={'ordering_key': orderby.lstrip('-')}, order_by=['-ordering_key' if orderby.startswith('-') else 'ordering_key'])
        # qs = qs.distinct()

        qs = qs.only('id', 'title', 'view_count', 'answer_count', 'last_activity_at', 'last_activity_by', 'closed', 'tagnames', 'accepted_answer')

        #print qs.query

        return qs.distinct(), meta_data

    def precache_view_data_hack(self, threads):
        # TODO: Re-enable this when we have a good test cases to verify that it works properly.
        #
        #       E.g.: - make sure that not precaching give threads never increase # of db queries for the main page
        #             - make sure that it really works, i.e. stuff for non-cached threads is fetched properly
        # Precache data only for non-cached threads - only those will be rendered
        #threads = [thread for thread in threads if not thread.summary_html_cached()]

        page_questions = Post.objects.filter(post_type='question', thread__in=[obj.id for obj in threads])\
                            .only('id', 'thread', 'score', 'is_anonymous', 'summary', 'post_type', 'deleted') # pick only the used fields
        page_question_map = {}
        for pq in page_questions:
            page_question_map[pq.thread_id] = pq
        for thread in threads:
            thread._question_cache = page_question_map[thread.id]

        last_activity_by_users = User.objects.filter(id__in=[obj.last_activity_by_id for obj in threads])\
                                    .only('id', 'username', 'country', 'show_country')
        user_map = {}
        for la_user in last_activity_by_users:
            user_map[la_user.id] = la_user
        for thread in threads:
            thread._last_activity_by_cache = user_map[thread.last_activity_by_id]


    #todo: this function is similar to get_response_receivers - profile this function against the other one
    def get_thread_contributors(self, thread_list):
        """Returns query set of Thread contributors"""
        # INFO: Evaluate this query to avoid subquery in the subsequent query below (At least MySQL can be awfully slow on subqueries)
        u_id = list(Post.objects.filter(post_type__in=('question', 'answer'), thread__in=thread_list).values_list('author', flat=True))

        #todo: this does not belong gere - here we select users with real faces
        #first and limit the number of users in the result for display
        #on the main page, we might also want to completely hide fake gravatars
        #and show only real images and the visitors - even if he does not have
        #a real image and try to prompt him/her to upload a picture
        from askbot.conf import settings as askbot_settings
        avatar_limit = askbot_settings.SIDEBAR_MAIN_AVATAR_LIMIT
        contributors = User.objects.filter(id__in=u_id).order_by('avatar_type', '?')[:avatar_limit]
        return contributors


class Thread(models.Model):
    SUMMARY_CACHE_KEY_TPL = 'thread-question-summary-%d'
    ANSWER_LIST_KEY_TPL = 'thread-answer-list-%d'

    title = models.CharField(max_length=300)

    tags = models.ManyToManyField('Tag', related_name='threads')

    # Denormalised data, transplanted from Question
    tagnames = models.CharField(max_length=125)
    view_count = models.PositiveIntegerField(default=0)
    favourite_count = models.PositiveIntegerField(default=0)
    answer_count = models.PositiveIntegerField(default=0)
    last_activity_at = models.DateTimeField(default=datetime.datetime.now)
    last_activity_by = models.ForeignKey(User, related_name='unused_last_active_in_threads')

    followed_by     = models.ManyToManyField(User, related_name='followed_threads')
    favorited_by    = models.ManyToManyField(User, through='FavoriteQuestion', related_name='unused_favorite_threads')

    closed          = models.BooleanField(default=False)
    closed_by       = models.ForeignKey(User, null=True, blank=True) #, related_name='closed_questions')
    closed_at       = models.DateTimeField(null=True, blank=True)
    close_reason    = models.SmallIntegerField(
                                            choices=const.CLOSE_REASONS,
                                            null=True,
                                            blank=True
                                        )

    accepted_answer = models.ForeignKey(Post, null=True, blank=True, related_name='+')
    answer_accepted_at = models.DateTimeField(null=True, blank=True)
    added_at = models.DateTimeField(default = datetime.datetime.now)

    score = models.IntegerField(default = 0)

    objects = ThreadManager()
    
    class Meta:
        app_label = 'askbot'

    def _question_post(self, refresh=False):
        if refresh and hasattr(self, '_question_cache'):
            delattr(self, '_question_cache')
        post = getattr(self, '_question_cache', None)
        if post:
            return post
        self._question_cache = Post.objects.get(post_type='question', thread=self)
        return self._question_cache

    def get_absolute_url(self):
        return self._question_post().get_absolute_url(thread = self)
        #question_id = self._question_post().id
        #return reverse('question', args = [question_id]) + slugify(self.title)

    def update_favorite_count(self):
        self.favourite_count = FavoriteQuestion.objects.filter(thread=self).count()
        self.save()

    def update_answer_count(self):
        self.answer_count = self.get_answers().count()
        self.save()

    def increase_view_count(self, increment=1):
        qset = Thread.objects.filter(id=self.id)
        qset.update(view_count=models.F('view_count') + increment)
        self.view_count = qset.values('view_count')[0]['view_count'] # get the new view_count back because other pieces of code relies on such behaviour
        ####################################################################
        self.update_summary_html() # regenerate question/thread summary html
        ####################################################################

    def set_closed_status(self, closed, closed_by, closed_at, close_reason):
        self.closed = closed
        self.closed_by = closed_by
        self.closed_at = closed_at
        self.close_reason = close_reason
        self.save()
        self.invalidate_cached_data()

    def set_accepted_answer(self, answer, timestamp):
        if answer and answer.thread != self:
            raise ValueError("Answer doesn't belong to this thread")
        self.accepted_answer = answer
        self.answer_accepted_at = timestamp
        self.save()

    def set_last_activity(self, last_activity_at, last_activity_by):
        self.last_activity_at = last_activity_at
        self.last_activity_by = last_activity_by
        self.save()
        ####################################################################
        self.update_summary_html() # regenerate question/thread summary html
        ####################################################################

    def get_tag_names(self):
        "Creates a list of Tag names from the ``tagnames`` attribute."
        if self.tagnames.strip() == '':
            return list()
        else:
            return self.tagnames.split(u' ')

    def get_title(self, question=None):
        if not question:
            question = self._question_post() # allow for optimization if the caller has already fetched the question post for this thread
        if self.closed:
            attr = const.POST_STATUS['closed']
        elif question.deleted:
            attr = const.POST_STATUS['deleted']
        else:
            attr = None
        if attr is not None:
            return u'%s %s' % (self.title, attr)
        else:
            return self.title

    def tagname_meta_generator(self):
        return u','.join([unicode(tag) for tag in self.get_tag_names()])

    def all_answers(self):
        return self.posts.get_answers()

    def get_answers(self, user=None):
        """returns query set for answers to this question
        that may be shown to the given user
        """
        if user is None or user.is_anonymous():
            return self.posts.get_answers().filter(deleted=False)
        else:
            if user.is_administrator() or user.is_moderator():
                return self.posts.get_answers()
            else:
                return self.posts.get_answers().filter(
                                models.Q(deleted = False) | models.Q(author = user) \
                                | models.Q(deleted_by = user)
                            )

    def invalidate_cached_thread_content_fragment(self):
        cache.cache.delete(self.SUMMARY_CACHE_KEY_TPL % self.id)

    def get_post_data_cache_key(self, sort_method = None):
        return 'thread-data-%s-%s' % (self.id, sort_method)

    def invalidate_cached_post_data(self):
        """needs to be called when anything notable 
        changes in the post data - on votes, adding,
        deleting, editing content"""
        #we can call delete_many() here if using Django > 1.2
        for sort_method in const.ANSWER_SORT_METHODS:
            cache.cache.delete(self.get_post_data_cache_key(sort_method))

    def invalidate_cached_data(self):
        self.invalidate_cached_post_data()
        #self.invalidate_cached_thread_content_fragment()
        self.update_summary_html()

    def get_cached_post_data(self, sort_method = None):
        """returns cached post data, as calculated by
        the method get_post_data()"""
        key = self.get_post_data_cache_key(sort_method)
        post_data = cache.cache.get(key)
        if not post_data:
            post_data = self.get_post_data(sort_method)
            cache.cache.set(key, post_data, const.LONG_TIME)
        return post_data

    def get_post_data(self, sort_method = None):
        """returns question, answers as list and a list of post ids
        for the given thread
        the returned posts are pre-stuffed with the comments
        all (both posts and the comments sorted in the correct
        order)
        """
        thread_posts = self.posts.all().order_by(
                    {
                        "latest":"-added_at",
                        "oldest":"added_at",
                        "votes":"-score"
                    }[sort_method]
                )
        #1) collect question, answer and comment posts and list of post id's
        answers = list()
        post_map = dict()
        comment_map = dict()
        post_to_author = dict()
        question_post = None
        for post in thread_posts:
            #pass through only deleted question posts
            if post.deleted and post.post_type != 'question':
                continue

            post_to_author[post.id] = post.author_id

            if post.post_type == 'answer':
                answers.append(post)
                post_map[post.id] = post
            elif post.post_type == 'comment':
                if post.parent_id not in comment_map:
                    comment_map[post.parent_id] = list()
                comment_map[post.parent_id].append(post)
            elif post.post_type == 'question':
                assert(question_post == None)
                post_map[post.id] = post
                question_post = post

        #2) sort comments in the temporal order
        for comment_list in comment_map.values():
            comment_list.sort(key=operator.attrgetter('added_at'))

        #3) attach comments to question and the answers
        for post_id, comment_list in comment_map.items():
            try:
                post_map[post_id].set_cached_comments(comment_list)
            except KeyError:
                pass#comment to deleted answer - don't want it

        if self.has_accepted_answer() and self.accepted_answer.deleted == False:
            #Put the accepted answer to front
            #the second check is for the case when accepted answer is deleted
            accepted_answer = post_map[self.accepted_answer_id]
            answers.remove(accepted_answer)
            answers.insert(0, accepted_answer)

        return (question_post, answers, post_to_author)

    def has_accepted_answer(self):
        return self.accepted_answer_id != None

    def get_similarity(self, other_thread = None):
        """return number of tags in the other question
        that overlap with the current question (self)
        """
        my_tags = set(self.get_tag_names())
        others_tags = set(other_thread.get_tag_names())
        return len(my_tags & others_tags)

    def get_similar_threads(self):
        """
        Get 10 similar threads for given one.
        Threads with the individual tags will be added to list if above questions are not full.

        This function has a limitation that it will
        retrieve only 100 records then select 10 most similar
        from that list as querying entire database may
        be very expensive - this function will benefit from
        some sort of optimization
        """

        def get_data():
            tags_list = self.get_tag_names()
            similar_threads = Thread.objects.filter(
                                        tags__name__in=tags_list
                                    ).exclude(
                                        id = self.id
                                    ).exclude(
                                        posts__post_type='question',
                                        posts__deleted = True
                                    ).distinct()[:100]
            similar_threads = list(similar_threads)

            for thread in similar_threads:
                thread.similarity = self.get_similarity(other_thread=thread)

            similar_threads.sort(key=operator.attrgetter('similarity'), reverse=True)
            similar_threads = similar_threads[:10]

            # Denormalize questions to speed up template rendering
            thread_map = dict([(thread.id, thread) for thread in similar_threads])
            questions = Post.objects.get_questions()
            questions = questions.select_related('thread').filter(thread__in=similar_threads)
            for q in questions:
                thread_map[q.thread_id].question_denorm = q

            # Postprocess data
            similar_threads = [
                {
                    'url': thread.question_denorm.get_absolute_url(),
                    'title': thread.get_title(thread.question_denorm)
                } for thread in similar_threads
            ]
            return similar_threads

        def get_cached_data():
            """similar thread data will expire
            with the default expiration delay
            """
            key = 'similar-threads-%s' % self.id
            data = cache.cache.get(key)
            if data is None:
                data = get_data()
                cache.cache.set(key, data)
            return data

        return LazyList(get_cached_data)

    def remove_author_anonymity(self):
        """removes anonymous flag from the question
        and all its revisions
        the function calls update method to make sure that
        signals are not called
        """
        #note: see note for the is_anonymous field
        #it is important that update method is called - not save,
        #because we do not want the signals to fire here
        thread_question = self._question_post()
        Post.objects.filter(id=thread_question.id).update(is_anonymous=False)
        thread_question.revisions.all().update(is_anonymous=False)

    def is_followed_by(self, user = None):
        """True if thread is followed by user"""
        if user and user.is_authenticated():
            return self.followed_by.filter(id = user.id).count() > 0
        return False

    def update_tags(self, tagnames = None, user = None, timestamp = None):
        """
        Updates Tag associations for a thread to match the given
        tagname string.

        When tags are removed and their use count hits 0 - the tag is
        automatically deleted.

        When an added tag does not exist - it is created

        Tag use counts are recalculated

        A signal tags updated is sent

        *IMPORTANT*: self._question_post() has to exist when update_tags() is called!
        """
        previous_tags = list(self.tags.all())

        previous_tagnames = set([tag.name for tag in previous_tags])
        updated_tagnames = set(t for t in tagnames.split(' '))

        removed_tagnames = previous_tagnames - updated_tagnames
        added_tagnames = updated_tagnames - previous_tagnames

        modified_tags = list()
        #remove tags from the question's tags many2many relation
        if removed_tagnames:
            removed_tags = [tag for tag in previous_tags if tag.name in removed_tagnames]
            self.tags.remove(*removed_tags)

            #if any of the removed tags reached use count == 1 that means they must be deleted
            for tag in removed_tags:
                if tag.used_count == 1:
                    #we won't modify used count b/c it's done below anyway
                    removed_tags.remove(tag)
                    #todo - do we need to use fields deleted_by and deleted_at?
                    tag.delete()#auto-delete tags whose use count dwindled

            #remember modified tags, we'll need to update use counts on them
            modified_tags = removed_tags

        #add new tags to the relation
        if added_tagnames:
            #find reused tags
            reused_tags = Tag.objects.filter(name__in = added_tagnames)
            #undelete them, because we are using them
            reused_count = reused_tags.update(
                                    deleted = False,
                                    deleted_by = None,
                                    deleted_at = None
                                )
            #if there are brand new tags, create them and finalize the added tag list
            if reused_count < len(added_tagnames):
                added_tags = list(reused_tags)

                reused_tagnames = set([tag.name for tag in reused_tags])
                new_tagnames = added_tagnames - reused_tagnames
                for name in new_tagnames:
                    new_tag = Tag.objects.create(
                                            name = name,
                                            created_by = user,
                                            used_count = 1
                                        )
                    added_tags.append(new_tag)
            else:
                added_tags = reused_tags

            #finally add tags to the relation and extend the modified list
            self.tags.add(*added_tags)
            modified_tags.extend(added_tags)

        ####################################################################
        self.update_summary_html() # regenerate question/thread summary html
        ####################################################################

        #if there are any modified tags, update their use counts
        if modified_tags:
            Tag.objects.update_use_counts(modified_tags)
            signals.tags_updated.send(None,
                                thread = self,
                                tags = modified_tags,
                                user = user,
                                timestamp = timestamp
                            )
            return True

        return False

    def retag(self, retagged_by=None, retagged_at=None, tagnames=None, silent=False):
        if None in (retagged_by, retagged_at, tagnames):
            raise Exception('arguments retagged_at, retagged_by and tagnames are required')

        thread_question = self._question_post()

        self.tagnames = tagnames
        self.save()

        # Update the Question itself
        if silent == False:
            thread_question.last_edited_at = retagged_at
            #thread_question.thread.last_activity_at = retagged_at
            thread_question.last_edited_by = retagged_by
            #thread_question.thread.last_activity_by = retagged_by
            thread_question.save()

        # Update the Thread's tag associations
        self.update_tags(tagnames=tagnames, user=retagged_by, timestamp=retagged_at)

        # Create a new revision
        latest_revision = thread_question.get_latest_revision()
        PostRevision.objects.create_question_revision(
            post = thread_question,
            title      = latest_revision.title,
            author     = retagged_by,
            revised_at = retagged_at,
            tagnames   = tagnames,
            summary    = const.POST_STATUS['retagged'],
            text       = latest_revision.text
        )

    def has_favorite_by_user(self, user):
        if not user.is_authenticated():
            return False

        return FavoriteQuestion.objects.filter(thread=self, user=user).exists()

    def get_last_update_info(self):
        posts = list(self.posts.select_related('author', 'last_edited_by'))

        last_updated_at = posts[0].added_at
        last_updated_by = posts[0].author

        for post in posts:
            last_updated_at, last_updated_by = max((last_updated_at, last_updated_by), (post.added_at, post.author))
            if post.last_edited_at:
                last_updated_at, last_updated_by = max((last_updated_at, last_updated_by), (post.last_edited_at, post.last_edited_by))

        return last_updated_at, last_updated_by

    def get_summary_html(self, search_state):
        html = self.get_cached_summary_html()
        if not html:
            html = self.update_summary_html()

        # use `<<<` and `>>>` because they cannot be confused with user input
        # - if user accidentialy types <<<tag-name>>> into question title or body,
        # then in html it'll become escaped like this: &lt;&lt;&lt;tag-name&gt;&gt;&gt;
        regex = re.compile(
            r'<<<(%s)>>>' % const.TAG_REGEX_BARE,
            re.UNICODE
        )

        while True:
            match = regex.search(html)
            if not match:
                break
            seq = match.group(0)  # e.g "<<<my-tag>>>"
            tag = match.group(1)  # e.g "my-tag"
            full_url = search_state.add_tag(tag).full_url()
            html = html.replace(seq, full_url)

        return html

    def get_cached_summary_html(self):
        return cache.cache.get(self.SUMMARY_CACHE_KEY_TPL % self.id)

    def update_summary_html(self):
        context = {
            'thread': self,
            'question': self._question_post(refresh=True),  # fetch new question post to make sure we're up-to-date
            'search_state': DummySearchState(),
        }
        html = get_template('widgets/question_summary.html').render(context)
        # INFO: Timeout is set to 30 days:
        # * timeout=0/None is not a reliable cross-backend way to set infinite timeout
        # * We probably don't need to pollute the cache with threads older than 30 days
        # * Additionally, Memcached treats timeouts > 30day as dates (https://code.djangoproject.com/browser/django/tags/releases/1.3/django/core/cache/backends/memcached.py#L36),
        #   which probably doesn't break anything but if we can stick to 30 days then let's stick to it
        cache.cache.set(
            self.SUMMARY_CACHE_KEY_TPL % self.id,
            html,
            timeout=const.LONG_TIME
        )
        return html

    def summary_html_cached(self):
        return cache.cache.has_key(self.SUMMARY_CACHE_KEY_TPL % self.id)

class QuestionView(models.Model):
    question = models.ForeignKey(Post, related_name='viewed')
    who = models.ForeignKey(User, related_name='question_views')
    when = models.DateTimeField()

    class Meta:
        app_label = 'askbot'

class FavoriteQuestion(models.Model):
    """A favorite Question of a User."""
    thread        = models.ForeignKey(Thread)
    user          = models.ForeignKey(User, related_name='user_favorite_questions')
    added_at      = models.DateTimeField(default=datetime.datetime.now)

    class Meta:
        app_label = 'askbot'
        db_table = u'favorite_question'
    def __unicode__(self):
        return '[%s] favorited at %s' %(self.user, self.added_at)


class AnonymousQuestion(AnonymousContent):
    """question that was asked before logging in
    maybe the name is a little misleading, the user still
    may or may not want to stay anonymous after the question
    is published
    """
    title = models.CharField(max_length=300)
    tagnames = models.CharField(max_length=125)
    is_anonymous = models.BooleanField(default=False)

    def publish(self,user):
        added_at = datetime.datetime.now()
        Thread.objects.create_new(
            title = self.title,
            added_at = added_at,
            author = user,
            wiki = self.wiki,
            is_anonymous = self.is_anonymous,
            tagnames = self.tagnames,
            text = self.text,
        )
        self.delete()
