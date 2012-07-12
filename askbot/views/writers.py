# encoding:utf-8
"""
:synopsis: views diplaying and processing main content post forms

This module contains views that allow adding, editing, and deleting main textual content.
"""
import datetime
import logging
import os
import os.path
import random
import sys
import tempfile
import time
import urlparse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseForbidden, Http404
from django.utils import simplejson
from django.utils.html import strip_tags, escape
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from django.core import exceptions
from django.conf import settings
from django.views.decorators import csrf

from askbot import forms
from askbot import models
from askbot.skins.loaders import render_into_skin
from askbot.utils import decorators
from askbot.utils.functions import diff_date
from askbot.utils import url_utils
from askbot.utils.file_utils import store_file
from askbot.utils.forms import post_as_user
from askbot.templatetags import extra_filters_jinja as template_filters
from askbot.importers.stackexchange import management as stackexchange#todo: may change

# used in index page
INDEX_PAGE_SIZE = 20
INDEX_AWARD_SIZE = 15
INDEX_TAGS_SIZE = 100
# used in tags list
DEFAULT_PAGE_SIZE = 60
# used in questions
QUESTIONS_PAGE_SIZE = 10
# used in answers
ANSWERS_PAGE_SIZE = 10

@csrf.csrf_exempt
def upload(request):#ajax upload file to a question or answer 
    """view that handles file upload via Ajax
    """

    # check upload permission
    result = ''
    error = ''
    new_file_name = ''
    try:
        #may raise exceptions.PermissionDenied
        if request.user.is_anonymous():
            msg = _('Sorry, anonymous users cannot upload files')
            raise exceptions.PermissionDenied(msg)

        request.user.assert_can_upload_file()

        #todo: build proper form validation
        file_name_prefix = request.POST.get('file_name_prefix', '')
        if file_name_prefix not in ('', 'group_logo_'):
            raise exceptions.PermissionDenied('invalid upload file name prefix')
        
        # check file type
        f = request.FILES['file-upload']
        #todo: extension checking should be replaced with mimetype checking
        #and this must be part of the form validation
        file_extension = os.path.splitext(f.name)[1].lower()
        if not file_extension in settings.ASKBOT_ALLOWED_UPLOAD_FILE_TYPES:
            file_types = "', '".join(settings.ASKBOT_ALLOWED_UPLOAD_FILE_TYPES)
            msg = _("allowed file types are '%(file_types)s'") % \
                    {'file_types': file_types}
            raise exceptions.PermissionDenied(msg)

        # generate new file name and storage object
        file_storage, new_file_name, file_url = store_file(
                                            f, file_name_prefix
                                        )
        # check file size
        # byte
        size = file_storage.size(new_file_name)
        if size > settings.ASKBOT_MAX_UPLOAD_FILE_SIZE:
            file_storage.delete(new_file_name)
            msg = _("maximum upload file size is %(file_size)sK") % \
                    {'file_size': settings.ASKBOT_MAX_UPLOAD_FILE_SIZE}
            raise exceptions.PermissionDenied(msg)

    except exceptions.PermissionDenied, e:
        error = unicode(e)
    except Exception, e:
        logging.critical(unicode(e))
        error = _('Error uploading file. Please contact the site administrator. Thank you.')

    if error == '':
        result = 'Good'
    else:
        result = ''
        file_url = ''

    #data = simplejson.dumps({
    #    'result': result,
    #    'error': error,
    #    'file_url': file_url
    #})
    #return HttpResponse(data, mimetype = 'application/json')
    xml_template = "<result><msg><![CDATA[%s]]></msg><error><![CDATA[%s]]></error><file_url>%s</file_url></result>"
    xml = xml_template % (result, error, file_url)

    return HttpResponse(xml, mimetype="application/xml")

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
    if request.user.is_anonymous() or (not request.user.is_administrator()):
        if models.Post.objects.get_questions().exists():
            raise Http404

    if request.method == 'POST':
        #if not request.is_ajax():
        #    raise Http404

        form = forms.DumpUploadForm(request.POST, request.FILES)
        if form.is_valid():
            dump_file = form.cleaned_data['dump_file']
            dump_storage = tempfile.NamedTemporaryFile()

            #save the temp file
            for chunk in dump_file.chunks():
                dump_storage.write(chunk)
            dump_storage.flush()

            return HttpResponse(__import_se_data(dump_storage))
            #yield HttpResponse(_('StackExchange import complete.'), mimetype='text/plain')
            #dump_storage.close()
    else:
        form = forms.DumpUploadForm()

    data = {
        'dump_upload_form': form,
        'need_configuration': (not stackexchange.is_ready())
    }
    return render_into_skin('import_data.html', data, request)

#@login_required #actually you can post anonymously, but then must register
@csrf.csrf_protect
@decorators.check_authorization_to_post(_(
    "<span class=\"strong big\">You are welcome to start submitting your question "
    "anonymously</span>. When you submit the post, you will be redirected to the "
    "login/signup page. Your question will be saved in the current session and "
    "will be published after you log in. Login/signup process is very simple. "
    "Login takes about 30 seconds, initial signup takes a minute or less."
))
@decorators.check_spam('text')
def ask(request):#view used to ask a new question
    """a view to ask a new question
    gives space for q title, body, tags and checkbox for to post as wiki

    user can start posting a question anonymously but then
    must login/register in order for the question go be shown
    """
    form = forms.AskForm(request.REQUEST)
    if request.method == 'POST':
        if form.is_valid():
            timestamp = datetime.datetime.now()
            title = form.cleaned_data['title']
            wiki = form.cleaned_data['wiki']
            tagnames = form.cleaned_data['tags']
            text = form.cleaned_data['text']
            ask_anonymously = form.cleaned_data['ask_anonymously']

            if request.user.is_authenticated():

                user = post_as_user(request.user, form)
               
                try:
                    question = user.post_question(
                        title = title,
                        body_text = text,
                        tags = tagnames,
                        wiki = wiki,
                        is_anonymous = ask_anonymously,
                        timestamp = timestamp
                    )
                    return HttpResponseRedirect(question.get_absolute_url())
                except exceptions.PermissionDenied, e:
                    request.user.message_set.create(message = unicode(e))
                    return HttpResponseRedirect(reverse('index'))

            else:
                request.session.flush()
                session_key = request.session.session_key
                summary = strip_tags(text)[:120]
                models.AnonymousQuestion.objects.create(
                    session_key = session_key,
                    title       = title,
                    tagnames = tagnames,
                    wiki = wiki,
                    is_anonymous = ask_anonymously,
                    text = text,
                    summary = summary,
                    added_at = timestamp,
                    ip_addr = request.META['REMOTE_ADDR'],
                )
                return HttpResponseRedirect(url_utils.get_login_url())

    if request.method == 'GET':
        form = forms.AskForm()

    form.initial = {
        'title': request.REQUEST.get('title', ''),
        'text': request.REQUEST.get('text', ''),
        'tags': request.REQUEST.get('tags', ''),
        'wiki': request.REQUEST.get('wiki', False),
        'is_anonymous': request.REQUEST.get('is_anonymous', False),
    }

    data = {
        'active_tab': 'ask',
        'page_class': 'ask-page',
        'form' : form,
        'mandatory_tags': models.tag.get_mandatory_tags(),
        'email_validation_faq_url':reverse('faq') + '#validate',
    }
    return render_into_skin('ask.html', data, request)

@login_required
@csrf.csrf_exempt
def retag_question(request, id):
    """retag question view
    """
    question = get_object_or_404(models.Post, id=id)

    try:
        request.user.assert_can_retag_question(question)
        if request.method == 'POST':
            form = forms.RetagQuestionForm(question, request.POST)
            if form.is_valid():
                if form.has_changed():
                    request.user.retag_question(question=question, tags=form.cleaned_data['tags'])
                if request.is_ajax():
                    response_data = {
                        'success': True,
                        'new_tags': question.thread.tagnames
                    }
                    data = simplejson.dumps(response_data)
                    return HttpResponse(data, mimetype="application/json")
                else:
                    return HttpResponseRedirect(question.get_absolute_url())
            elif request.is_ajax():
                response_data = {
                    'message': unicode(form.errors['tags']),
                    'success': False
                }
                data = simplejson.dumps(response_data)
                return HttpResponse(data, mimetype="application/json")
        else:
            form = forms.RetagQuestionForm(question)

        data = {
            'active_tab': 'questions',
            'question': question,
            'form' : form,
        }
        return render_into_skin('question_retag.html', data, request)
    except exceptions.PermissionDenied, e:
        if request.is_ajax():
            response_data = {
                'message': unicode(e),
                'success': False
            }
            data = simplejson.dumps(response_data)
            return HttpResponse(data, mimetype="application/json")
        else:
            request.user.message_set.create(message = unicode(e))
            return HttpResponseRedirect(question.get_absolute_url())

@login_required
@csrf.csrf_protect
@decorators.check_spam('text')
def edit_question(request, id):
    """edit question view
    """
    question = get_object_or_404(models.Post, id=id)
    latest_revision = question.get_latest_revision()
    revision_form = None
    try:
        request.user.assert_can_edit_question(question)
        if request.method == 'POST':
            if 'select_revision' in request.POST:
                #revert-type edit - user selected previous revision
                revision_form = forms.RevisionForm(
                                                question,
                                                latest_revision,
                                                request.POST
                                            )
                if revision_form.is_valid():
                    # Replace with those from the selected revision
                    rev_id = revision_form.cleaned_data['revision']
                    selected_revision = models.PostRevision.objects.question_revisions().get(
                                                        post = question,
                                                        revision = rev_id
                                                    )
                    form = forms.EditQuestionForm(
                                            question = question,
                                            user = request.user,
                                            revision = selected_revision
                                        )
                else:
                    form = forms.EditQuestionForm(
                                            request.POST,
                                            question = question,
                                            user = request.user,
                                            revision = latest_revision
                                        )
            else:#new content edit
                # Always check modifications against the latest revision
                form = forms.EditQuestionForm(
                                        request.POST,
                                        question = question,
                                        revision = latest_revision,
                                        user = request.user,
                                    )
                revision_form = forms.RevisionForm(question, latest_revision)
                if form.is_valid():
                    if form.has_changed():

                        if form.cleaned_data['reveal_identity']:
                            question.thread.remove_author_anonymity()

                        is_anon_edit = form.cleaned_data['stay_anonymous']
                        is_wiki = form.cleaned_data.get('wiki', question.wiki)

                        user = post_as_user(request.user, form, userfield='user_author')
                        user.edit_question(
                            question = question,
                            title = form.cleaned_data['title'],
                            body_text = form.cleaned_data['text'],
                            revision_comment = form.cleaned_data['summary'],
                            tags = form.cleaned_data['tags'],
                            wiki = is_wiki, 
                            edit_anonymously = is_anon_edit,
                        )
                    return HttpResponseRedirect(question.get_absolute_url())
        else:
            #request type was "GET"
            revision_form = forms.RevisionForm(question, latest_revision)
            form = forms.EditQuestionForm(
                                    question = question,
                                    revision = latest_revision,
                                    user = request.user
                                )

        data = {
            'page_class': 'edit-question-page',
            'active_tab': 'questions',
            'question': question,
            'revision_form': revision_form,
            'mandatory_tags': models.tag.get_mandatory_tags(),
            'form' : form,
        }
        return render_into_skin('question_edit.html', data, request)

    except exceptions.PermissionDenied, e:
        request.user.message_set.create(message = unicode(e))
        return HttpResponseRedirect(question.get_absolute_url())

@login_required
@csrf.csrf_protect
@decorators.check_spam('text')
def edit_answer(request, id):
    answer = get_object_or_404(models.Post, id=id)
    latest_revision = answer.get_latest_revision()
    try:
        request.user.assert_can_edit_answer(answer)
        latest_revision = answer.get_latest_revision()
        if request.method == "POST":
            if 'select_revision' in request.POST:
                # user has changed revistion number
                revision_form = forms.RevisionForm(
                                                answer, 
                                                latest_revision,
                                                request.POST
                                            )
                if revision_form.is_valid():
                    # Replace with those from the selected revision
                    rev = revision_form.cleaned_data['revision']
                    selected_revision = models.PostRevision.objects.answer_revisions().get(
                                                            post = answer,
                                                            revision = rev
                                                        )
                    form = forms.EditAnswerForm(answer, selected_revision)
                else:
                    form = forms.EditAnswerForm(
                                            answer,
                                            latest_revision,
                                            request.POST
                                        )
            else:
                form = forms.EditAnswerForm(answer, latest_revision, request.POST)
                revision_form = forms.RevisionForm(answer, latest_revision)

                if form.is_valid():
                    if form.has_changed():
                        user = post_as_user(request.user, form)
                        user.edit_answer(
                                answer = answer,
                                body_text = form.cleaned_data['text'],
                                revision_comment = form.cleaned_data['summary'],
                                wiki = form.cleaned_data.get('wiki', answer.wiki),
                                #todo: add wiki field to form
                            )
                    return HttpResponseRedirect(answer.get_absolute_url())
        else:
            revision_form = forms.RevisionForm(answer, latest_revision)
            form = forms.EditAnswerForm(answer, latest_revision)
        data = {
            'page_class': 'edit-answer-page',
            'active_tab': 'questions',
            'answer': answer,
            'revision_form': revision_form,
            'form': form,
        }
        return render_into_skin('answer_edit.html', data, request)

    except exceptions.PermissionDenied, e:
        request.user.message_set.create(message = unicode(e))
        return HttpResponseRedirect(answer.get_absolute_url())

#todo: rename this function to post_new_answer
@decorators.check_authorization_to_post(_('Please log in to answer questions'))
@decorators.check_spam('text')
def answer(request, id):#process a new answer
    """view that posts new answer

    anonymous users post into anonymous storage
    and redirected to login page

    authenticated users post directly
    """
    question = get_object_or_404(models.Post, post_type='question', id=id)
    if request.method == "POST":
        form = forms.AnswerForm(request.POST)
        if form.is_valid():
            wiki = form.cleaned_data['wiki']
            text = form.cleaned_data['text']
            update_time = datetime.datetime.now()

            if request.user.is_authenticated():
                try:
                    follow = form.cleaned_data['email_notify']

                    user = post_as_user(request.user, form)

                    answer = user.post_answer(
                                        question = question,
                                        body_text = text,
                                        follow = follow,
                                        wiki = wiki,
                                        timestamp = update_time,
                                    )
                    return HttpResponseRedirect(answer.get_absolute_url())
                except exceptions.PermissionDenied, e:
                    request.user.message_set.create(message = unicode(e))
            else:
                request.session.flush()
                models.AnonymousAnswer.objects.create(
                    question=question,
                    wiki=wiki,
                    text=text,
                    summary=strip_tags(text)[:120],
                    session_key=request.session.session_key,
                    ip_addr=request.META['REMOTE_ADDR'],
                )
                return HttpResponseRedirect(url_utils.get_login_url())

    return HttpResponseRedirect(question.get_absolute_url())

def __generate_comments_json(obj, user):#non-view generates json data for the post comments
    """non-view generates json data for the post comments
    """
    models.Post.objects.precache_comments(for_posts=[obj], visitor=user)
    comments = obj._cached_comments

    # {"Id":6,"PostId":38589,"CreationDate":"an hour ago","Text":"hello there!","UserDisplayName":"Jarrod Dixon","UserUrl":"/users/3/jarrod-dixon","DeleteUrl":null}
    json_comments = []
    for comment in comments:

        if user and user.is_authenticated():
            try:
                user.assert_can_delete_comment(comment)
                #/posts/392845/comments/219852/delete
                #todo translate this url
                is_deletable = True
            except exceptions.PermissionDenied:
                is_deletable = False
            is_editable = template_filters.can_edit_comment(comment.author, comment)
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
            'user_url': comment_owner.get_profile_url(),
            'user_id': comment_owner.id,
            'is_deletable': is_deletable,
            'is_editable': is_editable,
            'score': comment.score,
            'upvoted_by_user': getattr(comment, 'upvoted_by_user', False)
        }
        json_comments.append(comment_data)

    data = simplejson.dumps(json_comments)
    return HttpResponse(data, mimetype="application/json")

@csrf.csrf_exempt
@decorators.check_spam('comment')
def post_comments(request):#generic ajax handler to load comments to an object
    # only support get post comments by ajax now

    post_type = request.REQUEST.get('post_type', '')
    if not request.is_ajax() or post_type not in ('question', 'answer'):
        raise Http404  # TODO: Shouldn't be 404! More like 400, 403 or sth more specific

    user = request.user

    id = request.REQUEST['post_id']
    obj = get_object_or_404(models.Post, id=id)

    if request.method == "GET":
        response = __generate_comments_json(obj, user)
    elif request.method == "POST":
        try:
            if user.is_anonymous():
                msg = _('Sorry, you appear to be logged out and '
                        'cannot post comments. Please '
                        '<a href="%(sign_in_url)s">sign in</a>.') % \
                        {'sign_in_url': url_utils.get_login_url()}
                raise exceptions.PermissionDenied(msg)
            user.post_comment(parent_post=obj, body_text=request.POST.get('comment'))
            response = __generate_comments_json(obj, user)
        except exceptions.PermissionDenied, e:
            response = HttpResponseForbidden(unicode(e), mimetype="application/json")

    return response

@csrf.csrf_exempt
@decorators.ajax_only
@decorators.check_spam('comment')
def edit_comment(request):
    if request.user.is_anonymous():
        raise exceptions.PermissionDenied(_('Sorry, anonymous users cannot edit comments'))

    comment_id = int(request.POST['comment_id'])
    comment_post = models.Post.objects.get(post_type='comment', id=comment_id)

    request.user.edit_comment(comment_post=comment_post, body_text = request.POST['comment'])

    is_deletable = template_filters.can_delete_comment(comment_post.author, comment_post)
    is_editable = template_filters.can_edit_comment(comment_post.author, comment_post)
    tz = ' ' + template_filters.TIMEZONE_STR

    return {
        'id' : comment_post.id,
        'object_id': comment_post.parent.id,
        'comment_added_at': str(comment_post.added_at.replace(microsecond = 0)) + tz,
        'html': comment_post.html,
        'user_display_name': comment_post.author.username,
        'user_url': comment_post.author.get_profile_url(),
        'user_id': comment_post.author.id,
        'is_deletable': is_deletable,
        'is_editable': is_editable,
        'score': comment_post.score,
        'voted': comment_post.is_upvoted_by(request.user),
    }

@csrf.csrf_exempt
def delete_comment(request):
    """ajax handler to delete comment
    """
    try:
        if request.user.is_anonymous():
            msg = _('Sorry, you appear to be logged out and '
                    'cannot delete comments. Please '
                    '<a href="%(sign_in_url)s">sign in</a>.') % \
                    {'sign_in_url': url_utils.get_login_url()}
            raise exceptions.PermissionDenied(msg)
        if request.is_ajax():

            comment_id = request.POST['comment_id']
            comment = get_object_or_404(models.Post, post_type='comment', id=comment_id)
            request.user.assert_can_delete_comment(comment)

            parent = comment.parent
            comment.delete()
            #attn: recalc denormalized field
            parent.comment_count = parent.comment_count - 1
            parent.save()
            parent.thread.invalidate_cached_data()

            return __generate_comments_json(parent, request.user)

        raise exceptions.PermissionDenied(
                    _('sorry, we seem to have some technical difficulties')
                )
    except exceptions.PermissionDenied, e:
        return HttpResponseForbidden(
                    unicode(e),
                    mimetype = 'application/json'
                )
