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
from django.utils import simplejson, timezone
from django.utils.html import strip_tags, escape
from django.utils.translation import get_language
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.core.urlresolvers import reverse
from django.core import exceptions
from django.conf import settings
from django.views.decorators import csrf
from django.contrib.auth.models import User

from askbot import exceptions as askbot_exceptions
from askbot import forms
from askbot import models
from askbot.models import signals
from askbot.conf import settings as askbot_settings
from askbot.utils import decorators
from askbot.utils.forms import format_errors
from askbot.utils.functions import diff_date
from askbot.utils import url_utils
from askbot.utils.file_utils import store_file
from askbot.utils.loading import load_module
from askbot.views import context
from askbot.templatetags import extra_filters_jinja as template_filters
from askbot.importers.stackexchange import management as stackexchange#todo: may change
from askbot.utils.slug import slugify
from recaptcha_works.decorators import fix_recaptcha_remote_ip

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
        result, error, file_url, orig_file_name = None, '', None, None
        if request.user.is_anonymous():
            msg = _('Sorry, anonymous users cannot upload files')
            raise exceptions.PermissionDenied(msg)

        request.user.assert_can_upload_file()

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

        # generate new file name and storage object
        file_storage, new_file_name, file_url = store_file(
                                            uploaded_file, file_name_prefix
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
            #yield HttpResponse(_('StackExchange import complete.'), content_type='text/plain')
            #dump_storage.close()
    else:
        form = forms.DumpUploadForm()

    data = {
        'dump_upload_form': form,
        'need_configuration': (not stackexchange.is_ready())
    }
    return render(request, 'import_data.html', data)

@fix_recaptcha_remote_ip
@csrf.csrf_protect
@decorators.check_authorization_to_post(ugettext_lazy('Please log in to make posts'))
@decorators.check_spam('text')
def ask(request):#view used to ask a new question
    """a view to ask a new question
    gives space for q title, body, tags and checkbox for to post as wiki

    user can start posting a question anonymously but then
    must login/register in order for the question go be shown
    """
    if request.user.is_authenticated():
        if request.user.is_read_only():
            referer = request.META.get("HTTP_REFERER", reverse('questions'))
            request.user.message_set.create(message=_('Sorry, but you have only read access'))
            return HttpResponseRedirect(referer)

    if askbot_settings.READ_ONLY_MODE_ENABLED:
        return HttpResponseRedirect(reverse('index'))

    if request.method == 'POST':
        form = forms.AskForm(request.POST, user=request.user)
        if form.is_valid():
            timestamp = timezone.now()
            title = form.cleaned_data['title']
            wiki = form.cleaned_data['wiki']
            tagnames = form.cleaned_data['tags']
            text = form.cleaned_data['text']
            ask_anonymously = form.cleaned_data['ask_anonymously']
            post_privately = form.cleaned_data['post_privately']
            group_id = form.cleaned_data.get('group_id', None)
            language = form.cleaned_data.get('language', None)

            if request.user.is_authenticated():
                drafts = models.DraftQuestion.objects.filter(author=request.user)
                drafts.delete()
                user = form.get_post_user(request.user)
            elif request.user.is_anonymous() and askbot_settings.ALLOW_ASK_UNREGISTERED:
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
                        group_id=group_id,
                        language=language,
                        ip_addr=request.META.get('REMOTE_ADDR')
                    )
                    signals.new_question_posted.send(None,
                        question=question,
                        user=user,
                        form_data=form.cleaned_data
                    )
                    return HttpResponseRedirect(question.get_absolute_url())
                except exceptions.PermissionDenied, e:
                    request.user.message_set.create(message = unicode(e))
                    return HttpResponseRedirect(reverse('index'))

            else:
                request.session.flush()
                session_key=request.session.session_key
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

    draft_title = ''
    draft_text = ''
    draft_tagnames = ''
    if request.user.is_authenticated():
        drafts = models.DraftQuestion.objects.filter(author=request.user)
        if len(drafts) > 0:
            draft = drafts[0]
            draft_title = draft.title
            draft_text = draft.text
            draft_tagnames = draft.tagnames

    form.initial = {
        'ask_anonymously': request.REQUEST.get('ask_anonymously', False),
        'tags': request.REQUEST.get('tags', draft_tagnames),
        'text': request.REQUEST.get('text', draft_text),
        'title': request.REQUEST.get('title', draft_title),
        'post_privately': request.REQUEST.get('post_privately', False),
        'language': get_language(),
        'wiki': request.REQUEST.get('wiki', False),
    }
    if 'group_id' in request.REQUEST:
        try:
            group_id = int(request.GET.get('group_id', None))
            form.initial['group_id'] = group_id
        except Exception:
            pass

    data = {
        'active_tab': 'ask',
        'page_class': 'ask-page',
        'form' : form,
        'mandatory_tags': models.tag.get_mandatory_tags(),
        'email_validation_faq_url':reverse('faq') + '#validate',
        'category_tree_data': askbot_settings.CATEGORY_TREE,
        'tag_names': list()#need to keep context in sync with edit_question for tag editor
    }
    data.update(context.get_for_tag_editor())
    return render(request, 'ask.html', data)

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

                    if request.user.message_set.count() > 0:
                        #todo: here we will possibly junk messages
                        message = request.user.get_and_delete_messages()[-1]
                        response_data['message'] = message

                    data = simplejson.dumps(response_data)
                    return HttpResponse(data, content_type="application/json")
                else:
                    return HttpResponseRedirect(question.get_absolute_url())
            elif request.is_ajax():
                response_data = {
                    'message': format_errors(form.errors['tags']),
                    'success': False
                }
                data = simplejson.dumps(response_data)
                return HttpResponse(data, content_type="application/json")
        else:
            form = forms.RetagQuestionForm(question)

        data = {
            'active_tab': 'questions',
            'question': question,
            'form' : form,
        }
        return render(request, 'question_retag.html', data)
    except exceptions.PermissionDenied, e:
        if request.is_ajax():
            response_data = {
                'message': unicode(e),
                'success': False
            }
            data = simplejson.dumps(response_data)
            return HttpResponse(data, content_type="application/json")
        else:
            request.user.message_set.create(message = unicode(e))
            return HttpResponseRedirect(question.get_absolute_url())

@login_required
@csrf.csrf_protect
@decorators.check_spam('text')
@fix_recaptcha_remote_ip
def edit_question(request, id):
    """edit question view
    """
    question = get_object_or_404(models.Post, id=id)

    if askbot_settings.READ_ONLY_MODE_ENABLED:
        return HttpResponseRedirect(question.get_absolute_url())

    try:
        revision = question.revisions.get(revision=0)
    except models.PostRevision.DoesNotExist:
        revision = question.get_latest_revision()

    revision_form = None

    try:
        request.user.assert_can_edit_question(question)
        if request.method == 'POST':
            if request.POST['select_revision'] == 'true':
                #revert-type edit - user selected previous revision
                revision_form = forms.RevisionForm(
                                                question,
                                                revision,
                                                request.POST
                                            )
                if revision_form.is_valid():
                    # Replace with those from the selected revision
                    rev_id = revision_form.cleaned_data['revision']
                    revision = question.revisions.get(revision = rev_id)
                    form = forms.EditQuestionForm(
                                            question=question,
                                            user=request.user,
                                            revision=revision
                                        )
                else:
                    form = forms.EditQuestionForm(
                                            request.POST,
                                            question=question,
                                            user=question.user,
                                            revision=revision
                                        )
            else:#new content edit
                # Always check modifications against the latest revision
                form = forms.EditQuestionForm(
                                        request.POST,
                                        question=question,
                                        revision=revision,
                                        user=request.user,
                                    )
                revision_form = forms.RevisionForm(question, revision)
                if form.is_valid():
                    if form.has_changed():

                        if form.can_edit_anonymously() and form.cleaned_data['reveal_identity']:
                            question.thread.remove_author_anonymity()
                            question.is_anonymous = False

                        is_wiki = form.cleaned_data.get('wiki', question.wiki)
                        post_privately = form.cleaned_data['post_privately']
                        suppress_email = form.cleaned_data['suppress_email']

                        user = form.get_post_user(request.user)

                        user.edit_question(
                            question=question,
                            title=form.cleaned_data['title'],
                            body_text=form.cleaned_data['text'],
                            revision_comment=form.cleaned_data['summary'],
                            tags=form.cleaned_data['tags'],
                            wiki=is_wiki,
                            edit_anonymously=form.cleaned_data['edit_anonymously'],
                            is_private=post_privately,
                            suppress_email=suppress_email,
                            ip_addr=request.META.get('REMOTE_ADDR')
                        )

                        if 'language' in form.cleaned_data:
                            question.thread.set_language_code(form.cleaned_data['language'])

                    return HttpResponseRedirect(question.get_absolute_url())
        else:
            #request type was "GET"
            revision_form = forms.RevisionForm(question, revision)
            initial = {
                'language': question.thread.language_code,
                'post_privately': question.is_private(),
                'wiki': question.wiki
            }
            form = forms.EditQuestionForm(
                                    question=question,
                                    revision=revision,
                                    user=request.user,
                                    initial=initial
                                )

        data = {
            'page_class': 'edit-question-page',
            'active_tab': 'questions',
            'question': question,
            'revision': revision,
            'revision_form': revision_form,
            'mandatory_tags': models.tag.get_mandatory_tags(),
            'form' : form,
            'tag_names': question.thread.get_tag_names(),
            'category_tree_data': askbot_settings.CATEGORY_TREE
        }
        data.update(context.get_for_tag_editor())
        return render(request, 'question_edit.html', data)

    except exceptions.PermissionDenied, e:
        request.user.message_set.create(message = unicode(e))
        return HttpResponseRedirect(question.get_absolute_url())

@login_required
@csrf.csrf_protect
@decorators.check_spam('text')
@fix_recaptcha_remote_ip
def edit_answer(request, id):
    answer = get_object_or_404(models.Post, id=id)

    if askbot_settings.READ_ONLY_MODE_ENABLED:
        return HttpResponseRedirect(answer.get_absolute_url())

    try:
        revision = answer.revisions.get(revision=0)
    except models.PostRevision.DoesNotExist:
        revision = answer.get_latest_revision()

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
                        user.edit_answer(
                            answer=answer,
                            body_text=form.cleaned_data['text'],
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
            'page_class': 'edit-answer-page',
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

    except exceptions.PermissionDenied, e:
        request.user.message_set.create(message = unicode(e))
        return HttpResponseRedirect(answer.get_absolute_url())

#todo: rename this function to post_new_answer
@decorators.check_authorization_to_post(ugettext_lazy('Please log in to make posts'))
@decorators.check_spam('text')
@fix_recaptcha_remote_ip
def answer(request, id, form_class=forms.AnswerForm):#process a new answer
    """view that posts new answer

    anonymous users post into anonymous storage
    and redirected to login page

    authenticated users post directly
    """
    question = get_object_or_404(models.Post, post_type='question', id=id)

    if askbot_settings.READ_ONLY_MODE_ENABLED:
        return HttpResponseRedirect(question.get_absolute_url())

    if request.method == "POST":

        #this check prevents backward compatilibility
        if form_class == forms.AnswerForm:
            custom_class_path = getattr(settings, 'ASKBOT_NEW_ANSWER_FORM', None)
            if custom_class_path:
                form_class = load_module(custom_class_path)
            else:
                form_class = forms.AnswerForm

        form = form_class(request.POST, user=request.user)

        if form.is_valid():
            if request.user.is_authenticated():
                drafts = models.DraftAnswer.objects.filter(
                                                author=request.user,
                                                thread=question.thread
                                            )
                drafts.delete()
                user = form.get_post_user(request.user)
                try:
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
                except askbot_exceptions.AnswerAlreadyGiven, e:
                    request.user.message_set.create(message = unicode(e))
                    answer = question.thread.get_answers_by_user(user)[0]
                    return HttpResponseRedirect(answer.get_absolute_url())
                except exceptions.PermissionDenied, e:
                    request.user.message_set.create(message = unicode(e))
            else:
                request.session.flush()
                models.AnonymousAnswer.objects.create(
                    question=question,
                    wiki=form.cleaned_data['wiki'],
                    text=form.cleaned_data['text'],
                    session_key=request.session.session_key,
                    ip_addr=request.META.get('REMOTE_ADDR'),
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
            'user_url': comment_owner.get_profile_url(),
            'user_id': comment_owner.id,
            'is_deletable': is_deletable,
            'is_editable': is_editable,
            'points': comment.points,
            'score': comment.points, #to support js
            'upvoted_by_user': getattr(comment, 'upvoted_by_user', False)
        }
        json_comments.append(comment_data)

    data = simplejson.dumps(json_comments)
    return HttpResponse(data, content_type="application/json")

@csrf.csrf_exempt
@decorators.check_spam('comment')
def post_comments(request):#generic ajax handler to load comments to an object
    """todo: fixme: post_comments is ambigous:
    means either get comments for post or
    add a new comment to post
    """
    # only support get post comments by ajax now

    post_type = request.REQUEST.get('post_type', '')
    if not request.is_ajax() or post_type not in ('question', 'answer'):
        raise Http404  # TODO: Shouldn't be 404! More like 400, 403 or sth more specific

    user = request.user

    if request.method == 'POST':
        form = forms.NewCommentForm(request.POST)
    elif request.method == 'GET':
        form = forms.GetDataForPostForm(request.GET)

    if form.is_valid() == False:
        return HttpResponseBadRequest(
            _('This content is forbidden'),
            mimetype='application/json'
        )

    post_id = form.cleaned_data['post_id']
    try:
        post = models.Post.objects.get(id=post_id)
    except models.Post.DoesNotExist:
        return HttpResponseBadRequest(
            _('Post not found'), mimetype='application/json'
        )

    if request.method == "GET":
        response = __generate_comments_json(post, user)
    elif request.method == "POST":
        try:
            if user.is_anonymous():
                msg = _('Sorry, you appear to be logged out and '
                        'cannot post comments. Please '
                        '<a href="%(sign_in_url)s">sign in</a>.') % \
                        {'sign_in_url': url_utils.get_login_url()}
                raise exceptions.PermissionDenied(msg)

            if askbot_settings.READ_ONLY_MODE_ENABLED:
                raise exceptions.PermissionDenied(askbot_settings.READ_ONLY_MESSAGE)

            comment = user.post_comment(
                parent_post=post, 
                body_text=form.cleaned_data['comment'],
                ip_addr=request.META.get('REMOTE_ADDR')
            )
            signals.new_comment_posted.send(None,
                comment=comment,
                user=user,
                form_data=form.cleaned_data
            )
            response = __generate_comments_json(post, user)
        except exceptions.PermissionDenied, e:
            response = HttpResponseForbidden(unicode(e), content_type="application/json")

    return response

@csrf.csrf_exempt
@decorators.ajax_only
#@decorators.check_spam('comment')
def edit_comment(request):
    if request.user.is_anonymous():
        raise exceptions.PermissionDenied(_('Sorry, anonymous users cannot edit comments'))

    if askbot_settings.READ_ONLY_MODE_ENABLED:
        raise exceptions.PermissionDenied(askbot_settings.READ_ONLY_MESSAGE)

    form = forms.EditCommentForm(request.POST)
    if form.is_valid() == False:
        raise exceptions.PermissionDenied('This content is forbidden')

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
            #attn: recalc denormalized field
            parent.comment_count = parent.comments.count()
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

@login_required
@decorators.post_only
@csrf.csrf_protect
def comment_to_answer(request):
    if request.user.is_anonymous():
        msg = _('Sorry, only logged in users can convert comments to answers. '
                'Please <a href="%(sign_in_url)s">sign in</a>.') % \
                {'sign_in_url': url_utils.get_login_url()}
        raise exceptions.PermissionDenied(msg)

    form = forms.ProcessCommentForm(request.POST)
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
    if request.user.is_anonymous():
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

        if destination_post is None:
            message = _('Error - could not find the destination post')
            request.user.message_set.create(message=message)
            return HttpResponseRedirect(answer.get_absolute_url())

        if len(answer.text) <= askbot_settings.MAX_COMMENT_LENGTH:
            answer.post_type = 'comment'
            answer.parent = destination_post

            new_comment_count = answer.comments.count() + 1
            answer.comment_count = 0

            answer_comments = models.Post.objects.get_comments().filter(parent=answer)
            answer_comments.update(parent=destination_post)

            #why this and not just "save"?
            answer.parse_and_save(author=answer.author)
            answer.thread.update_answer_count()

            answer.parent.comment_count += new_comment_count
            answer.parent.save()

            answer.thread.invalidate_cached_data()
        else:
            message = _(
                'Cannot convert, because text has more characters than '
                '%(max_chars)s - maximum allowed for comments'
            ) % {'max_chars': askbot_settings.MAX_COMMENT_LENGTH}
            request.user.message_set.create(message=message)

        return HttpResponseRedirect(answer.get_absolute_url())
    else:
        raise Http404
