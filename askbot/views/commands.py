"""
:synopsis: most ajax processors for askbot

This module contains most (but not all) processors for Ajax requests.
Not so clear if this subdivision was necessary as separation of Ajax and non-ajax views
is not always very clean.
"""
import json
import logging
from bs4 import BeautifulSoup
from django.core import exceptions
#from django.core.management import call_command
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http import HttpResponseForbidden
from django.forms import IntegerField, CharField, ValidationError
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.template.loader import get_template
from django.views.decorators import csrf
from django.urls import resolve, Resolver404, NoReverseMatch
from django.utils import timezone
from django.utils import translation
from django.utils.html import escape
from django.utils.translation import gettext as _
from askbot.utils.slug import slugify
from askbot import models
from askbot import forms
from askbot import conf
from askbot import const
from askbot.conf import settings as askbot_settings
from askbot.utils import category_tree
from askbot.utils import decorators
from askbot.utils import url_utils
from askbot.utils.forms import get_db_object_or_404
from askbot.utils.functions import decode_and_loads
from askbot.utils.html import get_login_link
from askbot.utils.http import is_ajax, can_save_draft
from askbot import spam_checker
from askbot.skins.shortcuts import render_into_skin_as_string
from askbot.skins.shortcuts import render_text_into_skin
from askbot.models.tag import get_tags_by_names


def process_vote(user = None, vote_direction = None, post = None):
    """function (non-view) that actually processes user votes
    - i.e. up- or down- votes

    in the future this needs to be converted into a real view function
    for that url and javascript will need to be adjusted

    also in the future make keys in response data be more meaningful
    right now they are kind of cryptic - "status", "count"
    """
    if user.is_anonymous:
        raise exceptions.PermissionDenied(_(
            'Sorry, anonymous users cannot vote'
        ))

    vote = user.get_old_vote_for_post(post)
    response_data = {}
    if vote:
        user.assert_can_revoke_old_vote(vote)
        score_delta = vote.cancel()
        response_data['count'] = post.points + score_delta
        post.points = response_data['count'] #assign here too for correctness
        response_data['status'] = 1 #this means "cancel"
    else:
        user.assert_can_vote_for_post(post=post, direction=vote_direction)
        votes_left = user.get_unused_votes_today()
        if votes_left <= 0:
            raise exceptions.PermissionDenied(_('Sorry you ran out of votes for today'))

        votes_left -= 1
        if votes_left <= \
            askbot_settings.VOTES_LEFT_WARNING_THRESHOLD:
            msg = _('You have %(votes_left)s votes left for today') \
                    % {'votes_left': votes_left }
            response_data['message'] = msg

        if vote_direction == 'up':
            vote = user.upvote(post = post)
        else:
            vote = user.downvote(post = post)

        response_data['count'] = post.points
        response_data['status'] = 0 #this means "not cancel", normal operation

    if vote and post.thread_id:
        #todo: may be more careful here and clear
        #less items and maybe recalculate certain data
        #depending on whether the vote is on question
        #or other posts
        post.thread.clear_cached_data()

    response_data['success'] = 1

    return response_data


@csrf.csrf_protect
def legacy_vote_view(request):
    """
    TODO: This subroutine needs serious refactoring it's too long and is
          hard to understand.

    accept answer code:
        response_data['allowed'] = -1, Accept his own answer
                                    0, no allowed - Anonymous
                                    1, Allowed - by default
        response_data['success'] =  0, failed
                                    1, Success - by default
        response_data['status']  =  0, By default
                                    1, Answer has been accepted already(Cancel)

    vote code:
        allowed = -3, Don't have enough votes left
                  -2, Don't have enough reputation score
                  -1, Vote his own post
                   0, no allowed - Anonymous
                   1, Allowed - by default
        status  =  0, By default
                   1, Cancel
                   2, Vote is too old to be canceled

    offensive code:
        allowed = -3, Don't have enough flags left
                  -2, Don't have enough reputation score to do this
                   0, not allowed
                   1, allowed
        status  =  0, by default
                   1, can't do it again
    """

    response_data = {
        'allowed': 1,
        'success': 1,
        'status': 0,
        'count': 0,
        'message': '',
    }

    try:
        if not is_ajax(request) or not request.method == 'POST':
            raise Exception(_('Sorry, something is not right here...'))

        if not request.user.is_authenticated:
            raise exceptions.PermissionDenied(
                _('Sorry, but anonymous users cannot perform this action.'))

        vote_type = request.POST.get('type')

        if (vote_type not in const.VOTE_TYPES
                or vote_type == const.VOTE_FAVORITE):
            # TODO: Favoriting a question is not handled!
            raise Exception(
                _('Request mode is not supported. Please try again.'))

        vote_args = const.VOTE_TYPES[vote_type]
        user = request.user
        post_id = request.POST.get('postId')
        post = get_object_or_404(
            models.Post, post_type=vote_args[0], pk=post_id)

        if vote_type == const.VOTE_ACCEPT_ANSWER:
            if not askbot_settings.ACCEPTING_ANSWERS_ENABLED:
                raise Exception(
                    _('Request mode is not supported. Please try again.'))

            if post.endorsed:
                user.unaccept_best_answer(post)
                response_data['status'] = 1  # cancelation
            else:
                user.accept_best_answer(post)

            post.thread.update_summary_html()
        elif vote_type in const.VOTE_TYPES_VOTING:
            response_data = process_vote(user=user, vote_direction=vote_args[1], post=post)

            if vote_args[0] == 'question':
                post.thread.update_summary_html()
        elif vote_type in const.VOTE_TYPES_REPORTING:
            user.flag_post(post, cancel=vote_args[1], cancel_all=vote_args[2])
            response_data['count'] = post.offensive_flag_count
        elif vote_type in const.VOTE_TYPES_REMOVAL:
            if post.deleted:
                user.restore_post(post=post)
            else:
                user.delete_post(post=post)
        else:
            raise ValueError('unexpected vote type %d' % vote_type)

        if vote_type in const.VOTE_TYPES_INVALIDATE_CACHE:
            post.thread.reset_cached_data()
    except Exception as e:
        response_data['message'] = str(e)
        response_data['success'] = 0

    data = json.dumps(response_data)
    return HttpResponse(data, content_type='application/json')

#internally grouped views - used by the tagging system
@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
def mark_tag(request, **kwargs):#tagging system

    if request.user.is_anonymous:
        msg = _('anonymous users cannot %(perform_action)s') % \
            {'perform_action': _('mark or unmark tags')}
        raise exceptions.PermissionDenied(msg + ' ' + get_login_link())

    action = kwargs['action']
    post_data = decode_and_loads(request.body)
    raw_tagnames = post_data['tagnames']
    reason = post_data['reason']
    assert reason in ('good', 'bad', 'subscribed')
    #separate plain tag names and wildcard tags
    if action == 'remove':
        tagnames, wildcards = forms.classify_marked_tagnames(raw_tagnames)
    else:
        tagnames, wildcards = forms.clean_marked_tagnames(raw_tagnames)

    if request.user.is_administrator() and 'user' in post_data:
        user = get_object_or_404(models.User, pk=post_data['user'])
    else:
        user = request.user

    cleaned_tagnames, cleaned_wildcards = user.mark_tags(
                                                     tagnames,
                                                     wildcards,
                                                     reason=reason,
                                                     action=action
                                                )

    #lastly - calculate tag usage counts
    tag_usage_counts = dict()
    for name in tagnames:
        if name in cleaned_tagnames:
            tag_usage_counts[name] = 1
        else:
            tag_usage_counts[name] = 0

    for name in wildcards:
        if name in cleaned_wildcards:
            tag_usage_counts[name] = models.Tag.objects.filter(
                                        name__startswith = name[:-1],
                                        language_code=translation.get_language()
                                    ).count()
        else:
            tag_usage_counts[name] = 0

    return tag_usage_counts

@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
def clean_tag_name(request):
    tag_name = forms.clean_tag(request.POST['tag_name'])
    return {'cleaned_tag_name': tag_name}


#@decorators.ajax_only
@decorators.get_only
def get_tags_by_wildcard(request):
    """returns an json encoded array of tag names
    in the response to a wildcard tag name
    """
    wildcard = request.GET.get('wildcard', None)
    if wildcard is None:
        return HttpResponseForbidden()

    matching_tags = models.Tag.objects.get_by_wildcards( [wildcard,] )
    count = matching_tags.count()
    names = matching_tags.values_list('name', flat = True)[:20]
    re_data = json.dumps({'tag_count': count, 'tag_names': list(names)})
    return HttpResponse(re_data, content_type='application/json')

@decorators.get_only
def get_thread_shared_users(request):
    """returns snippet of html with users"""
    thread_id = request.GET['thread_id']
    thread_id = IntegerField().clean(thread_id)
    thread = models.Thread.objects.get(id=thread_id)
    users = thread.get_users_shared_with()
    data = {
        'users': users,
    }
    html = render_into_skin_as_string('components/users_list.html', data, request)
    re_data = json.dumps({
        'html': html,
        'users_count': users.count(),
        'success': True
    })
    return HttpResponse(re_data, content_type='application/json')

@decorators.get_only
def get_thread_shared_groups(request):
    """returns snippet of html with groups"""
    thread_id = request.GET['thread_id']
    thread_id = IntegerField().clean(thread_id)
    thread = models.Thread.objects.get(id=thread_id)
    groups = thread.get_groups_shared_with()
    data = {'groups': groups}
    html = render_into_skin_as_string('widgets/groups_list.html', data, request)
    re_data = json.dumps({
        'html': html,
        'groups_count': groups.count(),
        'success': True
    })
    return HttpResponse(re_data, content_type='application/json')

@decorators.ajax_only
def get_html_template(request):
    """returns rendered template"""
    template_name = getattr(request,request.method).get('template_name', None)
    allowed_templates = (
        'widgets/tag_category_selector.html',
    )
    #have allow simple context for the templates
    if template_name not in allowed_templates:
        raise Http404
    return {
        'html': get_template(template_name).render()
    }

@decorators.get_only
def get_tag_list(request):
    """returns tags to use in the autocomplete
    function
    """
    tags = models.Tag.objects.filter(
                        deleted=False,
                        status=models.Tag.STATUS_ACCEPTED,
                        language_code=translation.get_language()
                    )

    tag_names = tags.values_list(
                        'name', flat = True
                    )

    output = '\n'.join(map(escape, tag_names))
    return HttpResponse(output, content_type='text/plain')

@decorators.get_only
def load_object_description(request):
    """returns text of the object description in text"""
    obj = get_db_object_or_404(request.GET)#askbot forms utility
    text = getattr(obj.description, 'text', '').strip()
    return HttpResponse(text, content_type='text/plain')

@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
@decorators.moderators_only
def save_object_description(request):
    """if object description does not exist,
    creates a new record, otherwise edits an existing
    one"""
    obj = get_db_object_or_404(request.POST)
    text = request.POST['text']
    if obj.description:
        request.user.edit_post(obj.description, body_text=text)
    else:
        request.user.post_object_description(obj, body_text=text)
    return {'html': obj.description.html}

@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
def rename_tag(request):
    if request.user.is_anonymous \
        or not request.user.is_administrator_or_moderator():
        raise exceptions.PermissionDenied()
    post_data = decode_and_loads(request.body)
    to_name = forms.clean_tag(post_data['to_name'])
    from_name = forms.clean_tag(post_data['from_name'])
    path = post_data['path']

    #kwargs = {'from': old_name, 'to': new_name}
    #call_command('rename_tags', **kwargs)

    tree = category_tree.get_data()
    category_tree.rename_category(
        tree,
        from_name = from_name,
        to_name = to_name,
        path = path
    )
    category_tree.save_data(tree)

@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
def delete_tag(request):
    """todo: actually delete tags
    now it is only deletion of category from the tree"""
    if request.user.is_anonymous \
        or not request.user.is_administrator_or_moderator():
        raise exceptions.PermissionDenied()

    try:
        post_data = decode_and_loads(request.body)
        tag_name = post_data['tag_name']
        path = post_data['path']
        tree = category_tree.get_data()
        category_tree.delete_category(tree, tag_name, path)
        category_tree.save_data(tree)
    except Exception:
        if 'tag_name' in locals():
            logging.critical('could not delete tag %s' % tag_name)
        else:
            logging.critical('failed to parse post data %s' % request.body)
        raise exceptions.PermissionDenied(_('Sorry, could not delete tag'))
    return {'tree_data': tree}

@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
def add_tag_category(request):
    """adds a category at the tip of a given path expects
    the following keys in the ``request.POST``
    * path - array starting with zero giving path to
      the category page where to add the category
    * new_category_name - string that must satisfy the
      same requiremets as a tag

    return json with the category tree data
    todo: switch to json stored in the live settings
    now we have indented input
    """
    if request.user.is_anonymous \
        or not request.user.is_administrator_or_moderator():
        raise exceptions.PermissionDenied()

    post_data = decode_and_loads(request.body)
    category_name = forms.clean_tag(post_data['new_category_name'])
    path = post_data['path']

    tree = category_tree.get_data()

    if category_tree.path_is_valid(tree, path) == False:
        raise ValueError('category insertion path is invalid')

    new_path = category_tree.add_category(tree, category_name, path)
    category_tree.save_data(tree)
    return {
        'tree_data': tree,
        'new_path': new_path
    }


@decorators.get_only
def get_groups_list(request):
    """returns names of group tags
    for the autocomplete function"""
    global_group = models.Group.objects.get_global_group()
    groups = models.Group.objects.exclude_personal()
    group_names = groups.exclude(
                        name=global_group.name
                    ).values_list(
                        'name', flat = True
                    )
    output = '\n'.join(group_names)
    return HttpResponse(output, content_type='text/plain')

@csrf.csrf_protect
def subscribe_for_tags(request):
    """process subscription of users by tags"""
    #todo - use special separator to split tags
    tag_names = getattr(request,request.method).get('tags','').strip().split()
    pure_tag_names, wildcards = forms.clean_marked_tagnames(tag_names)
    if request.user.is_authenticated:
        if request.method == 'POST':
            if 'ok' in request.POST:
                request.user.mark_tags(
                            pure_tag_names,
                            wildcards,
                            reason = 'good',
                            action = 'add'
                        )
                request.user.message_set.create(
                    message = _('Your tag subscription was saved, thanks!')
                )
            else:
                message = _(
                    'Tag subscription was canceled (<a href="%(url)s">undo</a>).'
                ) % {'url': escape(request.path) + '?tags=' + getattr(request,request.method)['tags']}
                request.user.message_set.create(message = message)
            return HttpResponseRedirect(reverse('index'))
        else:
            data = {'tags': tag_names}
            return render(request, 'subscribe_for_tags.html', data)
    else:
        all_tag_names = pure_tag_names + wildcards
        message = _('Please sign in to subscribe for: %(tags)s') \
                    % {'tags': ', '.join(all_tag_names)}
        request.user.message_set.create(message = message)
        request.session['subscribe_for_tags'] = (pure_tag_names, wildcards)
        return HttpResponseRedirect(url_utils.get_login_url())

@decorators.moderators_only
def list_bulk_tag_subscription(request):
    if askbot_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED is False:
        raise Http404
    object_list = models.BulkTagSubscription.objects.all() # pylint: disable=no-member
    data = {'object_list': object_list}
    return render(request, 'tags/list_bulk_tag_subscription.html', data)

@decorators.moderators_only
def create_bulk_tag_subscription(request):
    if askbot_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED is False:
        raise Http404

    data = {'action': _('Create')}
    if request.method == "POST":
        form = forms.BulkTagSubscriptionForm(request.POST)
        if form.is_valid():
            tag_names = form.cleaned_data['tags'].split(' ')
            user_list = form.cleaned_data.get('users')
            group_list = form.cleaned_data.get('groups')
            lang = translation.get_language()

            bulk_subscription = models.BulkTagSubscription.objects.create(
                                                            tag_names=tag_names,
                                                            tag_author=request.user,
                                                            user_list=user_list,
                                                            group_list=group_list,
                                                            language_code=lang
                                                        )

            return HttpResponseRedirect(reverse('list_bulk_tag_subscription'))
        else:
            data['form'] = form
    else:
        data['form'] = forms.BulkTagSubscriptionForm()

    return render(request, 'tags/form_bulk_tag_subscription.html', data)

@decorators.moderators_only
def edit_bulk_tag_subscription(request, pk):
    if askbot_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED is False:
        raise Http404

    bulk_subscription = get_object_or_404(models.BulkTagSubscription,
                                          pk=pk)
    data = {'action': _('Edit')}
    if request.method == "POST":
        form = forms.BulkTagSubscriptionForm(request.POST)
        if form.is_valid():
            bulk_subscription.tags.clear()
            bulk_subscription.users.clear()
            bulk_subscription.groups.clear()

            if 'groups' in form.cleaned_data:
                group_ids = [user.id for user in form.cleaned_data['groups']]
                bulk_subscription.groups.add(*group_ids)

            lang = translation.get_language()

            tags, new_tag_names = get_tags_by_names(
                                        form.cleaned_data['tags'].split(' '),
                                        language_code=lang
                                    )
            tag_id_list = [tag.id for tag in tags]

            for new_tag_name in new_tag_names:
                new_tag = models.Tag.objects.create(
                                        name=new_tag_name,
                                        created_by=request.user,
                                        language_code=lang
                                    )
                tag_id_list.append(new_tag.id)

            bulk_subscription.tags.add(*tag_id_list)

            user_ids = []
            for user in form.cleaned_data['users']:
                user_ids.append(user)
                user.mark_tags(bulk_subscription.tag_list(),
                               reason='subscribed', action='add')

            bulk_subscription.users.add(*user_ids)

            return HttpResponseRedirect(reverse('list_bulk_tag_subscription'))
    else:
        form_initial = {
                        'users': bulk_subscription.users.all(),
                        'groups': bulk_subscription.groups.all(),
                        'tags': ' '.join([tag.name for tag in bulk_subscription.tags.all()]),
                       }
        data.update({
                    'bulk_subscription': bulk_subscription,
                    'form': forms.BulkTagSubscriptionForm(initial=form_initial),
                   })

    return render(request, 'tags/form_bulk_tag_subscription.html', data)

@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
def toggle_follow_question(request):
    result = dict()

    if request.user.is_anonymous:
        msg = _('anonymous users cannot %(perform_action)s') % \
            {'perform_action': askbot_settings.WORDS_FOLLOW_QUESTIONS}
        raise exceptions.PermissionDenied(msg + ' ' + get_login_link())
    else:
        q_id = request.POST['question_id']
        question = get_object_or_404(models.Post, id=q_id)
        result['is_enabled'] = request.user.toggle_favorite_question(question)
        result['num_followers'] = models.FavoriteQuestion.objects.filter(thread=question.thread).count()
    return result


@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
def set_question_title(request):
    if request.user.is_anonymous:
        message = _('anonymous users cannot %(perform_action)s') % \
            {'perform_action': _('make edits')}
        raise exceptions.PermissionDenied(message)

    question_id = request.POST['question_id']
    question = get_object_or_404(models.Post, pk=question_id)
    title = request.POST['title']

    spam_checker_params = spam_checker.get_params_from_request(request)
    enabled = askbot_settings.SPAM_FILTER_ENABLED
    if enabled and spam_checker.is_spam(question.get_text_content(title=title), **spam_checker_params):
        message = _('Spam was detected in the post')
        raise exceptions.PermissionDenied(message)

    user = request.user
    user.edit_question(question, title=title)
    return {'title': question.thread.get_title()}


@decorators.ajax_only
def get_question_title(request):
    question_id = request.GET['question_id']
    question = get_object_or_404(models.Post, pk=question_id)
    question.assert_is_visible_to(request.user)
    return {'title': question.thread.title}


@decorators.ajax_only
@decorators.get_only
def get_post_body(request):
    post_id = request.GET['post_id']
    form = forms.GetDataForPostForm(request.GET)
    form.full_clean()
    post = get_object_or_404(models.Post, pk=form.cleaned_data['post_id'])
    return {'body_text': post.text}


@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
def set_post_body(request):
    """Updates text body of post"""
    if request.user.is_anonymous:
        message = _('anonymous users cannot %(perform_action)s') % \
            {'perform_action': _('make edits')}
        raise exceptions.PermissionDenied(message)

    form = forms.SetPostBodyForm(request.POST)
    form.full_clean()
    post_id = form.cleaned_data['post_id']
    body_text = form.cleaned_data['body_text']
    suppress_email = form.cleaned_data['suppress_email']

    post = get_object_or_404(models.Post, pk=post_id)
    text = post.get_text_content(body_text=body_text)
    spam_checker_params = spam_checker.get_params_from_request(request)
    enabled = askbot_settings.SPAM_FILTER_ENABLED
    if enabled and spam_checker.is_spam(text, **spam_checker_params):
        message = _('Spam was detected in the post')
        raise exceptions.PermissionDenied(message)

    request.user.edit_post(post,
                           body_text=body_text,
                           suppress_email=suppress_email,
                           is_private=post.is_private()) # maintain privacy
    return {'body_html': post.html}


@decorators.moderators_only
@decorators.post_only
def delete_bulk_tag_subscription(request):
    if askbot_settings.SUBSCRIBED_TAG_SELECTOR_ENABLED is False:
        raise Http404

    pk = request.POST.get('pk')
    if pk:
        bulk_subscription = get_object_or_404(models.BulkTagSubscription, pk=pk)
        bulk_subscription.delete()
        return HttpResponseRedirect(reverse('list_bulk_tag_subscription'))
    else:
        return HttpResponseRedirect(reverse('list_bulk_tag_subscription'))

@decorators.get_only
def api_get_questions(request):
    """json api for retrieving questions by title match"""
    query = request.GET.get('query_text', '').strip()
    tag_name = request.GET.get('tag_name', None)

    if askbot_settings.GROUPS_ENABLED:
        threads = models.Thread.objects.get_visible(user=request.user)
    else:
        threads = models.Thread.objects.all() # pylint: disable=no-member

    if tag_name:
        threads = threads.filter(tags__name=tag_name)

    if query:
        threads = threads.get_for_title_query(query)

    #todo: filter out deleted threads, for now there is no way
    threads = threads.distinct()[:30]

    thread_list = []
    for thread in threads:#todo: this is a temp hack until thread model is fixed
        try:
            thread_list.append({
                    'title': escape(thread.title),
                    'url': thread.get_absolute_url(),
                    'answer_count': thread.get_answer_count(request.user)
                })
        except:
            continue

    json_data = json.dumps(thread_list)
    return HttpResponse(json_data, content_type="application/json")


@csrf.csrf_protect
@decorators.post_only
@decorators.ajax_login_required
def set_tag_filter_strategy(request):
    """saves data in the ``User.[email/display]_tag_filter_strategy``
    for the current user
    """
    filter_type = request.POST['filter_type']
    filter_value = int(request.POST['filter_value'])
    assert(filter_type in ('display', 'email'))
    if filter_type == 'display':
        allowed_values_dict = dict(conf.get_tag_display_filter_strategy_choices())
        assert(filter_value in allowed_values_dict)
        request.user.display_tag_filter_strategy = filter_value
    else:
        allowed_values_dict = dict(conf.get_tag_email_filter_strategy_choices())
        assert(filter_value in allowed_values_dict)
        request.user.email_tag_filter_strategy = filter_value
    request.user.save()
    return HttpResponse('{}', content_type="application/json") #curly braces required to make jquery happy


@login_required
@csrf.csrf_protect
def close(request, id):#close question
    """view to initiate and process
    question close
    """
    question = get_object_or_404(models.Post, post_type='question', id=id)
    try:
        if request.method == 'POST':
            form = forms.CloseForm(request.POST)
            if form.is_valid():
                reason = form.cleaned_data['reason']

                request.user.close_question(
                                        question = question,
                                        reason = reason
                                    )
            return HttpResponseRedirect(question.get_absolute_url())
        else:
            request.user.assert_can_close_question(question)
            form = forms.CloseForm()
            data = {
                'question': question,
                'form': form,
            }
            return render(request, 'close.html', data)
    except exceptions.PermissionDenied as e:
        request.user.message_set.create(message = str(e))
        return HttpResponseRedirect(question.get_absolute_url())

@login_required
@csrf.csrf_protect
def reopen(request, id):#re-open question
    """view to initiate and process
    question close

    this is not an ajax view
    """

    question = get_object_or_404(models.Post, post_type='question', id=id)
    # open question
    try:
        if request.method == 'POST' :
            request.user.reopen_question(question)
            return HttpResponseRedirect(question.get_absolute_url())
        else:
            request.user.assert_can_reopen_question(question)
            closed_by_profile_url = question.thread.closed_by.get_profile_url()
            closed_by_username = question.thread.closed_by.username
            data = {
                'question' : question,
                'closed_by_profile_url': closed_by_profile_url,
                'closed_by_username': closed_by_username,
            }
            return render(request, 'reopen.html', data)

    except exceptions.PermissionDenied as e:
        request.user.message_set.create(message = str(e))
        return HttpResponseRedirect(question.get_absolute_url())


@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
def upvote_comment(request):
    if request.user.is_anonymous:
        raise exceptions.PermissionDenied(_('Please sign in to vote'))
    form = forms.VoteForm(request.POST)
    if form.is_valid():
        comment_id = form.cleaned_data['post_id']
        cancel_vote = form.cleaned_data['cancel_vote']
        comment = get_object_or_404(models.Post, post_type='comment', id=comment_id)
        process_vote(
            post=comment,
            vote_direction='up',
            user=request.user
        )
    else:
        raise ValueError
    #FIXME: rename js
    return {'score': comment.points}

@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
def delete_post(request):
    if request.user.is_anonymous:
        raise exceptions.PermissionDenied(_('Please sign in to delete/restore posts'))
    form = forms.VoteForm(request.POST)
    if form.is_valid():
        post_id = form.cleaned_data['post_id']
        post = get_object_or_404(
            models.Post,
            post_type__in = ('question', 'answer'),
            id = post_id
        )
        if form.cleaned_data['cancel_vote']:
            request.user.restore_post(post)
        else:
            request.user.delete_post(post)
    else:
        raise ValueError
    return {'is_deleted': post.deleted}

#askbot-user communication system
@csrf.csrf_protect
def read_message(request):#marks message a read
    if request.method == "POST":
        if request.POST.get('formdata') == 'required':
            request.session['message_silent'] = 1
            if request.user.is_authenticated:
                request.user.delete_messages()
    return HttpResponse('')


@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
@decorators.moderators_only
def edit_group_membership(request):
    #todo: this call may need to go.
    #it used to be the one creating groups
    #from the user profile page
    #we have a separate method
    form = forms.EditGroupMembershipForm(request.POST)
    if form.is_valid():
        group_name = form.cleaned_data['group_name']
        user_id = form.cleaned_data['user_id']
        try:
            user = models.User.objects.get(id=user_id)
        except models.User.DoesNotExist:
            raise exceptions.PermissionDenied(
                'user with id %d not found' % user_id
            )

        action = form.cleaned_data['action']
        #warning: possible race condition
        if action == 'add':
            try:
                group = models.Group.objects.get(name=group_name)
                request.user.edit_group_membership(user, group, 'add')
                template = get_template('widgets/group_snippet.html')
                return {
                    'name': group.name,
                    'description': getattr(group.description, 'text', ''),
                    'html': template.render({'group': group})
                }
            except models.Group.DoesNotExist:
                raise exceptions.PermissionDenied(
                    _('Group %(name)s does not exist') % {'name': group_name}
                )

        elif action == 'remove':
            try:
                group = models.Group.objects.get(name = group_name)
                request.user.edit_group_membership(user, group, 'remove')
            except models.Group.DoesNotExist:
                raise exceptions.PermissionDenied()
        else:
            raise exceptions.PermissionDenied()
    else:
        raise exceptions.PermissionDenied()


#todo - enable csrf protection for this function
@csrf.csrf_exempt
@decorators.ajax_only
@decorators.post_only
@decorators.moderators_only
def save_group_logo_url(request):
    """saves urls for the group logo"""
    form = forms.GroupLogoURLForm(request.POST)
    if form.is_valid():
        group_id = form.cleaned_data['group_id']
        image_url = form.cleaned_data['image_url']
        group = models.Group.objects.get(id=group_id)
        group.logo_url = image_url
        group.save()
    else:
        raise ValueError('invalid data found when saving group logo')

@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
@decorators.moderators_only
def add_group(request):
    group_name = request.POST.get('group')
    if group_name:
        group, _ = models.Group.objects.get_or_create(
                            name=group_name,
                            openness=models.Group.OPEN,
                            user=request.user,
                        )

        url = reverse('users_by_group', kwargs={'group_id': group.id,
                   'group_slug': slugify(group_name)})
        response_dict = dict(group_name = group_name,
                             url = url )
        return response_dict

@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
@decorators.moderators_only
def delete_group_logo(request):
    group_id = IntegerField().clean(int(request.POST['group_id']))
    group = models.Group.objects.get(id=group_id) # pylint: disable=no-member
    group.logo_url = None
    group.save()


@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
@decorators.moderators_only
def delete_post_reject_reason(request):
    reason_id = IntegerField().clean(int(request.POST['reason_id']))
    reason = models.PostFlagReason.objects.get(id=reason_id) # pylint: disable=no-member
    reason.delete()


@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
@decorators.moderators_only
def toggle_group_profile_property(request):
    #todo: this might be changed to more general "toggle object property"
    group_id = IntegerField().clean(int(request.POST['group_id']))
    property_name = CharField().clean(request.POST['property_name'])
    assert property_name in (
                        'moderate_email',
                        'can_post_questions',
                        'can_post_answers',
                        'can_post_comments',
                        'can_upload_attachments',
                        'can_upload_images',
                        'read_only'
                    )
    group = models.Group.objects.get(id = group_id)
    new_value = not getattr(group, property_name)
    setattr(group, property_name, new_value)
    group.save()
    return {'is_enabled': new_value}


@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
@decorators.moderators_only
def set_group_openness(request):
    group_id = IntegerField().clean(int(request.POST['group_id']))
    value = IntegerField().clean(int(request.POST['value']))
    group = models.Group.objects.get(id=group_id)
    group.openness = value
    group.save()


@csrf.csrf_protect
@decorators.ajax_only
@decorators.moderators_only
def edit_object_property_text(request):
    model_name = CharField().clean(getattr(request,request.method)['model_name'])
    object_id = IntegerField().clean(getattr(request,request.method)['object_id'])
    property_name = CharField().clean(getattr(request,request.method)['property_name'])

    accessible_fields = (
        ('Group', 'preapproved_emails'),
        ('Group', 'preapproved_email_domains')
    )

    if (model_name, property_name) not in accessible_fields:
        raise exceptions.PermissionDenied()

    obj = models.get_model(model_name).objects.get(id=object_id)
    if request.method == 'POST':
        text = CharField().clean(request.POST['text'])
        setattr(obj, property_name, text)
        obj.save()
    elif request.method == 'GET':
        return {'text': getattr(obj, property_name)}
    else:
        raise exceptions.PermissionDenied()


@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
def join_or_leave_group(request):
    """called when user wants to join/leave
    ask to join/cancel join request, depending
    on the groups acceptance level for the given user

    returns resulting "membership_level"
    """
    if request.user.is_anonymous:
        raise exceptions.PermissionDenied()

    Group = models.Group
    Membership = models.GroupMembership

    group_id = IntegerField().clean(request.POST['group_id'])
    group = Group.objects.get(id=group_id)

    membership = request.user.get_group_membership(group)
    if membership is None:
        membership = request.user.join_group(group)
        new_level = membership.get_level_display()
    else:
        request.user.leave_group(group)
        new_level = Membership.get_level_value_display(Membership.NONE)

    return {'membership_level': new_level}


@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
@decorators.moderators_only
def save_post_reject_reason(request):
    """saves post reject reason and returns the reason id
    if reason_id is not given in the input - a new reason is created,
    otherwise a reason with the given id is edited and saved
    """
    form = forms.EditRejectReasonForm(request.POST)

    if form.is_valid():
        raise ValidationError(forms.format_form_errors(form))

    title = form.cleaned_data['title']
    details = form.cleaned_data['details']
    if form.cleaned_data['reason_id'] is None:
        reason = request.user.create_post_reject_reason(
            title = title, details = details
        )
    else:
        reason_id = form.cleaned_data['reason_id']
        reason = models.PostFlagReason.objects.get(id = reason_id) # pylint: disable=no-member
        request.user.edit_post_reject_reason(
            reason, title = title, details = details
        )
    return {
        'reason_id': reason.id,
        'title': title,
        'details': details
    }

@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
@decorators.moderators_only
def moderate_suggested_tag(request):
    """accepts or rejects a suggested tag
    if thread id is given, then tag is
    applied to or removed from only one thread,
    otherwise the decision applies to all threads
    """
    form = forms.ModerateTagForm(request.POST)

    if form.is_valid():
        raise ValidationError(forms.format_form_errors(form))

    tag_id = form.cleaned_data['tag_id']
    thread_id = form.cleaned_data.get('thread_id', None)

    lang = translation.get_language()

    try:
        tag = models.Tag.objects.get( # pylint: disable=no-member
                                id=tag_id,
                                language_code=lang
                            )#can tag not exist?
    except models.Tag.DoesNotExist: # pylint: disable=no-member
        return

    if thread_id:
        threads = models.Thread.objects.filter( # pylint: disable=no-member
                                        id=thread_id,
                                        language_code=lang
                                    )
    else:
        threads = tag.threads.none()

    if form.cleaned_data['action'] == 'accept':
        #todo: here we lose ability to come back
        #to the tag moderation and approve tag to
        #other threads later for the case where tag.used_count > 1
        tag.status = models.Tag.STATUS_ACCEPTED
        tag.save()
        for thread in threads:
            thread.add_tag(
                tag_name=tag.name,
                user=tag.created_by,
                timestamp=timezone.now(),
                silent=True
            )
    else:
        if tag.threads.count() > len(threads):
            for thread in threads:
                thread.tags.remove(tag)
            tag.used_count = tag.threads.count()
            tag.save()
        elif tag.status == models.Tag.STATUS_SUGGESTED:
            tag.delete()


@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
def save_draft_question(request):
    """saves draft questions"""
    if not can_save_draft(request):
        return

    form = forms.DraftQuestionForm(request.POST)
    if not form.is_valid():
        return

    title = form.cleaned_data.get('title', '')
    text = form.cleaned_data.get('text', '')
    tagnames = form.cleaned_data.get('tagnames', '')
    if title or text or tagnames:
        try:
            draft = models.DraftQuestion.objects.get(author=request.user) # pylint: disable=no-member
        except models.DraftQuestion.DoesNotExist: # pylint: disable=no-member
            draft = models.DraftQuestion()

        draft.title = title
        draft.text = text
        draft.tagnames = tagnames
        draft.author = request.user
        draft.save()


@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
def save_draft_answer(request):
    """saves draft answers"""
    #todo: maybe allow drafts for anonymous users
    if not can_save_draft(request.user):
        return

    form = forms.DraftAnswerForm(request.POST)
    if not form.is_valid():
        return

    thread_id = form.cleaned_data['thread_id']
    try:
        thread = models.Thread.objects.get(id=thread_id) # pylint: disable=no-member
    except models.Thread.DoesNotExist: # pylint: disable=no-member
        return
    try:
        draft = models.DraftAnswer.objects.get( # pylint: disable=no-member
                                        thread=thread,
                                        author=request.user
                                )
    except models.DraftAnswer.DoesNotExist: # pylint: disable=no-member
        draft = models.DraftAnswer()

    draft.author = request.user
    draft.thread = thread
    draft.text = form.cleaned_data.get('text', '')
    draft.save()

@decorators.get_only
def get_users_info(request):
    """retuns list of user names and email addresses
    of "fake" users - so that admins can post on their
    behalf"""
    if request.user.is_anonymous:
        return HttpResponseForbidden()

    query = request.GET['q']
    limit = IntegerField().clean(request.GET['limit'])

    users = models.User.objects
    user_info_list = users.filter(username__istartswith=query)

    if request.user.is_administrator_or_moderator():
        user_info_list = user_info_list.values_list('username', 'email')
    else:
        user_info_list = user_info_list.values_list('username')

    result_list = ['|'.join(info) for info in user_info_list[:limit]]
    return HttpResponse('\n'.join(result_list), content_type='text/plain')

@csrf.csrf_protect
def share_question_with_group(request):
    form = forms.ShareQuestionForm(request.POST)
    try:
        if not form.is_valid():
            raise ValueError('invalid form data')

        thread_id = form.cleaned_data['thread_id']
        group_name = form.cleaned_data['recipient_name']

        thread = models.Thread.objects.get(id=thread_id)
        question_post = thread._question_post() # pylint: disable=protected-access

        #get notif set before
        sets1 = question_post.get_notify_sets(
                                mentioned_users=[],
                                exclude_list=[request.user,]
                            )

        #share the post
        if group_name == askbot_settings.GLOBAL_GROUP_NAME:
            thread.make_public(recursive=True)
        else:
            group = models.Group.objects.get(name=group_name)
            thread.add_to_groups((group,), recursive=True)

        #get notif sets after
        sets2 = question_post.get_notify_sets(
                                mentioned_users=[],
                                exclude_list=[request.user,]
                            )

        notify_sets = {
            'for_mentions': sets2['for_mentions'] - sets1['for_mentions'],
            'for_email': sets2['for_email'] - sets1['for_email'],
            'for_inbox': sets2['for_inbox'] - sets1['for_inbox']
        }

        question_post.issue_update_notifications(
            updated_by=request.user,
            notify_sets=notify_sets,
            activity_type=const.TYPE_ACTIVITY_POST_SHARED,
            timestamp=timezone.now()
        )

    except Exception: # pylint: disable=broad-except
        error_message = _('Sorry, looks like sharing request was invalid')
        request.user.message_set.create(message=error_message)

    return HttpResponseRedirect(thread.get_absolute_url())

@csrf.csrf_protect
def share_question_with_user(request):
    form = forms.ShareQuestionForm(request.POST)
    try:
        if not form.is_valid():
            raise ValueError('invalid form data')

        thread_id = form.cleaned_data['thread_id']
        username = form.cleaned_data['recipient_name']

        thread = models.Thread.objects.get(id=thread_id)
        user = models.User.objects.get(username=username)
        group = user.get_personal_group()
        thread.add_to_groups([group], recursive=True)
        #notify the person
        #todo: see if user could already see the post - b/f the sharing
        notify_sets = {
            'for_inbox': set([user]),
            'for_mentions': set([user]),
            'for_email': set([user])
        }
        thread._question_post().issue_update_notifications( # pylint: disable=protected-access
            updated_by=request.user,
            notify_sets=notify_sets,
            activity_type=const.TYPE_ACTIVITY_POST_SHARED,
            timestamp=timezone.now()
        )

    except Exception: # pylint: disable=broad-except
        error_message = _('Sorry, looks like sharing request was invalid')
        request.user.message_set.create(message=error_message)

    return HttpResponseRedirect(thread.get_absolute_url())

@csrf.csrf_protect
def moderate_group_join_request(request):
    """moderator of the group can accept or reject a new user"""
    request_id = IntegerField().clean(request.POST['request_id'])
    action = request.POST['action']
    assert(action in ('approve', 'deny'))

    activity = get_object_or_404(models.Activity, pk=request_id)
    group = activity.content_object
    applicant = activity.user

    if group.has_moderator(request.user):
        group_membership = models.GroupMembership.objects.get( # pylint: disable=no-member
                                            user=applicant, group=group
                                        )
        if action == 'approve':
            group_membership.level = models.GroupMembership.FULL
            group_membership.save()
            msg_data = {'user': applicant.username, 'group': group.name}
            message = _('%(user)s, welcome to group %(group)s!') % msg_data
            applicant.message_set.create(message=message)
        else:
            group_membership.delete()

        activity.delete()
        url = request.user.get_absolute_url() + '?sort=inbox&section=join_requests'
        return HttpResponseRedirect(url)
    raise Http404

@decorators.get_only
def get_editor(request):
    """returns bits of html for the tinymce editor in a dictionary with keys:
    * html - the editor element
    * scripts - an array of script tags
    * success - True
    """
    if 'config' not in request.GET:
        return HttpResponseForbidden()
    config = json.loads(request.GET['config'])
    element_id = request.GET.get('id', 'editor')
    form = forms.EditorForm(
                attrs={'id': element_id},
                editor_attrs=config,
                user=request.user
            )
    editor_html = render_text_into_skin(
        '{{ form.media }} {{ form.editor }}',
        {'form': form},
        request
    )
    #parse out javascript and dom, and return them separately
    #we need that, because js needs to be added in a special way
    html_soup = BeautifulSoup(editor_html, 'html5lib')

    parsed_scripts = []
    for script in html_soup.find_all('script'):
        parsed_scripts.append({
            'contents': script.string,
            'src': script.get('src', None)
        })

    data = {
        'html': str(html_soup.textarea),
        'scripts': parsed_scripts,
        'success': True
    }
    return HttpResponse(json.dumps(data), content_type='application/json')

@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
def publish_post(request):
    """will publish or unpublish post"""
    denied_msg = _('Sorry, only thread moderators or post owners can use this function')

    if request.user.is_anonymous:
        raise exceptions.PermissionDenied(denied_msg)

    post_id = IntegerField().clean(request.POST['post_id'])
    post = models.Post.objects.get(pk=post_id)

    if not request.user.can_publish_group_private_post(post):
        raise exceptions.PermissionDenied(denied_msg)

    # there used to be an experiment where questions were asked
    # privately to a group - i.e. the question was visible to the
    # inquirer and the group only. When the answer was published
    # it was shared with the inquirer
    # Now the code is switched to a simpler mode -
    # "published" === visible to the "everyone" group.
    # (and used to be "published" -> visible to the enquirer).
    #inquirer = answer.thread._question_post().author
    #inquirer_group = enquirer.get_personal_group()
    if askbot_settings.GROUPS_ENABLED:
        if post.is_private():
            #answer.add_to_groups([inquirer_group])
            if post.post_type == 'question':
                post.thread.make_public()
            else:
                post.make_public()

            message = _('The post is now published')
        else:
            #answer.remove_from_groups([inquirer_group])
            if post.post_type == 'question':
                post.thread.make_private(request.user)
            else:
                post.make_private(request.user)

            message = _('The post is now unpublished')
    else:
        message = _('This feature is disabled')

    request.user.message_set.create(message=message)
    return {'redirect_url': post.get_absolute_url()}

@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
def merge_questions(request):
    post_data = decode_and_loads(request.body)
    if request.user.is_anonymous:
        denied_msg = _('Sorry, only thread moderators can use this function')
        raise exceptions.PermissionDenied(denied_msg)

    form_class = forms.GetDataForPostForm
    from_form = form_class({'post_id': post_data['from_id']})
    to_form = form_class({'post_id': post_data['to_id']})
    if from_form.is_valid() and to_form.is_valid():
        from_question = get_object_or_404(models.Post, id=from_form.cleaned_data['post_id'])
        to_question = get_object_or_404(models.Post, id=to_form.cleaned_data['post_id'])
        request.user.merge_duplicate_questions(from_question, to_question)


@decorators.ajax_only
@decorators.get_only
def translate_url(request):
    """Attempts to return url specific to the requested language"""
    form = forms.TranslateUrlForm(request.GET)
    match = None
    if form.is_valid():
        try:
            match = resolve(form.cleaned_data['url'])
        except Resolver404:
            pass

    url = None
    if match:
        lang = form.cleaned_data['language']
        site_lang = translation.get_language()
        translation.activate(lang)

        try:
            url = reverse(match.url_name, args=match.args, kwargs=match.kwargs)
        except NoReverseMatch:
            pass

        translation.activate(site_lang)

    return {'url': url}


@csrf.csrf_protect
@decorators.ajax_only
@decorators.post_only
def reorder_badges(request):
    """places given badge to desired position"""
    if request.user.is_anonymous \
        or not request.user.is_administrator_or_moderator():
        raise exceptions.PermissionDenied()

    form = forms.ReorderBadgesForm(request.POST)
    if form.is_valid():
        badge_id = form.cleaned_data['badge_id']
        position = form.cleaned_data['position']
        badge = models.BadgeData.objects.get(id=badge_id) # pylint: disable=no-member
        badges = list(models.BadgeData.objects.all()) # pylint: disable=no-member
        badges = [v for v in badges if v.is_enabled()]
        badges.remove(badge)
        badges.insert(position, badge)
        pos = 0
        for badge in badges:
            badge.display_order = 10 * pos
            badge.save()
            pos += 1
        return

    raise exceptions.PermissionDenied()
