"""/api/v1 views"""
import json
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, Http404
from askbot import models
from askbot.models import User, UserProfile
from askbot.conf import settings as askbot_settings
from askbot.search.state_manager import SearchState
from askbot.utils.html import site_url
from askbot.utils.functions import get_epoch_str

def get_posts_filter(posts_filter=None):
    """Returns filter for the posts.
    `posts_filter` can be preset, remaining default values
    will be initalized by the current function.
    """
    posts_filter = posts_filter or {}
    posts_filter.setdefault('deleted', False)
    if askbot_settings.CONTENT_MODERATION_MODE == 'premoderation':
        posts_filter.setdefault('approved', True)
    return posts_filter

def get_user_id_info(user_obj):
    """Returns dict with 'id' and 'username' keys and values"""
    return {'id': user_obj.id, 'username': user_obj.username}

def get_user_data(user_obj):
    """get common data about the user"""
    avatar_url = user_obj.get_avatar_url()
    if 'gravatar.com' not in avatar_url:
        avatar_url = site_url(avatar_url)

    return {
        'id': user_obj.id,
        'avatar': avatar_url,
        'username': user_obj.username,
        'joined_at': get_epoch_str(user_obj.date_joined),
        'last_seen_at': get_epoch_str(user_obj.last_seen),
        'reputation': user_obj.reputation,
        'gold': user_obj.gold,
        'silver': user_obj.silver,
        'bronze': user_obj.bronze,
    }

def get_question_data(thread):
    """returns data dictionary for a given thread"""
    question_post = thread._question_post() #pylint: disable=protected-access
    datum = {
        'added_at': get_epoch_str(thread.added_at),
        'id': question_post.id,
        'answer_count': thread.answer_count,
        'answer_ids': thread.get_answer_ids(),
        'accepted_answer_id': thread.accepted_answer_id,
        'view_count': thread.view_count,
        'score': thread.score,
        'last_activity_at': get_epoch_str(thread.last_activity_at),
        'title': thread.title,
        'summary': question_post.summary,
        'tags': thread.tagnames.strip().split(),
        'url': site_url(thread.get_absolute_url()),
    }
    if question_post.last_edited_at:
        datum['last_edited_at'] = get_epoch_str(question_post.last_edited_at)

    if question_post.last_edited_by:
        datum['last_edited_by'] = get_user_id_info(question_post.last_edited_by)

    if thread.closed:
        datum['closed'] = True
        datum['closed_by'] = get_user_id_info(thread.closed_by)
        datum['closed_at'] = get_epoch_str(thread.closed_at)
        datum['closed_reason'] = thread.get_close_reason_display()

    datum['author'] = get_user_id_info(question_post.author)
    datum['last_activity_by'] = get_user_id_info(thread.last_activity_by)
    return datum

def get_answer_data(post):
    """returns data dictionary for a given answer post"""
    datum = {
        'added_at': get_epoch_str(post.added_at),
        'id': post.id,
        'score': post.score,
        'summary': post.summary,
        'url': site_url(post.get_absolute_url()),
    }
    datum['author'] = get_user_id_info(post.author)

    if post.last_edited_at:
        datum['last_edited_at'] = get_epoch_str(post.last_edited_at)

    if post.last_edited_by:
        datum['last_edited_by'] = get_user_id_info(post.last_edited_by)

    return datum

def info(request): #pylint: disable=unused-argument
    """Returns general data about the forum"""
    data = {}

    posts_filter = get_posts_filter()
    posts = models.Post.objects.filter(**posts_filter)
    data['answers'] = posts.filter(post_type='answer').count()
    data['questions'] = posts.filter(post_type='question').count()
    data['comments'] = posts.filter(post_type='comment').count()
    data['users'] = User.objects.filter(is_active=True).count()

    if askbot_settings.GROUPS_ENABLED:
        data['groups'] = models.Group.objects.exclude_personal().count()
    else:
        data['groups'] = 0

    json_string = json.dumps(data)
    return HttpResponse(json_string, content_type='application/json')

def user(request, user_id): #pylint: disable=unused-argument
    '''
       Returns data about one user
    '''
    user_obj = get_object_or_404(User, pk=user_id)
    data = get_user_data(user_obj)
    posts_filter = get_posts_filter({'author': user_obj})
    posts = models.Post.objects.filter(**posts_filter)
    data['answers'] = posts.filter(post_type='answer').count()
    data['questions'] = posts.filter(post_type='question').count()
    data['comments'] = posts.filter(post_type='comment').count()
    json_string = json.dumps(data)
    return HttpResponse(json_string, content_type='application/json')


def users(request):
    """Returns data of the most active or latest users."""
    page = request.GET.get("page", '1')

    try:
        page = int(page)
    except ValueError: # cast failed
        page = 1
    except KeyError as exc: # lookup failed
        raise Http404 from exc

    user_ids = UserProfile.objects.values_list('pk', flat=True) # pylint: disable=no-member
    users_objects = User.objects.filter(id__in=user_ids).order_by('id')

    paginator = Paginator(users_objects, 10)

    try:
        user_objects = paginator.page(page)
    except (EmptyPage, InvalidPage):
        user_objects = paginator.page(paginator.num_pages)

    user_list = []
    #serializing to json
    for user_object in user_objects:
        user_dict = get_user_data(user_object)
        user_list.append(dict.copy(user_dict))

    response_dict = {
                'pages': paginator.num_pages,
                'count': paginator.count,
                'users': user_list
            }
    json_string = json.dumps(response_dict)

    return HttpResponse(json_string, content_type='application/json')


def question(request, question_id): #pylint: disable=unused-argument
    """Returns info about a question by id"""
    #we retrieve question by post id, b/c that's what is in the url,
    #not thread id (currently)
    post_filter = get_posts_filter({'id': question_id, 'post_type': 'question'})
    post = get_object_or_404(models.Post, **post_filter)
    datum = get_question_data(post.thread)
    json_string = json.dumps(datum)
    return HttpResponse(json_string, content_type='application/json')

def answer(request, answer_id): #pylint: disable=unused-argument
    """Returns info about an answer by id"""
    post_filter = get_posts_filter({'id': answer_id, 'post_type': 'answer'})
    post = get_object_or_404(models.Post, **post_filter)
    datum = get_answer_data(post)
    json_string = json.dumps(datum)
    return HttpResponse(json_string, content_type='application/json')

def questions(request):
    """
    List of Questions, Tagged questions, and Unanswered questions.
    matching search query or user selection
    """
    try:
        author_id = int(request.GET.get("author"))
    except (ValueError, TypeError):
        author_id = None

    try:
        page = int(request.GET.get("page"))
    except (ValueError, TypeError):
        page = None

    search_state = SearchState(scope=request.GET.get('scope', 'all'),
                               sort=request.GET.get('sort', 'activity-desc'),
                               query=request.GET.get('query', None),
                               tags=request.GET.get('tags', None),
                               author=author_id,
                               page=page,
                               user_logged_in=request.user.is_authenticated)

    qset, meta_data = models.Thread.objects.run_advanced_search(
        request_user=request.user, search_state=search_state
    )
    if meta_data['non_existing_tags']:
        search_state = search_state.remove_tags(meta_data['non_existing_tags'])

    #exludes the question from groups
    #global_group = models.Group.objects.get_global_group()
    #qs = qs.exclude(~Q(groups__id=global_group.id))

    page_size = askbot_settings.DEFAULT_QUESTIONS_PAGE_SIZE
    paginator = Paginator(qset, page_size)
    if paginator.num_pages < search_state.page:
        search_state.page = 1
    page = paginator.page(search_state.page)

    question_list = []
    for thread in page.object_list:
        datum = get_question_data(thread)
        question_list.append(datum)

    ajax_data = {
        'count': paginator.count,
        'pages' : paginator.num_pages,
        'questions': question_list
    }
    response_data = json.dumps(ajax_data)
    return HttpResponse(response_data, content_type='application/json')
