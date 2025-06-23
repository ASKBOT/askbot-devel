# encoding:utf-8
"""
:synopsis: views diplaying and processing main content post forms

This module contains views that allow adding, editing, and deleting main textual content.
"""
import logging
import os
import os.path
import random
import sys
import tempfile
import time
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseForbidden
from django.http import HttpResponseRedirect
from django.http import Http404
import json
from django.utils import timezone
from django.utils.html import strip_tags, escape
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.urls import reverse
from django.core import exceptions
from django.conf import settings
from django.views.decorators import csrf
from django.contrib.auth.models import User

from askbot import exceptions as askbot_exceptions
from askbot import forms
from askbot import models
from askbot import signals
from askbot.conf import settings as askbot_settings
from askbot.utils import decorators
from askbot.utils.forms import format_errors
from askbot.utils.functions import diff_date
from askbot.utils import url_utils
from askbot.utils.file_utils import store_file
from askbot.utils.functions import encode_jwt
from askbot.utils.http import is_ajax
from askbot.utils.loading import load_module
from askbot.views import context
from askbot.templatetags import extra_filters_jinja as template_filters
from askbot.importers.stackexchange import management as stackexchange#todo: may change
from askbot.utils.slug import slugify
from askbot import spam_checker

#todo: make this work with csrf
@csrf.csrf_exempt
def upload(request):#ajax upload file to a question or answer
    """view that handles file upload via Ajax
    """
    # check upload permission
    result = ''
    error = ''
    try:
        #may raise exceptions.PermissionDenied
        result, error, file_url, orig_file_name = None, '', None, None
        if request.user.is_anonymous:
            msg = _('Sorry, anonymous users cannot upload files')
            raise exceptions.PermissionDenied(msg)

        if not (request.user.can_upload_attachment() or request.user.can_upload_image()):
            # NOTE: there is no file type check enforcement yet,
            # the permission to upload attachements/images works only for users acting in good faith
            raise exceptions.PermissionDenied(_('Uploading of files is not allowed'))

        #todo: build proper form validation
        file_name_prefix = request.POST.get('file_name_prefix', '')
        if file_name_prefix not in ('', 'group_logo_'):
            raise exceptions.PermissionDenied('invalid upload file name prefix')

        #todo: check file type
        uploaded_file = request.FILES['file-upload']#take first file
        orig_file_name = uploaded_file.name
        #todo: extension checking should be replaced with mimetype checking
        #and this must be part of the form validation
        file_extension = os.path.splitext(orig_file_name)[1].lower()
        if not file_extension in settings.ASKBOT_ALLOWED_UPLOAD_FILE_TYPES:
            file_types = "', '".join(settings.ASKBOT_ALLOWED_UPLOAD_FILE_TYPES)
            msg = _("allowed file types are '%(file_types)s'") % \
                    {'file_types': file_types}
            raise exceptions.PermissionDenied(msg)

        # get file size, make sure that the file is not too large
        uploaded_file.seek(0, 2)
        size = uploaded_file.tell()
        if size > settings.ASKBOT_MAX_UPLOAD_FILE_SIZE:
            msg = _("maximum upload file size is %(file_size)s bytes") % \
                    {'file_size': settings.ASKBOT_MAX_UPLOAD_FILE_SIZE}
            raise exceptions.PermissionDenied(msg)

        # rewind the file and store
        uploaded_file.seek(0)
        file_url = store_file(uploaded_file.name, uploaded_file)

    except exceptions.PermissionDenied as e:
        error = str(e)
    except Exception as e:
        logging.critical(str(e))
        error = _('Error uploading file. Please contact the site administrator. Thank you.')

    if error == '':
        result = 'Good'
    else:
        result = ''
        file_url = ''

    #data = json.dumps({
    #    'result': result,
    #    'error': error,
    #    'file_url': file_url
    #})
    #return HttpResponse(data, content_type='application/json')
    xml_template = "<result><msg><![CDATA[%s]]></msg><error><![CDATA[%s]]></error><file_url>%s</file_url><orig_file_name><![CDATA[%s]]></orig_file_name></result>"
    xml = xml_template % (result, error, file_url, orig_file_name)

    return HttpResponse(xml, content_type="application/xml")

def __import_se_data(dump_file):
    """non-view function that imports the SE data
    in the future may import other formats as well

    In this function stdout is temporarily
    redirected, so that the underlying importer management
    command could stream the output to the browser

    todo: maybe need to add try/except clauses to restore
    the redirects in the exceptional situations
    """

    fake_stdout = tempfile.NamedTemporaryFile()
    real_stdout = sys.stdout
    sys.stdout = fake_stdout

    importer = stackexchange.ImporterThread(dump_file = dump_file.name)
    importer.start()

    #run a loop where we'll be reading output of the
    #importer tread and yielding it to the caller
    read_stdout = open(fake_stdout.name, 'r')
    file_pos = 0
    fd = read_stdout.fileno()
    yield '<html><body><style>* {font-family: sans;} p {font-size: 12px; line-height: 16px; margin: 0; padding: 0;}</style><h1>Importing your data. This may take a few minutes...</h1>'
    while importer.isAlive():
        c_size = os.fstat(fd).st_size
        if c_size > file_pos:
            line = read_stdout.readline()
            yield '<p>' + line + '</p>'
            file_pos = read_stdout.tell()

    fake_stdout.close()
    read_stdout.close()
    dump_file.close()
    sys.stdout = real_stdout
    yield '<p>Done. Please, <a href="%s">Visit Your Forum</a></p></body></html>' % reverse('index')

@csrf.csrf_protect
def import_data(request):
    """a view allowing the site administrator
    upload stackexchange data
    """
    #allow to use this view to site admins
    #or when the forum in completely empty
    if request.user.is_anonymous or (not request.user.is_administrator()):
        if models.Post.objects.get_questions().exists():
            raise Http404

    if request.method == 'POST':
        form = forms.DumpUploadForm(request.POST, request.FILES)
        if form.is_valid():
            dump_file = form.cleaned_data['dump_file']
            dump_storage = tempfile.NamedTemporaryFile()

            #save the temp file
            for chunk in dump_file.chunks():
                dump_storage.write(chunk)
            dump_storage.flush()

            return HttpResponse(__import_se_data(dump_storage))
            #yield HttpResponse(_('StackExchange import complete.'), content_type='text/plain')
            #dump_storage.close()
    else:
        form = forms.DumpUploadForm()

    data = {
        'dump_upload_form': form,
        'need_configuration': (not stackexchange.is_ready())
    }
    return render(request, 'import_data.html', data)

@csrf.csrf_protect
@decorators.check_authorization_to_post(gettext_lazy('Please log in to make posts'))
def ask(request):#view used to ask a new question
    """a view to ask a new question
    gives space for q title, body, tags and checkbox for to post as wiki

    user can start posting a question anonymously but then
    must login/register in order for the question go be shown
    """
    if request.user.is_authenticated:
        if request.user.is_read_only():
            referer = request.META.get("HTTP_REFERER", reverse('questions'))
            request.user.message_set.create(message=_('Sorry, but you have only read access'))
            return HttpResponseRedirect(referer)
        if not request.user.can_post_question():
            return HttpResponseForbidden()

    if askbot_settings.READ_ONLY_MODE_ENABLED:
        return HttpResponseRedirect(reverse('index'))

    if request.method == 'POST':
        form = forms.AskForm(request.POST, user=request.user, label_suffix='')
        if form.is_valid():
            timestamp = timezone.now()
            title = form.cleaned_data['title']
            wiki = form.cleaned_data['wiki']
            tagnames = form.cleaned_data['tags']
            text = form.cleaned_data['text']
            ask_anonymously = form.cleaned_data['ask_anonymously']
            post_privately = form.cleaned_data['post_privately']
            #group_id = form.cleaned_data.get('group_id', None)
            language = form.cleaned_data.get('language', None)

            content = '{}\n\n{}\n\n{}'.format(title, tagnames, text)
            spam_checker_params = spam_checker.get_params_from_request(request)
            enabled = askbot_settings.SPAM_FILTER_ENABLED
            if enabled and spam_checker.is_spam(content, **spam_checker_params):
                message = _('Spam was detected in the post')
                raise exceptions.PermissionDenied(message)

            if request.user.is_authenticated:
                drafts = models.DraftQuestion.objects.filter(author=request.user)
                drafts.delete()
                user = form.get_post_user(request.user)
            elif request.user.is_anonymous and askbot_settings.ALLOW_ASK_UNREGISTERED:
                user = models.get_or_create_anonymous_user()
                ask_anonymously = True
            else:
                user = None

            if user:
                try:
                    question = user.post_question(
                        title=title,
                        body_text=text,
                        tags=tagnames,
                        wiki=wiki,
                        is_anonymous=ask_anonymously,
                        is_private=post_privately,
                        timestamp=timestamp,
                        #group_id=group_id,
                        language=language,
                        ip_addr=request.META.get('REMOTE_ADDR')
                    )
                    signals.new_question_posted.send(None,
                        question=question,
                        user=user,
                        form_data=form.cleaned_data
                    )
                    return HttpResponseRedirect(question.get_absolute_url())
                except exceptions.PermissionDenied as e:
                    request.user.message_set.create(message = str(e))
                    return HttpResponseRedirect(reverse('index'))

            else:
                session_key=request.session.session_key
                if session_key is None:
                    return HttpResponseForbidden()

                models.AnonymousQuestion.objects.create(
                    session_key=session_key,
                    title=title,
                    tagnames=tagnames,
                    wiki=wiki,
                    is_anonymous=ask_anonymously,
                    text=text,
                    added_at=timestamp,
                    ip_addr=request.META.get('REMOTE_ADDR'),
                )
                return HttpResponseRedirect(url_utils.get_login_url())

    if request.method == 'GET':
        form = forms.AskForm(user=request.user)
        #session key used only to enable anonymous asking
        #as django will autodelete empty sessions
        request.session['askbot_write_intent'] = True

    draft_title = ''
    draft_text = ''
    draft_tagnames = ''
    if request.user.is_authenticated:
        drafts = models.DraftQuestion.objects.filter(author=request.user)
        if len(drafts) > 0:
            draft = drafts[0]
            draft_title = draft.title
            draft_text = draft.get_text()
            draft_tagnames = draft.tagnames

    form.initial = {
        'ask_anonymously': getattr(request,request.method).get('ask_anonymously', False),
        'tags': getattr(request,request.method).get('tags', draft_tagnames),
        'text': getattr(request,request.method).get('text', draft_text),
        'title': getattr(request,request.method).get('title', draft_title),
        'post_privately': getattr(request,request.method).get('post_privately', False),
        'language': get_language(),
        'wiki': getattr(request,request.method).get('wiki', False),
    }
    #if 'group_id' in getattr(request,request.method):
    #    try:
    #        group_id = int(request.GET.get('group_id', None))
    #        form.initial['group_id'] = group_id
    #    except Exception:
    #        pass

    editor_is_folded = (askbot_settings.QUESTION_BODY_EDITOR_MODE=='folded' and \
                        askbot_settings.MIN_QUESTION_BODY_LENGTH==0 and \
                        form.initial['text'] == '')

    data = {
        'active_tab': 'ask',
        'form' : form,
        'editor_is_folded': editor_is_folded,
        'mandatory_tags': models.tag.get_mandatory_tags(),
        'email_validation_faq_url':reverse('faq') + '#validate',
        'category_tree_data': askbot_settings.CATEGORY_TREE,
        'tag_names': forms.split_tags(form.initial['tags'])
    }
    data.update(context.get_for_tag_editor())
    return render(request, 'ask/index.html', data)

@login_required
@csrf.csrf_protect
@decorators.ajax_only
def retag_question(request, id):
    """retag question view
    """
    question = get_object_or_404(models.Post, id=id)

    try:
        form = forms.RetagQuestionForm(question, request.POST)

        if not form.is_valid():
            response_data = {
                'message': format_errors(form.errors['tags']),
                'success': False
            }
            data = json.dumps(response_data)
            return HttpResponse(data, content_type="application/json")

        request.user.assert_can_retag_question(question, form.cleaned_data['tags'])

        if form.has_changed():
            text = question.get_text_content(tags=form.cleaned_data['tags'])
            spam_checker_params = spam_checker.get_params_from_request(request)
            enabled = askbot_settings.SPAM_FILTER_ENABLED
            if enabled and spam_checker.is_spam(text, **spam_checker_params):
                message = _('Spam was detected in the post')
                raise exceptions.PermissionDenied(message)

            request.user.retag_question(question=question, tags=form.cleaned_data['tags'])

        response_data = {
            'success': True,
            'new_tags': question.thread.tagnames
        }
        if request.user.message_set.count() > 0:
            message = request.user.get_and_delete_messages()[-1]
            response_data['message'] = message

        data = json.dumps(response_data)
        return HttpResponse(data, content_type="application/json")

    except exceptions.PermissionDenied as e:
        response_data = {
            'message': str(e),
            'success': False
        }
        data = json.dumps(response_data)
        return HttpResponse(data, content_type="application/json")


@login_required
@csrf.csrf_protect
def edit_answer(request, id):
    answer = get_object_or_404(models.Post, id=id)

    if askbot_settings.READ_ONLY_MODE_ENABLED:
        return HttpResponseRedirect(answer.get_absolute_url())

    revision = answer.get_latest_revision(request.user)

    class_path = getattr(settings, 'ASKBOT_EDIT_ANSWER_FORM', None)
    if class_path:
        edit_answer_form_class = load_module(class_path)
    else:
        edit_answer_form_class = forms.EditAnswerForm

    try:
        request.user.assert_can_edit_answer(answer)
        if request.method == "POST":
            if request.POST['select_revision'] == 'true':
                # user has changed revistion number
                revision_form = forms.RevisionForm(
                                                answer,
                                                revision,
                                                request.POST
                                            )
                if revision_form.is_valid():
                    # Replace with those from the selected revision
                    rev = revision_form.cleaned_data['revision']
                    revision = answer.revisions.get(revision = rev)
                    form = edit_answer_form_class(
                                    answer, revision, user=request.user
                                )
                else:
                    form = edit_answer_form_class(
                                                answer,
                                                revision,
                                                request.POST,
                                                user=request.user
                                            )
            else:
                form = edit_answer_form_class(
                    answer, revision, request.POST, user=request.user
                )
                revision_form = forms.RevisionForm(answer, revision)

                if form.is_valid():
                    if form.has_changed():
                        user = form.get_post_user(request.user)
                        suppress_email = form.cleaned_data['suppress_email']
                        is_private = form.cleaned_data.get('post_privately', False)

                        text = form.cleaned_data['text']
                        spam_checker_params = spam_checker.get_params_from_request(request)
                        enabled = askbot_settings.SPAM_FILTER_ENABLED
                        if enabled and spam_checker.is_spam(text, **spam_checker_params):
                            message = _('Spam was detected in the post')
                            raise exceptions.PermissionDenied(message)

                        user.edit_answer(
                            answer=answer,
                            body_text=text,
                            revision_comment=form.cleaned_data['summary'],
                            wiki=form.cleaned_data.get('wiki', answer.wiki),
                            is_private=is_private,
                            suppress_email=suppress_email,
                            ip_addr=request.META.get('REMOTE_ADDR')
                        )

                        signals.answer_edited.send(None,
                            answer=answer,
                            user=user,
                            form_data=form.cleaned_data
                        )

                    return HttpResponseRedirect(answer.get_absolute_url())
        else:
            revision_form = forms.RevisionForm(answer, revision)
            form = edit_answer_form_class(answer, revision, user=request.user)
            if request.user.can_make_group_private_posts():
                form.initial['post_privately'] = answer.is_private()

        data = {
            'active_tab': 'questions',
            'answer': answer,
            'revision': revision,
            'revision_form': revision_form,
            'form': form,
        }
        extra_context = context.get_extra(
            'ASKBOT_EDIT_ANSWER_PAGE_EXTRA_CONTEXT',
            request,
            data
        )
        data.update(extra_context)

        return render(request, 'answer_edit.html', data)

    except exceptions.PermissionDenied as e:
        request.user.message_set.create(message = str(e))
        return HttpResponseRedirect(answer.get_absolute_url())

#todo: rename this function to post_new_answer
@decorators.check_authorization_to_post(gettext_lazy('Please log in to make posts'))
def answer(request, id, form_class=forms.AnswerForm):#process a new answer
    """view that posts new answer

    anonymous users post into anonymous storage
    and redirected to login page

    authenticated users post directly
    """
    question = get_object_or_404(models.Post, post_type='question', id=id)

    if askbot_settings.READ_ONLY_MODE_ENABLED:
        return HttpResponseRedirect(question.get_absolute_url())

    if request.method == 'GET':
        #session key used only to enable anonymous asking
        #as django will autodelete empty sessions
        request.session['askbot_write_intent'] = True
    elif request.method == 'POST':

        #this check prevents backward compatilibility
        if form_class == forms.AnswerForm:
            custom_class_path = getattr(settings, 'ASKBOT_NEW_ANSWER_FORM', None)
            if custom_class_path:
                form_class = load_module(custom_class_path)
            else:
                form_class = forms.AnswerForm

        form = form_class(request.POST, user=request.user)

        if form.is_valid():
            if request.user.is_authenticated:
                drafts = models.DraftAnswer.objects.filter(
                                                author=request.user,
                                                thread=question.thread
                                            )
                drafts.delete()
                user = form.get_post_user(request.user)
                try:
                    text = form.cleaned_data['text']
                    spam_checker_params = spam_checker.get_params_from_request(request)
                    enabled = askbot_settings.SPAM_FILTER_ENABLED
                    if enabled and spam_checker.is_spam(text, **spam_checker_params):
                        message = _('Spam was detected in the post')
                        raise exceptions.PermissionDenied(message)

                    answer = form.save(
                                    question,
                                    user,
                                    ip_addr=request.META.get('REMOTE_ADDR')
                                )

                    signals.new_answer_posted.send(None,
                        answer=answer,
                        user=user,
                        form_data=form.cleaned_data
                    )

                    return HttpResponseRedirect(answer.get_absolute_url())
                except askbot_exceptions.AnswerAlreadyGiven as e:
                    request.user.message_set.create(message = str(e))
                    answer = question.thread.get_answers_by_user(user)[0]
                    return HttpResponseRedirect(answer.get_absolute_url())
                except exceptions.PermissionDenied as e:
                    request.user.message_set.create(message = str(e))
            else:
                if request.session.session_key is None:
                    return HttpResponseForbidden()

                models.AnonymousAnswer.objects.create(
                    question=question,
                    wiki=form.cleaned_data['wiki'],
                    text=form.cleaned_data['text'],
                    session_key=request.session.session_key,
                    ip_addr=request.META.get('REMOTE_ADDR'),
                )
                # in this case automatically show newest answer on top, due to
                # the limitation that we don't know the final answer url
                next_jwt = encode_jwt({'next_url': question.get_absolute_url() + '?sort=latest#sort-top'})
                return HttpResponseRedirect(url_utils.get_login_url() + '?next=' + next_jwt)

    #TODO: look into an issue here is that backend form validation errors
    # won't be displayed, we are fully relying on the prevalidation
    # in the js
    return HttpResponseRedirect(question.get_absolute_url())

def __generate_comments_json(obj, user, avatar_size):
    """non-view generates json data for the post comments
    """
    models.Post.objects.precache_comments(for_posts=[obj], visitor=user)
    comments = obj._cached_comments

    # {"Id":6,"PostId":38589,"CreationDate":"an hour ago","Text":"hello there!","UserDisplayName":"Jarrod Dixon","UserUrl":"/users/3/jarrod-dixon","DeleteUrl":null}
    json_comments = []
    for comment in comments:

        if user and user.is_authenticated:
            try:
                user.assert_can_delete_comment(comment)
                #/posts/392845/comments/219852/delete
                #todo translate this url
                is_deletable = True
            except exceptions.PermissionDenied:
                is_deletable = False
            is_editable = template_filters.can_edit_comment(user, comment)
        else:
            is_deletable = False
            is_editable = False


        comment_owner = comment.author
        tz = ' ' + template_filters.TIMEZONE_STR
        comment_data = {'id' : comment.id,
            'object_id': obj.id,
            'comment_added_at': str(comment.added_at.replace(microsecond = 0)) + tz,
            'html': comment.html,
            'user_display_name': escape(comment_owner.username),
            'user_profile_url': comment_owner.get_profile_url(),
            'user_avatar_url': comment_owner.get_avatar_url(avatar_size),
            'user_id': comment_owner.id,
            'user_is_administrator': comment_owner.is_administrator(),
            'user_is_moderator': comment_owner.is_moderator(),
            'is_deletable': is_deletable,
            'is_editable': is_editable,
            'is_approved': comment.approved,
            'points': comment.points,
            'score': comment.points, #to support js
            'upvoted_by_user': getattr(comment, 'upvoted_by_user', False)
        }
        json_comments.append(comment_data)

    data = json.dumps(json_comments)
    return HttpResponse(data, content_type="application/json")

@csrf.csrf_protect
def post_comments(request):#generic ajax handler to load comments to an object
    """todo: fixme: post_comments is ambigous:
    means either get comments for post or
    add a new comment to post
    """
    # only support get post comments by ajax now
    post_type = getattr(request,request.method).get('post_type', '')
    if not is_ajax(request) or post_type not in ('question', 'answer'):
        raise Http404  # TODO: Shouldn't be 404! More like 400, 403 or sth more specific

    if post_type == 'question' \
        and askbot_settings.QUESTION_COMMENTS_ENABLED == False:
        raise Http404
    elif post_type == 'answer' \
        and askbot_settings.ANSWER_COMMENTS_ENABLED == False:
        raise Http404

    user = request.user

    if request.method == 'POST':
        form = forms.NewCommentForm(request.POST)
    elif request.method == 'GET':
        form = forms.GetCommentDataForPostForm(request.GET)

    if form.is_valid() == False:
        return HttpResponseBadRequest(
            _('This content is forbidden'),
            content_type='application/json'
        )

    post_id = form.cleaned_data['post_id']
    avatar_size = form.cleaned_data['avatar_size']
    try:
        post = models.Post.objects.get(id=post_id)
    except models.Post.DoesNotExist:
        return HttpResponseBadRequest(
            _('Post not found'), content_type='application/json'
        )

    if request.method == "GET":
        response = __generate_comments_json(post, user, avatar_size)
    elif request.method == "POST":
        try:
            if user.is_anonymous:
                msg = _('Sorry, you appear to be logged out and '
                        'cannot post comments. Please '
                        '<a href="%(sign_in_url)s">sign in</a>.') % \
                        {'sign_in_url': url_utils.get_login_url()}
                raise exceptions.PermissionDenied(msg)

            if askbot_settings.READ_ONLY_MODE_ENABLED:
                raise exceptions.PermissionDenied(askbot_settings.READ_ONLY_MESSAGE)

            text = form.cleaned_data['comment']
            spam_checker_params = spam_checker.get_params_from_request(request)
            enabled = askbot_settings.SPAM_FILTER_ENABLED
            if enabled and spam_checker.is_spam(text, **spam_checker_params):
                message = _('Spam was detected in the post')
                raise exceptions.PermissionDenied(message)

            comment = user.post_comment(
                parent_post=post,
                body_text=text,
                ip_addr=request.META.get('REMOTE_ADDR')
            )
            signals.new_comment_posted.send(None,
                comment=comment,
                user=user,
                form_data=form.cleaned_data
            )
            response = __generate_comments_json(post, user, avatar_size)
        except exceptions.PermissionDenied as e:
            response = HttpResponseForbidden(str(e), content_type="application/json")

    return response

@csrf.csrf_protect
@decorators.ajax_only
def edit_comment(request):
    if request.user.is_anonymous:
        raise exceptions.PermissionDenied(_('Sorry, anonymous users cannot edit comments'))

    if askbot_settings.READ_ONLY_MODE_ENABLED:
        raise exceptions.PermissionDenied(askbot_settings.READ_ONLY_MESSAGE)

    form = forms.EditCommentForm(request.POST)
    if form.is_valid() == False:
        raise exceptions.PermissionDenied('This content is forbidden')

    spam_checker_params = spam_checker.get_params_from_request(request)
    enabled = askbot_settings.SPAM_FILTER_ENABLED
    if enabled and spam_checker.is_spam(form.cleaned_data['comment'], **spam_checker_params):
        message = _('Spam was detected in the post')
        raise exceptions.PermissionDenied(message)

    comment_post = models.Post.objects.get(
                    post_type='comment',
                    id=form.cleaned_data['comment_id']
                )

    revision = request.user.edit_comment(
        comment_post=comment_post,
        body_text=form.cleaned_data['comment'],
        suppress_email=form.cleaned_data['suppress_email'],
        ip_addr=request.META.get('REMOTE_ADDR'),
    )

    is_deletable = template_filters.can_delete_comment(
                            comment_post.author, comment_post)

    is_editable = template_filters.can_edit_comment(
                            comment_post.author, comment_post)

    tz = ' ' + template_filters.TIMEZONE_STR

    tz = template_filters.TIMEZONE_STR
    timestamp = str(comment_post.added_at.replace(microsecond=0)) + tz

    #need this because the post.text is due to the latest approved
    #revision, but we may need the suggested revision
    comment_post.text = revision.text
    comment_post.html = comment_post.parse_post_text()['html']

    return {
        'id' : comment_post.id,
        'object_id': comment_post.parent.id,
        'comment_added_at': timestamp,
        'html': comment_post.html,
        'user_display_name': escape(comment_post.author.username),
        'user_url': comment_post.author.get_profile_url(),
        'user_id': comment_post.author.id,
        'is_deletable': is_deletable,
        'is_editable': is_editable,
        'score': comment_post.points, #to support unchanged js
        'points': comment_post.points,
        'voted': comment_post.is_upvoted_by(request.user),
    }

@csrf.csrf_protect
def delete_comment(request):
    """ajax handler to delete comment
    """
    try:
        if request.user.is_anonymous:
            msg = _('Sorry, you appear to be logged out and '
                    'cannot delete comments. Please '
                    '<a href="%(sign_in_url)s">sign in</a>.') % \
                    {'sign_in_url': url_utils.get_login_url()}
            raise exceptions.PermissionDenied(msg)
        if is_ajax(request):

            form = forms.ProcessCommentForm(request.POST)

            if form.is_valid() == False:
                return HttpResponseBadRequest()

            comment_id = form.cleaned_data['comment_id']
            comment = get_object_or_404(models.Post, post_type='comment', id=comment_id)
            request.user.assert_can_delete_comment(comment)

            if askbot_settings.READ_ONLY_MODE_ENABLED:
                raise exceptions.PermissionDenied(askbot_settings.READ_ONLY_MESSAGE)

            parent = comment.parent
            comment.delete()
            parent.recount_comments()
            parent.save()
            parent.thread.reset_cached_data()

            avatar_size = form.cleaned_data['avatar_size']
            return __generate_comments_json(parent, request.user, avatar_size)

        raise exceptions.PermissionDenied(
                    _('sorry, we seem to have some technical difficulties')
                )
    except exceptions.PermissionDenied as e:
        return HttpResponseForbidden(
                    str(e),
                    content_type='application/json'
                )

@login_required
@decorators.post_only
@csrf.csrf_protect
def comment_to_answer(request):
    if request.user.is_anonymous:
        msg = _('Sorry, only logged in users can convert comments to answers. '
                'Please <a href="%(sign_in_url)s">sign in</a>.') % \
                {'sign_in_url': url_utils.get_login_url()}
        raise exceptions.PermissionDenied(msg)

    form = forms.ConvertCommentForm(request.POST)
    if form.is_valid() == False:
        raise Http404

    comment = get_object_or_404(
                    models.Post,
                    post_type='comment',
                    id=form.cleaned_data['comment_id']
                )

    if askbot_settings.READ_ONLY_MODE_ENABLED is False:
        request.user.repost_comment_as_answer(comment)

    return HttpResponseRedirect(comment.get_absolute_url())

@decorators.post_only
@csrf.csrf_protect
#todo: change the urls config for this
def repost_answer_as_comment(request, destination=None):
    assert(
        destination in (
                'comment_under_question',
                'comment_under_previous_answer'
            )
    )
    if request.user.is_anonymous:
        msg = _('Sorry, only logged in users can convert answers to comments. '
                'Please <a href="%(sign_in_url)s">sign in</a>.') % \
                {'sign_in_url': url_utils.get_login_url()}
        raise exceptions.PermissionDenied(msg)
    answer_id = request.POST.get('answer_id')
    if answer_id:
        try:
            answer_id = int(answer_id)
        except (ValueError, TypeError):
            raise Http404
        answer = get_object_or_404(models.Post,
                post_type = 'answer', id=answer_id)

        if askbot_settings.READ_ONLY_MODE_ENABLED:
            return HttpResponseRedirect(answer.get_absolute_url())
        request.user.assert_can_convert_post(post=answer)

        if destination == 'comment_under_question':
            destination_post = answer.thread._question_post()
        else:
            #comment_under_previous_answer
            destination_post = answer.get_previous_answer(user=request.user)
        #todo: implement for comment under other answer

        if not destination_post:
            message = _('Error - could not find the destination post')
            request.user.message_set.create(message=message)
            return HttpResponseRedirect(answer.get_absolute_url())

        if len(answer.text) <= askbot_settings.MAX_COMMENT_LENGTH:
            answer.post_type = 'comment'
            answer.parent = destination_post

            answer.comment_count = 0

            answer_comments = models.Post.objects.get_comments().filter(parent=answer)
            answer_comments.update(parent=destination_post)

            #why this and not just "save"?
            answer.parse_and_save(author=answer.author)
            answer.thread.update_answer_count()

            answer.parent.recount_comments()
            answer.parent.save()

            answer.thread.reset_cached_data()
        else:
            message = _(
                'Cannot convert, because text has more characters than '
                '%(max_chars)s - maximum allowed for comments'
            ) % {'max_chars': askbot_settings.MAX_COMMENT_LENGTH}
            request.user.message_set.create(message=message)

        return HttpResponseRedirect(answer.get_absolute_url())
    else:
        raise Http404
