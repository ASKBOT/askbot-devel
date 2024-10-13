# encoding:utf-8
"""
:synopsis: views "read-only" for main textual content

By main textual content is meant - text of Questions, Answers and Comments.
The "read-only" requirement here is not 100% strict, as for example "question" view does
allow adding new comments via Ajax form post.
"""
import html
import logging
import urllib.request, urllib.parse, urllib.error
import operator
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.http import HttpResponse
from django.http import Http404
from django.http import HttpResponseNotAllowed
from django.http import HttpResponseForbidden
from django.http import HttpResponseBadRequest
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.template.loader import get_template
from django.template import Context, RequestContext
import json
from django.utils import timezone
from django.utils.html import escape
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.utils import translation
from django.views.decorators import csrf
from django.urls import reverse
from django.core import exceptions as django_exceptions
from django.contrib.humanize.templatetags import humanize
from django.http import QueryDict
from django.conf import settings as django_settings

from askbot import conf, const, exceptions, models, signals
from askbot.conf import settings as askbot_settings
from askbot.forms import AnswerForm
from askbot.forms import GetDataForPostForm
from askbot.forms import GetUserItemsForm
from askbot.forms import ShowTagsForm
from askbot.forms import ShowQuestionForm
from askbot.forms import SearchPostsForm
from askbot.models.post import MockPost
from askbot.models.tag import Tag
from askbot.models.recent_contributors import AvatarsBlockData
from askbot.search.state_manager import SearchState, DummySearchState
from askbot.startup_procedures import domain_is_bad
from askbot.templatetags import extra_tags
from askbot.utils import functions
from askbot.utils.decorators import anonymous_forbidden, ajax_only, get_only
from askbot.utils.diff import textDiff as htmldiff
from askbot.utils.html import sanitize_html
from askbot.utils.http import is_ajax
from askbot.utils.loading import load_module
from askbot.utils.translation import get_language_name
from askbot.utils.url_utils import reverse_i18n
from askbot.views import context
import askbot

# used in index page
#todo: - take these out of const or settings
from askbot.models import Post, Vote

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
    if request.method not in ('GET', 'HEAD'):
        return HttpResponseNotAllowed(['GET', 'HEAD'])

    search_state = SearchState(
                    user_logged_in=request.user.is_authenticated,
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

    contributors = AvatarsBlockData.get_data()

    paginator_context = {
        'is_paginated' : (paginator.count > search_state.page_size),
        'pages': paginator.num_pages,
        'current_page_number': search_state.page,
        'page_object': page,
        'base_url' : search_state.query_string(),
        'page_size' : search_state.page_size,
    }

    #get url for the rss feed
    context_feed_url = reverse('latest_questions_feed')
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
        rss_query_dict.setlist('tags', search_state.tags)
        context_feed_url += '?' + rss_query_dict.urlencode()

    reset_method_count = len([_f for _f in [search_state.query, search_state.tags, meta_data.get('author_name', None)] if _f])

    if is_ajax(request):
        q_count = paginator.count

        if q_count > search_state.page_size:
            paginator_tpl = get_template('questions/paginator.html')
            paginator_html = paginator_tpl.render(
                    {
                        'context': paginator_context,
                        'questions_count': q_count,
                        'page_size' : search_state.page_size,
                        'search_state': search_state,
                    },
                    request
            )
        else:
            paginator_html = ''

        questions_tpl = get_template('questions/questions.html')
        questions_html = questions_tpl.render({'threads': page,
                                               'search_state': search_state,
                                               'reset_method_count': reset_method_count,
                                               'request': request},
                                              request)

        question_list_title_tpl = get_template('questions/questions_title.html')
        question_list_title = question_list_title_tpl.render({'questions_count': q_count})

        ajax_data = {
            'query_data': {
                'tags': search_state.tags,
                'sort_order': search_state.sort,
                'ask_query_string': search_state.ask_query_string(),
            },
            'paginator': paginator_html,
            'question_list_title': question_list_title,
            'faces': [],#[extra_tags.gravatar(contributor, 48) for contributor in contributors],
            'feed_url': context_feed_url,
            'query_string': search_state.query_string(),
            'page_size' : search_state.page_size,
            'questions': questions_html.replace('\n',''),
            'non_existing_tags': meta_data['non_existing_tags'],
        }

        related_tags_tpl = get_template('widgets/related_tags.html')
        related_tags_data = {
            'tags': related_tags,
            'tag_list_type': tag_list_type,
            'query_string': search_state.query_string(),
            'search_state': search_state,
            'language_code': translation.get_language(),
        }
        if tag_list_type == 'cloud':
            related_tags_data['font_size'] = extra_tags.get_tag_font_size(related_tags)

        ajax_data['related_tags_html'] = related_tags_tpl.render(
            related_tags_data, request)

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

        return HttpResponse(json.dumps(ajax_data), content_type='application/json')

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
            'display_tag_filter_strategy_choices': conf.get_tag_display_filter_strategy_choices(),
            'email_tag_filter_strategy_choices': conf.get_tag_email_filter_strategy_choices(),
            'query_string': search_state.query_string(),
            'search_state': search_state,
            'feed_url': context_feed_url
        }

        if tag_list_type == 'cloud':
            template_data['font_size'] = extra_tags.get_tag_font_size(related_tags)

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
        if request.user.is_authenticated and request.user.is_administrator():
            if domain_is_bad():
                url = askbot_settings.get_setting_url(('QA_SITE_SETTINGS', 'APP_URL'))
                msg = _(
                    'Please go to Settings -> %s '
                    'and set the base url for your site to function properly'
                ) % url
                request.user.message_set.create(message=msg)

        #before = timezone.now()
        result = render(request, 'questions/index.html', template_data)
        #print('pure render time %s' % (timezone.now() - before))
        return result


def get_top_answers(request):
    """returns a snippet of html of users answers"""
    form = GetUserItemsForm(request.GET)
    if form.is_valid():
        owner = models.User.objects.get(id=form.cleaned_data['user_id'])
        paginator = owner.get_top_answers_paginator(visitor=request.user)
        answers = paginator.page(form.cleaned_data['page_number']).object_list
        template = get_template('user_profile/user_answers_list.html')
        answers_html = template.render({'top_answers': answers})
        json_string = json.dumps({
                            'html': answers_html,
                            'num_answers': paginator.count}
                        )
        return HttpResponse(json_string, content_type='application/json')
    else:
        return HttpResponseBadRequest()

def tags(request):#view showing a listing of available tags - plain list

    form = ShowTagsForm(getattr(request,request.method))
    form.full_clean() #always valid
    page = form.cleaned_data['page']
    sort_method = form.cleaned_data['sort']
    query = form.cleaned_data['query']

    tag_list_type = askbot_settings.TAG_LIST_FORMAT

    #2) Get query set for the tags.
    query_params = {
        'deleted': False,
        'language_code': translation.get_language()
    }
    if query != '':
        query_params['name__icontains'] = query

    tags_qs = Tag.objects.filter(**query_params).exclude(used_count=0)

    if sort_method == 'name':
        order_by = 'name'
    else:
        order_by = '-used_count'


    tags_qs = tags_qs.order_by(order_by)

    #3) Start populating the template context.
    data = {
        'active_tab': 'tags',
        'tag_list_type' : tag_list_type,
        'query' : query,
        'tab_id' : sort_method,
        'keywords' : query,
        'search_state': SearchState(*[None for x in range(8)])
    }

    if tag_list_type == 'list':
        #plain listing is paginated
        objects_list = Paginator(tags_qs, const.TAGS_PAGE_SIZE)
        try:
            tags = objects_list.page(page)
        except (EmptyPage, InvalidPage):
            tags = objects_list.page(objects_list.num_pages)

        paginator_data = {
            'is_paginated' : (objects_list.num_pages > 1),
            'pages': objects_list.num_pages,
            'current_page_number': page,
            'page_object': tags,
            'base_url' : reverse('tags') + '?sort=%s&' % sort_method
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

    if is_ajax(request):
        template = get_template('tags/content.html')
        json_data = {'success': True, 'html': template.render(data,request)}
        json_string = json.dumps(json_data)
        return HttpResponse(json_string, content_type='application/json')
    else:
        return render(request, 'tags/index.html', data)


def should_show_answer_form(user, thread, answers):
    """A utility function, used in the question detail view.
    Thread and answers are given as separate arguments
    with a purpose of performance optimization (i.e. we cannot do thread.get_answers(), etc.)
    """
    if thread.closed:
        return False

    if askbot_settings.READ_ONLY_MODE_ENABLED:
        return False

    if not user.is_authenticated:
        # we don't know if user has previous answers
        if askbot_settings.LIMIT_ONE_ANSWER_PER_USER:
            return False

    if askbot_settings.GROUPS_ENABLED:
        if user.is_authenticated:
            if not user.can_post_answer(thread):
                return False

        if askbot_settings.ALLOW_POSTING_BEFORE_LOGGING_IN:
            if models.Group.objects.get_global_group().can_post_answers:
                return True

    if user.is_authenticated and askbot_settings.LIMIT_ONE_ANSWER_PER_USER:
        for answer in answers:
            if answer.author_id == user.pk:
                return False

    if user.is_authenticated:
        return True

    if askbot_settings.ALLOW_POSTING_BEFORE_LOGGING_IN:
        return True

    return False


def should_hide_answer_ui(user, thread):
    """Hide answer form and any buttons related
    to answers - only when we are not sure if
    the user will be able to post an answer.
    This applies only when there are groups
    that are not allowed to post answers.
    """
    if thread.closed:
        return True

    if askbot_settings.READ_ONLY_MODE_ENABLED:
        return True

    if not askbot_settings.GROUPS_ENABLED:
        return False

    if user.is_anonymous:
        return True

    return not user.has_group_permission('post_answers')


@csrf.csrf_protect
def question(request, id):#refactor - long subroutine. display question body, answers and comments
    """view that displays body of the question and
    all answers to it

    todo: convert this view into class
    """
    #process url parameters
    #todo: fix inheritance of sort method from questions
    #before = timezone.now()
    form = ShowQuestionForm(getattr(request,request.method))
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
            except models.Post.DoesNotExist:
                pass
            else:
                return HttpResponseRedirect(old_answer.get_absolute_url())

        elif show_comment:
            try:
                old_comment = models.Post.objects.get_comments().get(old_comment_id=show_comment)
            except models.Post.DoesNotExist:
                pass
            else:
                return HttpResponseRedirect(old_comment.get_absolute_url())

    if show_comment or show_answer:
        try:
            show_post = models.Post.objects.get(pk=(show_comment or show_answer))
        except models.Post.DoesNotExist:
            #missing target post will be handled later
            pass
        else:
            if (show_comment and not show_post.is_comment()) \
                or (show_answer and not show_post.is_answer()):
                return HttpResponseRedirect(show_post.get_absolute_url())

    try:
        question_post.assert_is_visible_to(request.user)
    except exceptions.QuestionHidden as error:
        request.user.message_set.create(message = str(error))
        return HttpResponseRedirect(reverse('index'))

    #redirect if slug in the url is wrong
    if request.path.split('/')[-2] != question_post.slug:
        logging.debug('no slug match!')
        lang = translation.get_language()
        question_url = question_post.get_absolute_url(language=lang)
        if request.GET:
            question_url += '?' + urllib.parse.urlencode(request.GET)
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
        except exceptions.AnswerHidden as error:
            request.user.message_set.create(message = str(error))
            #use reverse function here because question is not yet loaded
            return HttpResponseRedirect(reverse('question', kwargs = {'id': id}))
        except exceptions.QuestionHidden as error:
            request.user.message_set.create(message = str(error))
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
        except django_exceptions.PermissionDenied as error:
            request.user.message_set.create(message = str(error))
            return HttpResponseRedirect(reverse('question', kwargs = {'id': id}))

    thread = question_post.thread

    if askbot.get_lang_mode() == 'url-lang':
        request_lang = translation.get_language()
        if request_lang != thread.language_code:
            template = get_template('question/lang_switch_message.html')
            message = template.render({
                'post_lang': get_language_name(thread.language_code),
                'request_lang': get_language_name(request_lang),
                'home_url': reverse_i18n(request_lang, 'questions')
            })
            request.user.message_set.create(message=message)
            return HttpResponseRedirect(thread.get_absolute_url())

    logging.debug('answer_sort_method=' + str(answer_sort_method))

    #load answers and post id's->athor_id mapping
    #posts are pre-stuffed with the correctly ordered comments
    question_post, answers, post_to_author, published_answer_ids = thread.get_post_data_for_question_view(
                                sort_method=answer_sort_method,
                                user=request.user
                            )
    user_votes = {}
    user_post_id_list = list()
    #todo: cache this query set, but again takes only 3ms!
    if request.user.is_authenticated:
        user_votes = Vote.objects.filter(
                            user=request.user,
                            voted_post__id__in = list(post_to_author.keys())
                        ).values_list('voted_post_id', 'vote')
        user_votes = dict(user_votes)
        #we can avoid making this query by iterating through
        #already loaded posts
        user_post_id_list = [
            post_id for post_id in post_to_author if post_to_author[post_id] == request.user.id
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
    signals.question_visited.send(None,
                    request=request,
                    question=question_post,
                    timestamp=timezone.now())

    paginator_data = {
        'is_paginated' : (objects_list.count > const.ANSWERS_PAGE_SIZE),
        'pages': objects_list.num_pages,
        'current_page_number': show_page,
        'page_object': page_objects,
        'base_url' : request.path + '?sort=%s&' % answer_sort_method,
    }
    paginator_context = functions.setup_paginator(paginator_data)

    #todo: maybe consolidate all activity in the thread
    #for the user into just one query?
    favorited = thread.has_favorite_by_user(request.user)

    is_cacheable = True
    if show_page != 1:
        is_cacheable = False
    # temporary, until invalidation fix. Got broken with Python 3
    # elif show_comment_position > askbot_settings.MAX_COMMENTS_TO_SHOW:
    #    is_cacheable = False

    #maybe load draft
    initial = {}
    if request.user.is_authenticated:
        #todo: refactor into methor on thread
        drafts = models.DraftAnswer.objects.filter(
                                        author=request.user,
                                        thread=thread
                                    )
        if drafts.count() > 0:
            initial['text'] = drafts[0].get_text()

    custom_answer_form_path = django_settings.ASKBOT_NEW_ANSWER_FORM
    if custom_answer_form_path:
        answer_form_class = load_module(custom_answer_form_path)
    else:
        answer_form_class = AnswerForm

    answer_form = answer_form_class(initial=initial, user=request.user, label_suffix='')

    user_can_post_comment = (
        request.user.is_authenticated \
        and request.user.can_post_comment(question_post)
    )

    previous_answer = None
    if request.user.is_authenticated and askbot_settings.LIMIT_ONE_ANSWER_PER_USER:
        for answer in answers:
            if answer.author_id == request.user.pk:
                previous_answer = answer

    if request.user.is_authenticated and askbot_settings.GROUPS_ENABLED:
        group_read_only = request.user.is_read_only()
    else:
        group_read_only = False

    #session variable added so that the session is
    #not empty and is not autodeleted, otherwise anonymous
    #answer posting is impossible
    request.session['askbot_write_intent'] = True

    data = {
        'active_tab': 'questions',
        'answer' : answer_form,
        'answers' : page_objects.object_list,
        'answer_count': thread.get_answer_count(request.user),
        'blank_comment': MockPost(post_type='comment', author=request.user),#data for the js comment template
        'category_tree_data': askbot_settings.CATEGORY_TREE,
        'favorited' : favorited,
        'group_read_only': group_read_only,
        'is_cacheable': False,#is_cacheable, #temporary, until invalidation fix
        'language_code': translation.get_language(),
        'long_time': const.LONG_TIME,#"forever" caching
        'show_answer_form': should_show_answer_form(request.user, thread, answers),
        'hide_answer_ui': should_hide_answer_ui(request.user, thread),
        'oldest_answer_id': thread.get_oldest_answer_id(request.user),
        'paginator_context' : paginator_context,
        'previous_answer': previous_answer,
        'published_answer_ids': published_answer_ids,
        'question' : question_post,
        'show_comment': show_comment,
        'show_comment_position': show_comment_position,
        'show_post': show_post,
        'similar_threads' : thread.get_similar_threads(),
        'tab_id' : answer_sort_method,
        'thread': thread,
        'user_is_thread_moderator': thread.has_moderator(request.user),
        'user_votes': user_votes,
        'user_post_id_list': user_post_id_list,
        'user_flag_counts_by_post_id': thread.get_flag_counts_by_post_id(request.user),
        'user_can_post_comment': user_can_post_comment,#in general
        'question_detail_page': True
    }
    #shared with ...
    if askbot_settings.GROUPS_ENABLED:
        data['sharing_info'] = thread.get_sharing_info()

    data.update(context.get_for_tag_editor())

    extra = context.get_extra('ASKBOT_QUESTION_PAGE_EXTRA_CONTEXT', request, data)
    data.update(extra)

    return render(request, 'question/index.html', data)
    #print 'generated in ', timezone.now() - before
    #return res

def revisions(request, id, post_type = None):
    assert post_type in ('question', 'answer')
    post = get_object_or_404(models.Post, post_type=post_type, id=id)

    if post.deleted:
        if request.user.is_anonymous \
            or not request.user.is_administrator_or_moderator():
            raise Http404

    revisions = list(models.PostRevision.objects.filter(post=post))
    for i, revision in enumerate(revisions):
        if i == 0:
            revision.diff = sanitize_html(revisions[i].html)
            revision.summary = _('initial version')
        else:
            revision.diff = htmldiff(
                sanitize_html(revisions[i-1].html),
                sanitize_html(revision.html)
            )

    data = {'active_tab':'questions',
            'post': post,
            'revisions': revisions}
    return render(request, 'revisions.html', data)

@ajax_only
@anonymous_forbidden
@get_only
def get_comment(request):
    """returns text of a comment by id
    via ajax response requires request method get
    and request must be ajax
    """
    post_id = int(request.GET['id'])
    comment = models.Post.objects.get(post_type='comment', id=post_id)
    request.user.assert_can_edit_comment(comment)
    rev = comment.get_latest_revision(request.user)
    return {'text': rev.text}


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

    if askbot_settings.REPLY_BY_EMAIL:
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


def search_posts(request):
    """Allows searching for posts by text and post id,
    browsing matching posts forwards and backwards by ID.
    """
    if not request.user.is_authenticated:
        return HttpResponseForbidden()

    if not request.user.is_admin_or_mod():
        return HttpResponseForbidden()

    if request.method == 'POST':
        request_data = request.POST
    else:
        request_data = request.GET

    form = SearchPostsForm(request_data)
    form.full_clean()

    query_string = form.cleaned_data.get('q', '')
    post_id = form.cleaned_data.get('post_id', None)
    post_ord = form.cleaned_data.get('post_ord', None)

    post_types = ('question', 'answer', 'comment')
    posts = Post.objects.filter(post_type__in=post_types).order_by('id')

    if query_string:
        posts = posts.filter(text__icontains=query_string)

    posts_count = posts.count()

    post = None
    if post_id:
        try:
            post = posts.get(pk=post_id)
        except Post.DoesNotExist:
            pass
    elif post_ord:
        try:
            post = posts[post_ord - 1]
        except IndexError:
            pass
    elif posts_count:
        post = posts[0]

    if post and not post_ord:
        post_ord = posts.filter(id__lt=post.pk).count() + 1

    prev_post, next_post = [None] * 2
    if post:
        prev_posts = posts.filter(pk__lt=post.pk).only('id').order_by('-id')
        prev_count = prev_posts.count()
        if prev_count:
            prev_post = prev_posts[0]

        next_posts = posts.filter(pk__gt=post.pk).only('id').order_by('id')
        next_count = next_posts.count()
        if next_count:
            next_post = next_posts[0]

    template_data = {
        'post': post,
        'post_ord': post_ord,
        'next_post': next_post,
        'prev_post': prev_post,
        'query_string': query_string,
        'posts_count': posts_count,
    }

    if request.method == 'POST' and post:
        return HttpResponseRedirect(f'{reverse("search_posts")}?post_id={post.pk}&q={urllib.parse.quote(query_string)}')

    return render(request, 'search_posts/index.html', template_data)
