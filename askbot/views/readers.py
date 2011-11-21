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
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.template import Context
from django.utils.http import urlencode
from django.utils import simplejson
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext
from django.utils import translation
from django.views.decorators import csrf
from django.core.urlresolvers import reverse
from django.core import exceptions as django_exceptions
from django.contrib.humanize.templatetags import humanize
from django.views.decorators.cache import cache_page
from django.http import QueryDict

import askbot
from askbot import exceptions
from askbot.utils.diff import textDiff as htmldiff
from askbot.forms import AdvancedSearchForm, AnswerForm, ShowQuestionForm
from askbot import models
from askbot import schedules
from askbot.models.badges import award_badges_signal
from askbot import const
from askbot.utils import functions
from askbot.utils.decorators import anonymous_forbidden, ajax_only, get_only
from askbot.search.state_manager import SearchState
from askbot.templatetags import extra_tags
from askbot.templatetags import extra_filters
import askbot.conf
from askbot.conf import settings as askbot_settings
from askbot.skins.loaders import render_into_skin, get_template#jinja2 template loading enviroment

# used in index page
#todo: - take these out of const or settings
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

def questions(request):
    """
    List of Questions, Tagged questions, and Unanswered questions.
    matching search query or user selection
    """
    #before = datetime.datetime.now()
    #don't allow to post to this view
    if request.method == 'POST':
        raise Http404

    #update search state
    form = AdvancedSearchForm(request.GET)
    if form.is_valid():
        user_input = form.cleaned_data
    else:
        user_input = None
    search_state = request.session.get('search_state', SearchState())
    view_log = request.session['view_log']
    search_state.update(user_input, view_log, request.user)
    request.session['search_state'] = search_state
    request.session.modified = True

    #force reset for debugging
    #search_state.reset()
    #request.session.modified = True

    #todo: have this call implemented for sphinx, mysql and pgsql
    (qs, meta_data, related_tags) = models.Question.objects.run_advanced_search(
                                            request_user = request.user,
                                            search_state = search_state,
                                        )

    tag_list_type = askbot_settings.TAG_LIST_FORMAT

    #force cloud to sort by name
    if tag_list_type == 'cloud':
        related_tags = sorted(related_tags, key = operator.attrgetter('name'))

    font_size = extra_tags.get_tag_font_size(related_tags)

    paginator = Paginator(qs, search_state.page_size)

    if paginator.num_pages < search_state.page:
        raise Http404

    page = paginator.page(search_state.page)

    contributors = models.Question.objects.get_question_and_answer_contributors(page.object_list)

    paginator_context = {
        'is_paginated' : (paginator.count > search_state.page_size),
        'pages': paginator.num_pages,
        'page': search_state.page,
        'has_previous': page.has_previous(),
        'has_next': page.has_next(),
        'previous': page.previous_page_number(),
        'next': page.next_page_number(),
        'base_url' : request.path + '?sort=%s&amp;' % search_state.sort,#todo in T sort=>sort_method
        'page_size' : search_state.page_size,#todo in T pagesize -> page_size
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
    
    # Format the url with the QueryDict
    context_feed_url = '/feeds/rss/?%s' % rss_query_dict.urlencode()

    if request.is_ajax():

        q_count = paginator.count
        if search_state.tags:
            question_counter = ungettext(
                                    '%(q_num)s question, tagged',
                                    '%(q_num)s questions, tagged',
                                    q_count
                                ) % {
                                    'q_num': humanize.intcomma(q_count),
                                }
        else:
            question_counter = ungettext(
                                    '%(q_num)s question',
                                    '%(q_num)s questions',
                                    q_count
                                ) % {
                                    'q_num': humanize.intcomma(q_count),
                                }

        if q_count > search_state.page_size:
            paginator_tpl = get_template('main_page/paginator.html', request)
            #todo: remove this patch on context after all templates are moved to jinja
            paginator_context['base_url'] = request.path + '?sort=%s&' % search_state.sort
            data = {
                'context': extra_tags.cnprog_paginator(paginator_context),
                'questions_count': q_count
            }
            paginator_html = paginator_tpl.render(Context(data))
        else:
            paginator_html = ''
        search_tags = list()
        if search_state.tags:
            search_tags = list(search_state.tags)
        query_data = {
            'tags': search_tags,
            'sort_order': search_state.sort
        }
        ajax_data = {
            #current page is 1 by default now
            #because ajax is only called by update in the search button
            'query_data': query_data,
            'paginator': paginator_html,
            'question_counter': question_counter,
            'questions': list(),
            'related_tags': list(),
            'faces': list(),
            'feed_url': context_feed_url,
        }

        badge_levels = dict(const.BADGE_TYPE_CHOICES)
        def pluralize_badge_count(count, level):
            return ungettext(
                '%(badge_count)d %(badge_level)s badge',
                '%(badge_count)d %(badge_level)s badges',
                count
            ) % {
                'badge_count': count,
                'badge_level': badge_levels[level]
            }

        gold_badge_css_class = const.BADGE_CSS_CLASSES[const.GOLD_BADGE],
        silver_badge_css_class = const.BADGE_CSS_CLASSES[const.SILVER_BADGE],
        bronze_badge_css_class = const.BADGE_CSS_CLASSES[const.BRONZE_BADGE],

        for tag in related_tags:
            tag_data = {
                'name': tag.name,
                'used_count': humanize.intcomma(tag.local_used_count)
            }
            ajax_data['related_tags'].append(tag_data)

        for contributor in contributors:
            ajax_data['faces'].append(extra_tags.gravatar(contributor, 48))
        #we render the template
        #from django.template import RequestContext
        questions_tpl = get_template('main_page/questions_loop.html', request)
        #todo: remove this patch on context after all templates are moved to jinja
        data = {
            'questions': page,
            'questions_count': q_count,
            'context': paginator_context,
            'language_code': translation.get_language(),
            'query': search_state.query,
        }

        questions_html = questions_tpl.render(Context(data))
        ajax_data['questions'] = questions_html.replace('\n','')
        return HttpResponse(
                    simplejson.dumps(ajax_data),
                    mimetype = 'application/json'
                )

    reset_method_count = 0
    if search_state.query:
        reset_method_count += 1
    if search_state.tags:
        reset_method_count += 1
    if meta_data.get('author_name',None):
        reset_method_count += 1
    

    template_data = {
        'active_tab': 'questions',
        'author_name' : meta_data.get('author_name',None),
        'contributors' : contributors,
        'context' : paginator_context,
        'is_unanswered' : False,#remove this from template
        'interesting_tag_names': meta_data.get('interesting_tag_names',None),
        'ignored_tag_names': meta_data.get('ignored_tag_names',None),
        'language_code': translation.get_language(),
        'name_of_anonymous_user' : models.get_name_of_anonymous_user(),
        'page_class': 'main-page',
        'query': search_state.query,
        'questions' : page,
        'questions_count' : paginator.count,
        'reset_method_count': reset_method_count,
        'scope': search_state.scope,
        'show_sort_by_relevance': askbot.conf.should_show_sort_by_relevance(),
        'search_tags' : search_state.tags,
        'sort': search_state.sort,
        'tab_id' : search_state.sort,
        'tags' : related_tags,
        'tag_list_type' : tag_list_type,
        'font_size' : font_size,
        'tag_filter_strategy_choices': const.TAG_FILTER_STRATEGY_CHOICES,
        'update_avatar_data': schedules.should_update_avatar_data(request),
        'feed_url': context_feed_url,
    }

    assert(request.is_ajax() == False)
    #ajax request is handled in a separate branch above

    #before = datetime.datetime.now()
    response = render_into_skin('main_page.html', template_data, request)
    #after = datetime.datetime.now()
    #print after - before
    return response

def tags(request):#view showing a listing of available tags - plain list

    tag_list_type = askbot_settings.TAG_LIST_FORMAT

    if tag_list_type == 'list':

        stag = ""
        is_paginated = True
        sortby = request.GET.get('sort', 'used')
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        if request.method == "GET":
            stag = request.GET.get("query", "").strip()
            if stag != '':
                objects_list = Paginator(
                                models.Tag.objects.filter(
                                                    deleted=False,
                                                    name__icontains=stag
                                                ).exclude(
                                                    used_count=0
                                                ),
                                DEFAULT_PAGE_SIZE
                            )
            else:
                if sortby == "name":
                    objects_list = Paginator(models.Tag.objects.all().filter(deleted=False).exclude(used_count=0).order_by("name"), DEFAULT_PAGE_SIZE)
                else:
                    objects_list = Paginator(models.Tag.objects.all().filter(deleted=False).exclude(used_count=0).order_by("-used_count"), DEFAULT_PAGE_SIZE)

        try:
            tags = objects_list.page(page)
        except (EmptyPage, InvalidPage):
            tags = objects_list.page(objects_list.num_pages)

        paginator_data = {
            'is_paginated' : is_paginated,
            'pages': objects_list.num_pages,
            'page': page,
            'has_previous': tags.has_previous(),
            'has_next': tags.has_next(),
            'previous': tags.previous_page_number(),
            'next': tags.next_page_number(),
            'base_url' : reverse('tags') + '?sort=%s&amp;' % sortby
        }
        paginator_context = extra_tags.cnprog_paginator(paginator_data)
        data = {
            'active_tab': 'tags',
            'page_class': 'tags-page',
            'tags' : tags,
            'tag_list_type' : tag_list_type,
            'stag' : stag,
            'tab_id' : sortby,
            'keywords' : stag,
            'paginator_context' : paginator_context
        }

    else:

        stag = ""
        sortby = request.GET.get('sort', 'name')

        if request.method == "GET":
            stag = request.GET.get("query", "").strip()
            if stag != '':
                tags = models.Tag.objects.filter(deleted=False, name__icontains=stag).exclude(used_count=0)
            else:
                if sortby == "name":
                    tags = models.Tag.objects.all().filter(deleted=False).exclude(used_count=0).order_by("name")
                else:
                    tags = models.Tag.objects.all().filter(deleted=False).exclude(used_count=0).order_by("-used_count")

        font_size = extra_tags.get_tag_font_size(tags)

        data = {
            'active_tab': 'tags',
            'page_class': 'tags-page',
            'tags' : tags,
            'tag_list_type' : tag_list_type,
            'font_size' : font_size,
            'stag' : stag,
            'tab_id' : sortby,
            'keywords' : stag,
        }

    return render_into_skin('tags.html', data, request)

@csrf.csrf_protect
@cache_page(60 * 5)
def question(request, id):#refactor - long subroutine. display question body, answers and comments
    """view that displays body of the question and
    all answers to it
    """
    #process url parameters
    #todo: fix inheritance of sort method from questions
    default_sort_method = request.session.get('questions_sort_method', 'votes')
    form = ShowQuestionForm(request.GET, default_sort_method)
    form.full_clean()#always valid
    show_answer = form.cleaned_data['show_answer']
    show_comment = form.cleaned_data['show_comment']
    show_page = form.cleaned_data['show_page']
    is_permalink = form.cleaned_data['is_permalink']
    answer_sort_method = form.cleaned_data['answer_sort_method']

    #resolve comment and answer permalinks
    #they go first because in theory both can be moved to another question
    #this block "returns" show_post and assigns actual comment and answer
    #to show_comment and show_answer variables
    #in the case if the permalinked items or their parents are gone - redirect
    #redirect also happens if id of the object's origin post != requested id
    show_post = None #used for permalinks
    if show_comment is not None:
        #if url calls for display of a specific comment,
        #check that comment exists, that it belongs to
        #the current question
        #if it is an answer comment and the answer is hidden -
        #redirect to the default view of the question
        #if the question is hidden - redirect to the main page
        #in addition - if url points to a comment and the comment
        #is for the answer - we need the answer object
        try:
            show_comment = models.Comment.objects.get(id = show_comment)
            if str(show_comment.get_origin_post().id) != id:
                return HttpResponseRedirect(show_comment.get_absolute_url())
            show_post = show_comment.content_object
            show_comment.assert_is_visible_to(request.user)
        except models.Comment.DoesNotExist:
            error_message = _(
                'Sorry, the comment you are looking for has been '
                'deleted and is no longer accessible'
            )
            request.user.message_set.create(message = error_message)
            return HttpResponseRedirect(reverse('question', kwargs = {'id': id}))
        except exceptions.AnswerHidden, error:
            request.user.message_set.create(message = unicode(error))
            #use reverse function here because question is not yet loaded
            return HttpResponseRedirect(reverse('question', kwargs = {'id': id}))
        except exceptions.QuestionHidden, error:
            request.user.message_set.create(message = unicode(error))
            return HttpResponseRedirect(reverse('index'))

    elif show_answer is not None:
        #if the url calls to view a particular answer to 
        #question - we must check whether the question exists
        #whether answer is actually corresponding to the current question
        #and that the visitor is allowed to see it
        try:
            show_post = get_object_or_404(models.Answer, id = show_answer)
            if str(show_post.question.id) != id:
                return HttpResponseRedirect(show_post.get_absolute_url())
            show_post.assert_is_visible_to(request.user)
        except django_exceptions.PermissionDenied, error:
            request.user.message_set.create(message = unicode(error))
            return HttpResponseRedirect(reverse('question', kwargs = {'id': id}))

    #load question and maybe refuse showing deleted question
    try:
        question = get_object_or_404(models.Question, id=id)
        question.assert_is_visible_to(request.user)
    except exceptions.QuestionHidden, error:
        request.user.message_set.create(message = unicode(error))
        return HttpResponseRedirect(reverse('index'))

    #redirect if slug in the url is wrong
    if request.path.split('/')[-1] != question.slug:
        logging.debug('no slug match!')
        question_url = '?'.join((
                            question.get_absolute_url(),
                            urllib.urlencode(request.GET)
                        ))
        return HttpResponseRedirect(question_url)


    logging.debug('answer_sort_method=' + unicode(answer_sort_method))
    #load answers
    answers = question.get_answers(user = request.user)
    answers = answers.select_related(depth=1)

    user_answer_votes = {}
    if request.user.is_authenticated():
        for answer in answers:
            vote = answer.get_user_vote(request.user)
            if vote is not None and not answer.id in user_answer_votes:
                user_answer_votes[answer.id] = int(vote)

    view_dic = {"latest":"-added_at", "oldest":"added_at", "votes":"-score" }
    orderby = view_dic[answer_sort_method]
    if answers is not None:
        answers = answers.order_by("-accepted", orderby)

    filtered_answers = []
    for answer in answers:
        if answer.deleted == True:
            if answer.author_id == request.user.id:
                filtered_answers.append(answer)
        else:
            filtered_answers.append(answer)

    #resolve page number and comment number for permalinks
    show_comment_position = None
    if show_comment:
        show_page = show_comment.get_page_number(answers = filtered_answers)
        show_comment_position = show_comment.get_order_number()
    elif show_answer:
        show_page = show_post.get_page_number(answers = filtered_answers)

    objects_list = Paginator(filtered_answers, const.ANSWERS_PAGE_SIZE)
    if show_page > objects_list.num_pages:
        return HttpResponseRedirect(question.get_absolute_url())
    page_objects = objects_list.page(show_page)

    #count visits
    if functions.not_a_robot_request(request):
        #todo: split this out into a subroutine
        #todo: merge view counts per user and per session
        #1) view count per session
        update_view_count = False
        if 'question_view_times' not in request.session:
            request.session['question_view_times'] = {}

        last_seen = request.session['question_view_times'].get(question.id, None)
        updated_when, updated_who = question.get_last_update_info()

        if updated_who != request.user:
            if last_seen:
                if last_seen < updated_when:
                    update_view_count = True
            else:
                update_view_count = True

        request.session['question_view_times'][question.id] = \
                                                    datetime.datetime.now()

        if update_view_count:
            question.view_count += 1
            question.save()

        #2) question view count per user and clear response displays
        if request.user.is_authenticated():
            #get response notifications
            request.user.visit_question(question)

        #3) send award badges signal for any badges
        #that are awarded for question views
        award_badges_signal.send(None,
                        event = 'view_question',
                        actor = request.user,
                        context_object = question,
                    )

    paginator_data = {
        'is_paginated' : (objects_list.count > const.ANSWERS_PAGE_SIZE),
        'pages': objects_list.num_pages,
        'page': show_page,
        'has_previous': page_objects.has_previous(),
        'has_next': page_objects.has_next(),
        'previous': page_objects.previous_page_number(),
        'next': page_objects.next_page_number(),
        'base_url' : request.path + '?sort=%s&amp;' % answer_sort_method,
        'extend_url' : "#sort-top"
    }
    paginator_context = extra_tags.cnprog_paginator(paginator_data)

    favorited = question.has_favorite_by_user(request.user)
    user_question_vote = 0
    if request.user.is_authenticated():
        votes = question.votes.select_related().filter(user=request.user)
        if votes.count() > 0:
            user_question_vote = int(votes[0])
        else:
            user_question_vote = 0

    data = {
        'page_class': 'question-page',
        'active_tab': 'questions',
        'question' : question,
        'user_question_vote' : user_question_vote,
        'question_comment_count':question.comments.count(),
        'answer' : AnswerForm(question,request.user),
        'answers' : page_objects.object_list,
        'user_answer_votes': user_answer_votes,
        'tags' : question.tags.all(),
        'tab_id' : answer_sort_method,
        'favorited' : favorited,
        'similar_questions' : question.get_similar_questions(),
        'language_code': translation.get_language(),
        'paginator_context' : paginator_context,
        'show_post': show_post,
        'show_comment': show_comment,
        'show_comment_position': show_comment_position
    }
    return render_into_skin('question.html', data, request)

def revisions(request, id, object_name=None):
    assert(object_name in ('Question', 'Answer'))
    post = get_object_or_404(models.get_model(object_name), id=id)
    revisions = list(post.revisions.all())
    revisions.reverse()
    for i, revision in enumerate(revisions):
        revision.html = revision.as_html()
        if i == 0:
            revision.diff = revisions[i].html
            revision.summary = _('initial version')
        else:
            revision.diff = htmldiff(revisions[i-1].html, revision.html)
    data = {
        'page_class':'revisions-page',
        'active_tab':'questions',
        'post': post,
        'revisions': revisions,
    }
    return render_into_skin('revisions.html', data, request)

@ajax_only
@anonymous_forbidden
@get_only
def get_comment(request):
    """returns text of a comment by id
    via ajax response requires request method get
    and request must be ajax
    """
    id = int(request.GET['id'])
    comment = models.Comment.objects.get(id = id)
    request.user.assert_can_edit_comment(comment)
    return {'text': comment.comment}

@ajax_only
@get_only
def get_question_body(request):
    search_state = request.session.get('search_state', SearchState())
    view_log = request.session['view_log']
    (qs, meta_data, related_tags) = models.Question.objects.run_advanced_search(
                                            request_user = request.user,
                                            search_state = search_state)
    paginator = Paginator(qs, search_state.page_size)
    page = paginator.page(search_state.page)
    questions_dict = {}
    for question in page.object_list:
        questions_dict['question-%s' % question.id] = question.summary

    return {'questions-titles': questions_dict}
    return {'questions-titles': questions_dict}
