# encoding:utf-8
"""
:synopsis: views "read-only" for main textual content

By main textual content is meant - text of Questions, Answers and Comments.
The "read-only" requirement here is not 100% strict, as for example "question" view does
allow adding new comments via Ajax form post.
"""
import datetime
import logging
import urllib
import operator
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.http import HttpResponse
from django.http import Http404
from django.http import HttpResponseNotAllowed
from django.http import HttpResponseBadRequest
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.template.loader import get_template
from django.template import RequestContext
from django.utils import simplejson
from django.utils.html import escape
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext
from django.utils import translation
from django.views.decorators import csrf
from django.core.urlresolvers import reverse
from django.core import exceptions as django_exceptions
from django.contrib.humanize.templatetags import humanize
from django.http import QueryDict
from django.conf import settings as django_settings

import askbot
from askbot import exceptions
from askbot.utils.diff import textDiff as htmldiff
from askbot.forms import AnswerForm
from askbot.forms import ShowQuestionForm
from askbot.forms import GetUserItemsForm
from askbot.forms import GetDataForPostForm
from askbot.utils.loading import load_module
from askbot import conf
from askbot import models
from askbot import schedules
from askbot.models.tag import Tag
from askbot import const
from askbot.startup_procedures import domain_is_bad
from askbot.utils import functions
from askbot.utils.html import sanitize_html
from askbot.utils.decorators import anonymous_forbidden, ajax_only, get_only
from askbot.search.state_manager import SearchState, DummySearchState
from askbot.templatetags import extra_tags
from askbot.conf import settings as askbot_settings
from askbot.views import context

# used in index page
#todo: - take these out of const or settings
from askbot.models import Post, Vote

INDEX_PAGE_SIZE = 30
INDEX_AWARD_SIZE = 15
INDEX_TAGS_SIZE = 25
# used in tags list
DEFAULT_PAGE_SIZE = 60
# used in questions
# used in answers

#refactor? - we have these
#views that generate a listing of questions in one way or another:
#index, unanswered, questions, search, tag
#should we dry them up?
#related topics - information drill-down, search refinement

def index(request):#generates front page - shows listing of questions sorted in various ways
    """index view mapped to the root url of the Q&A site
    """
    return HttpResponseRedirect(reverse('questions'))

def questions(request, **kwargs):
    """
    List of Questions, Tagged questions, and Unanswered questions.
    matching search query or user selection
    """
    #before = datetime.datetime.now()
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    search_state = SearchState(
                    user_logged_in=request.user.is_authenticated(),
                    **kwargs
                )

    qs, meta_data = models.Thread.objects.run_advanced_search(
                        request_user=request.user, search_state=search_state
                    )
    if meta_data['non_existing_tags']:
        search_state = search_state.remove_tags(meta_data['non_existing_tags'])

    paginator = Paginator(qs, search_state.page_size)
    if paginator.num_pages < search_state.page:
        search_state.page = 1
    page = paginator.page(search_state.page)
    page.object_list = list(page.object_list) # evaluate the queryset

    # INFO: Because for the time being we need question posts and thread authors
    #       down the pipeline, we have to precache them in thread objects
    models.Thread.objects.precache_view_data_hack(threads=page.object_list)

    related_tags = Tag.objects.get_related_to_search(
                        threads=page.object_list,
                        ignored_tag_names=meta_data.get('ignored_tag_names',[])
                    )
    tag_list_type = askbot_settings.TAG_LIST_FORMAT
    if tag_list_type == 'cloud': #force cloud to sort by name
        related_tags = sorted(related_tags, key = operator.attrgetter('name'))

    contributors = list(
        models.Thread.objects.get_thread_contributors(
                                        thread_list=page.object_list
                                    ).only('id', 'username', 'gravatar')
                        )

    paginator_context = {
        'is_paginated' : (paginator.count > search_state.page_size),
        'pages': paginator.num_pages,
        'current_page_number': search_state.page,
        'page_object': page,
        'base_url' : search_state.query_string(),
        'page_size' : search_state.page_size,
    }

    # We need to pass the rss feed url based
    # on the search state to the template.
    # We use QueryDict to get a querystring
    # from dicts and arrays. Much cleaner
    # than parsing and string formating.
    rss_query_dict = QueryDict("").copy()
    if search_state.query:
        # We have search string in session - pass it to
        # the QueryDict
        rss_query_dict.update({"q": search_state.query})
    if search_state.tags:
        # We have tags in session - pass it to the
        # QueryDict but as a list - we want tags+
        rss_query_dict.setlist("tags", search_state.tags)
    context_feed_url = '/%sfeeds/rss/?%s' % (
                            django_settings.ASKBOT_URL,
                            rss_query_dict.urlencode()
                        ) # Format the url with the QueryDict

    reset_method_count = len(filter(None, [search_state.query, search_state.tags, meta_data.get('author_name', None)]))

    if request.is_ajax():
        q_count = paginator.count

        #todo: words
        question_counter = ungettext('%(q_num)s question', '%(q_num)s questions', q_count)
        question_counter = question_counter % {'q_num': humanize.intcomma(q_count),}

        if q_count > search_state.page_size:
            paginator_tpl = get_template('main_page/paginator.html')
            paginator_html = paginator_tpl.render(
                RequestContext(
                    request, {
                        'context': paginator_context,
                        'questions_count': q_count,
                        'page_size' : search_state.page_size,
                        'search_state': search_state,
                    }
                )
            )
        else:
            paginator_html = ''

        questions_tpl = get_template('main_page/questions_loop.html')
        questions_html = questions_tpl.render(
            RequestContext(
                request, {
                    'threads': page,
                    'search_state': search_state,
                    'reset_method_count': reset_method_count,
                    'request': request
                }
            )
        )

        ajax_data = {
            'query_data': {
                'tags': search_state.tags,
                'sort_order': search_state.sort,
                'ask_query_string': search_state.ask_query_string(),
            },
            'paginator': paginator_html,
            'question_counter': question_counter,
            'faces': [],#[extra_tags.gravatar(contributor, 48) for contributor in contributors],
            'feed_url': context_feed_url,
            'query_string': search_state.query_string(),
            'page_size' : search_state.page_size,
            'questions': questions_html.replace('\n',''),
            'non_existing_tags': meta_data['non_existing_tags'],
        }
        ajax_data['related_tags'] = [{
            'name': escape(tag.name),
            'used_count': humanize.intcomma(tag.local_used_count)
        } for tag in related_tags]

        #here we add and then delete some items
        #to allow extra context processor to work
        ajax_data['tags'] = related_tags
        ajax_data['interesting_tag_names'] = None
        ajax_data['threads'] = page
        extra_context = context.get_extra(
                                    'ASKBOT_QUESTIONS_PAGE_EXTRA_CONTEXT',
                                    request,
                                    ajax_data
                                )
        del ajax_data['tags']
        del ajax_data['interesting_tag_names']
        del ajax_data['threads']

        ajax_data.update(extra_context)

        return HttpResponse(simplejson.dumps(ajax_data), mimetype = 'application/json')

    else: # non-AJAX branch

        template_data = {
            'active_tab': 'questions',
            'author_name' : meta_data.get('author_name',None),
            'contributors' : contributors,
            'context' : paginator_context,
            'is_unanswered' : False,#remove this from template
            'interesting_tag_names': meta_data.get('interesting_tag_names', None),
            'ignored_tag_names': meta_data.get('ignored_tag_names', None),
            'subscribed_tag_names': meta_data.get('subscribed_tag_names', None),
            'language_code': translation.get_language(),
            'name_of_anonymous_user' : models.get_name_of_anonymous_user(),
            'page_class': 'main-page',
            'page_size': search_state.page_size,
            'query': search_state.query,
            'threads' : page,
            'questions_count' : paginator.count,
            'reset_method_count': reset_method_count,
            'scope': search_state.scope,
            'show_sort_by_relevance': conf.should_show_sort_by_relevance(),
            'search_tags' : search_state.tags,
            'sort': search_state.sort,
            'tab_id' : search_state.sort,
            'tags' : related_tags,
            'tag_list_type' : tag_list_type,
            'font_size' : extra_tags.get_tag_font_size(related_tags),
            'display_tag_filter_strategy_choices': conf.get_tag_display_filter_strategy_choices(),
            'email_tag_filter_strategy_choices': conf.get_tag_email_filter_strategy_choices(),
            'update_avatar_data': schedules.should_update_avatar_data(request),
            'query_string': search_state.query_string(),
            'search_state': search_state,
            'feed_url': context_feed_url,
        }

        extra_context = context.get_extra(
                                    'ASKBOT_QUESTIONS_PAGE_EXTRA_CONTEXT',
                                    request,
                                    template_data
                                )

        template_data.update(extra_context)
        template_data.update(context.get_for_tag_editor())

        #and one more thing:) give admin user heads up about
        #setting the domain name if they have not done that yet
        #todo: move this out to a separate middleware
        if request.user.is_authenticated() and request.user.is_administrator():
            if domain_is_bad():
                url = reverse(
                    'group_settings',
                    kwargs = {'group': 'QA_SITE_SETTINGS'}
                )
                url = url + '#id_QA_SITE_SETTINGS__APP_URL'
                msg = _(
                    'Please go to '
                    '<a href="%s">"settings->URLs, keywords and greetings"</a> '
                    'and set the base url for your site to function properly'
                ) % url
                request.user.message_set.create(message=msg)

        return render(request, 'main_page.html', template_data)


def get_top_answers(request):
    """returns a snippet of html of users answers"""
    form = GetUserItemsForm(request.GET)
    if form.is_valid():
        owner = models.User.objects.get(id=form.cleaned_data['user_id'])
        paginator = owner.get_top_answers_paginator(visitor=request.user)
        answers = paginator.page(form.cleaned_data['page_number']).object_list
        template = get_template('user_profile/user_answers_list.html')
        answers_html = template.render({'top_answers': answers})
        json_string = simplejson.dumps({
                            'html': answers_html,
                            'num_answers': paginator.count}
                        )
        return HttpResponse(json_string, mimetype='application/json')
    else:
        return HttpResponseBadRequest()

def tags(request):#view showing a listing of available tags - plain list

    #1) Get parameters. This normally belongs to form cleaning.
    post_data = request.GET
    sortby = post_data.get('sort', 'used')
    try:
        page = int(post_data.get('page', '1'))
    except ValueError:
        page = 1

    if sortby == 'name':
        order_by = 'name'
    else:
        order_by = '-used_count'

    query = post_data.get('query', '').strip()
    tag_list_type = askbot_settings.TAG_LIST_FORMAT

    #2) Get query set for the tags.
    query_params = {'deleted': False}
    if query != '':
        query_params['name__icontains'] = query

    tags_qs = Tag.objects.filter(**query_params).exclude(used_count=0)

    tags_qs = tags_qs.order_by(order_by)

    #3) Start populating the template context.
    data = {
        'active_tab': 'tags',
        'page_class': 'tags-page',
        'tag_list_type' : tag_list_type,
        'stag' : query,
        'tab_id' : sortby,
        'keywords' : query,
        'search_state': SearchState(*[None for x in range(8)])
    }

    if tag_list_type == 'list':
        #plain listing is paginated
        objects_list = Paginator(tags_qs, DEFAULT_PAGE_SIZE)
        try:
            tags = objects_list.page(page)
        except (EmptyPage, InvalidPage):
            tags = objects_list.page(objects_list.num_pages)

        paginator_data = {
            'is_paginated' : (objects_list.num_pages > 1),
            'pages': objects_list.num_pages,
            'current_page_number': page,
            'page_object': tags,
            'base_url' : reverse('tags') + '?sort=%s&amp;' % sortby
        }
        paginator_context = functions.setup_paginator(paginator_data)
        data['paginator_context'] = paginator_context
    else:
        #tags for the tag cloud are given without pagination
        tags = tags_qs
        font_size = extra_tags.get_tag_font_size(tags)
        data['font_size'] = font_size

    data['tags'] = tags
    data.update(context.get_extra('ASKBOT_TAGS_PAGE_EXTRA_CONTEXT', request, data))

    if request.is_ajax():
        template = get_template('tags/content.html')
        template_context = RequestContext(request, data)
        json_data = {'success': True, 'html': template.render(template_context)}
        json_string = simplejson.dumps(json_data)
        return HttpResponse(json_string, mimetype='application/json')
    else:
        return render(request, 'tags.html', data)

@csrf.csrf_protect
def question(request, id):#refactor - long subroutine. display question body, answers and comments
    """view that displays body of the question and
    all answers to it
    """
    #process url parameters
    #todo: fix inheritance of sort method from questions
    #before = datetime.datetime.now()
    form = ShowQuestionForm(request.GET)
    form.full_clean()#always valid
    show_answer = form.cleaned_data['show_answer']
    show_comment = form.cleaned_data['show_comment']
    show_page = form.cleaned_data['show_page']
    answer_sort_method = form.cleaned_data['answer_sort_method']

    #load question and maybe refuse showing deleted question
    #if the question does not exist - try mapping to old questions
    #and and if it is not found again - then give up
    try:
        question_post = models.Post.objects.filter(
                                post_type = 'question',
                                id = id
                            ).select_related('thread')[0]
    except IndexError:
    # Handle URL mapping - from old Q/A/C/ URLs to the new one
        try:
            question_post = models.Post.objects.filter(
                                    post_type='question',
                                    old_question_id = id
                                ).select_related('thread')[0]
        except IndexError:
            raise Http404

        if show_answer:
            try:
                old_answer = models.Post.objects.get_answers().get(old_answer_id=show_answer)
                return HttpResponseRedirect(old_answer.get_absolute_url())
            except models.Post.DoesNotExist:
                pass

        elif show_comment:
            try:
                old_comment = models.Post.objects.get_comments().get(old_comment_id=show_comment)
                return HttpResponseRedirect(old_comment.get_absolute_url())
            except models.Post.DoesNotExist:
                pass

    try:
        question_post.assert_is_visible_to(request.user)
    except exceptions.QuestionHidden, error:
        request.user.message_set.create(message = unicode(error))
        return HttpResponseRedirect(reverse('index'))

    #redirect if slug in the url is wrong
    if request.path.split('/')[-2] != question_post.slug:
        logging.debug('no slug match!')
        question_url = '?'.join((
                            question_post.get_absolute_url(),
                            urllib.urlencode(request.GET)
                        ))
        return HttpResponseRedirect(question_url)


    #resolve comment and answer permalinks
    #they go first because in theory both can be moved to another question
    #this block "returns" show_post and assigns actual comment and answer
    #to show_comment and show_answer variables
    #in the case if the permalinked items or their parents are gone - redirect
    #redirect also happens if id of the object's origin post != requested id
    show_post = None #used for permalinks
    if show_comment:
        #if url calls for display of a specific comment,
        #check that comment exists, that it belongs to
        #the current question
        #if it is an answer comment and the answer is hidden -
        #redirect to the default view of the question
        #if the question is hidden - redirect to the main page
        #in addition - if url points to a comment and the comment
        #is for the answer - we need the answer object
        try:
            show_comment = models.Post.objects.get_comments().get(id=show_comment)
        except models.Post.DoesNotExist:
            error_message = _(
                'Sorry, the comment you are looking for has been '
                'deleted and is no longer accessible'
            )
            request.user.message_set.create(message = error_message)
            return HttpResponseRedirect(question_post.thread.get_absolute_url())

        if str(show_comment.thread._question_post().id) != str(id):
            return HttpResponseRedirect(show_comment.get_absolute_url())
        show_post = show_comment.parent

        try:
            show_comment.assert_is_visible_to(request.user)
        except exceptions.AnswerHidden, error:
            request.user.message_set.create(message = unicode(error))
            #use reverse function here because question is not yet loaded
            return HttpResponseRedirect(reverse('question', kwargs = {'id': id}))
        except exceptions.QuestionHidden, error:
            request.user.message_set.create(message = unicode(error))
            return HttpResponseRedirect(reverse('index'))

    elif show_answer:
        #if the url calls to view a particular answer to
        #question - we must check whether the question exists
        #whether answer is actually corresponding to the current question
        #and that the visitor is allowed to see it
        show_post = get_object_or_404(models.Post, post_type='answer', id=show_answer)
        if str(show_post.thread._question_post().id) != str(id):
            return HttpResponseRedirect(show_post.get_absolute_url())

        try:
            show_post.assert_is_visible_to(request.user)
        except django_exceptions.PermissionDenied, error:
            request.user.message_set.create(message = unicode(error))
            return HttpResponseRedirect(reverse('question', kwargs = {'id': id}))

    thread = question_post.thread

    if getattr(django_settings, 'ASKBOT_MULTILINGUAL', False):
        if thread.language_code != translation.get_language():
            return HttpResponseRedirect(thread.get_absolute_url())

    logging.debug('answer_sort_method=' + unicode(answer_sort_method))

    #load answers and post id's->athor_id mapping
    #posts are pre-stuffed with the correctly ordered comments
    updated_question_post, answers, post_to_author, published_answer_ids = thread.get_cached_post_data(
                                sort_method=answer_sort_method,
                                user=request.user
                            )
    question_post.set_cached_comments(
        updated_question_post.get_cached_comments()
    )


    #Post.objects.precache_comments(for_posts=[question_post] + answers, visitor=request.user)

    user_votes = {}
    user_post_id_list = list()
    #todo: cache this query set, but again takes only 3ms!
    if request.user.is_authenticated():
        user_votes = Vote.objects.filter(
                            user=request.user,
                            voted_post__id__in = post_to_author.keys()
                        ).values_list('voted_post_id', 'vote')
        user_votes = dict(user_votes)
        #we can avoid making this query by iterating through
        #already loaded posts
        user_post_id_list = [
            id for id in post_to_author if post_to_author[id] == request.user.id
        ]

    #resolve page number and comment number for permalinks
    show_comment_position = None
    if show_comment:
        show_page = show_comment.get_page_number(answer_posts=answers)
        show_comment_position = show_comment.get_order_number()
    elif show_answer:
        show_page = show_post.get_page_number(answer_posts=answers)

    objects_list = Paginator(answers, const.ANSWERS_PAGE_SIZE)
    if show_page > objects_list.num_pages:
        return HttpResponseRedirect(question_post.get_absolute_url())
    page_objects = objects_list.page(show_page)

    #count visits
    #import ipdb; ipdb.set_trace()
    if functions.not_a_robot_request(request):
        #todo: split this out into a subroutine
        #todo: merge view counts per user and per session
        #1) view count per session
        update_view_count = False
        if 'question_view_times' not in request.session:
            request.session['question_view_times'] = {}

        last_seen = request.session['question_view_times'].get(question_post.id, None)

        if thread.last_activity_by_id != request.user.id:
            if last_seen:
                if last_seen < thread.last_activity_at:
                    update_view_count = True
            else:
                update_view_count = True

        request.session['question_view_times'][question_post.id] = \
                                                    datetime.datetime.now()

        #2) run the slower jobs in a celery task
        from askbot import tasks
        tasks.record_question_visit.delay(
            question_post = question_post,
            user_id = request.user.id,
            update_view_count = update_view_count
        )

    paginator_data = {
        'is_paginated' : (objects_list.count > const.ANSWERS_PAGE_SIZE),
        'pages': objects_list.num_pages,
        'current_page_number': show_page,
        'page_object': page_objects,
        'base_url' : request.path + '?sort=%s&amp;' % answer_sort_method,
    }
    paginator_context = functions.setup_paginator(paginator_data)

    #todo: maybe consolidate all activity in the thread
    #for the user into just one query?
    favorited = thread.has_favorite_by_user(request.user)

    is_cacheable = True
    if show_page != 1:
        is_cacheable = False
    elif show_comment_position > askbot_settings.MAX_COMMENTS_TO_SHOW:
        is_cacheable = False

    #maybe load draft
    initial = {}
    if request.user.is_authenticated():
        #todo: refactor into methor on thread
        drafts = models.DraftAnswer.objects.filter(
                                        author=request.user,
                                        thread=thread
                                    )
        if drafts.count() > 0:
            initial['text'] = drafts[0].text

    custom_answer_form_path = getattr(django_settings, 'ASKBOT_NEW_ANSWER_FORM', None)
    if custom_answer_form_path:
        answer_form_class = load_module(custom_answer_form_path)
    else:
        answer_form_class = AnswerForm

    answer_form = answer_form_class(initial=initial, user=request.user)

    user_can_post_comment = (
        request.user.is_authenticated() and request.user.can_post_comment()
    )

    new_answer_allowed = True
    previous_answer = None
    if request.user.is_authenticated():
        if askbot_settings.LIMIT_ONE_ANSWER_PER_USER:
            for answer in answers:
                if answer.author == request.user:
                    new_answer_allowed = False
                    previous_answer = answer
                    break

    if request.user.is_authenticated() and askbot_settings.GROUPS_ENABLED:
        group_read_only = request.user.is_read_only()
    else:
        group_read_only = False

    data = {
        'is_cacheable': False,#is_cacheable, #temporary, until invalidation fix
        'long_time': const.LONG_TIME,#"forever" caching
        'page_class': 'question-page',
        'active_tab': 'questions',
        'question' : question_post,
        'thread': thread,
        'thread_is_moderated': thread.is_moderated(),
        'user_is_thread_moderator': thread.has_moderator(request.user),
        'published_answer_ids': published_answer_ids,
        'answer' : answer_form,
        'editor_is_unfolded': answer_form.has_data(),
        'answers' : page_objects.object_list,
        'answer_count': thread.get_answer_count(request.user),
        'category_tree_data': askbot_settings.CATEGORY_TREE,
        'user_votes': user_votes,
        'user_post_id_list': user_post_id_list,
        'user_can_post_comment': user_can_post_comment,#in general
        'new_answer_allowed': new_answer_allowed,
        'oldest_answer_id': thread.get_oldest_answer_id(request.user),
        'previous_answer': previous_answer,
        'tab_id' : answer_sort_method,
        'favorited' : favorited,
        'similar_threads' : thread.get_similar_threads(),
        'language_code': translation.get_language(),
        'paginator_context' : paginator_context,
        'show_post': show_post,
        'show_comment': show_comment,
        'show_comment_position': show_comment_position,
        'group_read_only': group_read_only,
    }
    #shared with ...
    if askbot_settings.GROUPS_ENABLED:
        data['sharing_info'] = thread.get_sharing_info()

    data.update(context.get_for_tag_editor())

    extra = context.get_extra('ASKBOT_QUESTION_PAGE_EXTRA_CONTEXT', request, data)
    data.update(extra)

    return render(request, 'question.html', data)

def revisions(request, id, post_type = None):
    assert post_type in ('question', 'answer')
    post = get_object_or_404(models.Post, post_type=post_type, id=id)
    revisions = list(models.PostRevision.objects.filter(post=post))
    revisions.reverse()
    for i, revision in enumerate(revisions):
        if i == 0:
            revision.diff = sanitize_html(revisions[i].html)
            revision.summary = _('initial version')
        else:
            revision.diff = htmldiff(
                sanitize_html(revisions[i-1].html),
                sanitize_html(revision.html)
            )

    data = {
        'page_class':'revisions-page',
        'active_tab':'questions',
        'post': post,
        'revisions': revisions,
    }
    return render(request, 'revisions.html', data)

@csrf.csrf_exempt
@ajax_only
@anonymous_forbidden
@get_only
def get_comment(request):
    """returns text of a comment by id
    via ajax response requires request method get
    and request must be ajax
    """
    id = int(request.GET['id'])
    comment = models.Post.objects.get(post_type='comment', id=id)
    request.user.assert_can_edit_comment(comment)
    return {'text': comment.text}


@csrf.csrf_exempt
@ajax_only
@anonymous_forbidden
@get_only
def get_perms_data(request):
    """returns details about permitted activities
    according to the users reputation
    """

    items = (
        'MIN_REP_TO_VOTE_UP',
        'MIN_REP_TO_VOTE_DOWN',
    )

    if askbot_settings.MIN_DAYS_TO_ANSWER_OWN_QUESTION > 0:
        items += ('MIN_REP_TO_ANSWER_OWN_QUESTION',)

    if askbot_settings.ACCEPTING_ANSWERS_ENABLED:
        items += (
            'MIN_REP_TO_ACCEPT_OWN_ANSWER',
            'MIN_REP_TO_ACCEPT_ANY_ANSWER',
        )

    items += (
        'MIN_REP_TO_FLAG_OFFENSIVE',
        'MIN_REP_TO_DELETE_OTHERS_COMMENTS',
        'MIN_REP_TO_DELETE_OTHERS_POSTS',
        'MIN_REP_TO_UPLOAD_FILES',
        'MIN_REP_TO_INSERT_LINK',
        'MIN_REP_TO_SUGGEST_LINK',
        'MIN_REP_TO_CLOSE_OTHERS_QUESTIONS',
        'MIN_REP_TO_RETAG_OTHERS_QUESTIONS',
        'MIN_REP_TO_EDIT_WIKI',
        'MIN_REP_TO_EDIT_OTHERS_POSTS',
        'MIN_REP_TO_VIEW_OFFENSIVE_FLAGS',
    )

    if askbot_settings.ALLOW_ASKING_BY_EMAIL or askbot_settings.REPLY_BY_EMAIL:
        items += (
            'MIN_REP_TO_POST_BY_EMAIL',
            'MIN_REP_TO_TWEET_ON_OTHERS_ACCOUNTS',
        )

    data = list()
    for item in items:
        setting = (
            askbot_settings.get_description(item),
            getattr(askbot_settings, item)
        )
        data.append(setting)

    template = get_template('widgets/user_perms.html')
    html = template.render({
        'user': request.user,
        'perms_data': data
    })

    return {'html': html}

@ajax_only
@get_only
def get_post_html(request):
    post = models.Post.objects.get(id=request.GET['post_id'])
    post.assert_is_visible_to(request.user)
    return {'post_html': post.html}
