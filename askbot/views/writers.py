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
from django.core.files.storage import FileSystemStorage
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseForbidden, Http404
from django.utils import simplejson
from django.utils.html import strip_tags
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

        # check file type
        f = request.FILES['file-upload']
        file_extension = os.path.splitext(f.name)[1].lower()
        if not file_extension in settings.ASKBOT_ALLOWED_UPLOAD_FILE_TYPES:
            file_types = "', '".join(settings.ASKBOT_ALLOWED_UPLOAD_FILE_TYPES)
            msg = _("allowed file types are '%(file_types)s'") % \
                    {'file_types': file_types}
            raise exceptions.PermissionDenied(msg)

        # generate new file name
        new_file_name = str(
                            time.time()
                        ).replace(
                            '.', 
                            str(random.randint(0,100000))
                        ) + file_extension

        file_storage = FileSystemStorage(
                    location = settings.ASKBOT_FILE_UPLOAD_DIR,
                    base_url = reverse('uploaded_file', kwargs = {'path':''}),
                )
        # use default storage to store file
        file_storage.save(new_file_name, f)
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
        file_url = file_storage.url(new_file_name)
    else:
        result = ''
        file_url = ''

    #<result><msg><![CDATA[%s]]></msg><error><![CDATA[%s]]></error><file_url>%s</file_url></result>
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
        if models.Question.objects.count() > 0:
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
@decorators.check_authorization_to_post(_('Please log in to ask questions'))
@decorators.check_spam('text')
def ask(request):#view used to ask a new question
    """a view to ask a new question
    gives space for q title, body, tags and checkbox for to post as wiki

    user can start posting a question anonymously but then
    must login/register in order for the question go be shown
    """
    if request.method == "POST":
        form = forms.AskForm(request.POST)
        if form.is_valid():
            timestamp = datetime.datetime.now()
            #todo: move this to clean_title
            title = form.cleaned_data['title'].strip()
            wiki = form.cleaned_data['wiki']
            #todo: move this to clean_tagnames
            tagnames = form.cleaned_data['tags'].strip()
            text = form.cleaned_data['text']
            ask_anonymously = form.cleaned_data['ask_anonymously']

            if request.user.is_authenticated():
                try:
                    question = request.user.post_question(
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
                question = models.AnonymousQuestion(
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
                question.save()
                return HttpResponseRedirect(url_utils.get_login_url())
        else:
            form = forms.AskForm(request.POST)
            if 'title' in request.GET:
                #normally this title is inherited from search query
                #but it is possible to ask with a parameter title in the url query
                form.initial['title'] = request.GET['title']
            else:
                #attempt to extract title from previous search query
                search_state = request.session.get('search_state', None)
                if search_state:
                    query = search_state.query
                    form.initial['title'] = query
    else:
        #this branch is for the initial load of ask form
        form = forms.AskForm()
        if 'title' in request.GET:
            #normally this title is inherited from search query
            #but it is possible to ask with a parameter title in the url query
            form.initial['title'] = request.GET['title']
        else:
            #attempt to extract title from previous search query
            search_state = request.session.get('search_state', None)
            if search_state:
                query = search_state.query
                form.initial['title'] = query

        if 'tags' in request.GET:
            #pre-populate tags.
            clean_tags = request.GET['tags'].replace(',', ' ')
            form.initial['tags'] = clean_tags
        else:
            #attemp to get tags from search state
            search_state = request.session.get('search_state', None)
            if search_state.tags:
                tags = ' '.join(search_state.tags)
                form.initial['tags'] = tags

    data = {
        'active_tab': 'ask',
        'page_class': 'ask-page',
        'form' : form,
        'mandatory_tags': models.tag.get_mandatory_tags(),
        'email_validation_faq_url':reverse('faq') + '#validate',
    }
    return render_into_skin('ask.html', data, request)

@login_required
#@csrf.csrf_protect remove for ajax
def retag_question(request, id):
    """retag question view
    """
    question = get_object_or_404(models.Question, id = id)

    try:
        request.user.assert_can_retag_question(question)
        if request.method == 'POST':
            form = forms.RetagQuestionForm(question, request.POST)
            if form.is_valid():
                if form.has_changed():
                    request.user.retag_question(
                                        question = question,
                                        tags = form.cleaned_data['tags']
                                    )
                if request.is_ajax():
                    response_data = {
                        'success': True,
                        'new_tags': question.tagnames
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
    question = get_object_or_404(models.Question, id = id)
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
                                                        question = question,
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
                            question.remove_author_anonymity()

                        is_anon_edit = form.cleaned_data['stay_anonymous']
                        is_wiki = form.cleaned_data.get('wiki', question.wiki)
                        request.user.edit_question(
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
    answer = get_object_or_404(models.Answer, id=id)
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
                                                            answer = answer,
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
                        request.user.edit_answer(
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
    question = get_object_or_404(models.Question, id=id)
    if request.method == "POST":
        form = forms.AnswerForm(question, request.user, request.POST)
        if form.is_valid():
            wiki = form.cleaned_data['wiki']
            text = form.cleaned_data['text']
            update_time = datetime.datetime.now()

            if request.user.is_authenticated():
                try:
                    follow = form.cleaned_data['email_notify']
                    answer = request.user.post_answer(
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
                anon = models.AnonymousAnswer(
                                       question=question,
                                       wiki=wiki,
                                       text=text,
                                       summary=strip_tags(text)[:120],
                                       session_key=request.session.session_key,
                                       ip_addr=request.META['REMOTE_ADDR'],
                                       )
                anon.save()
                return HttpResponseRedirect(url_utils.get_login_url())

    return HttpResponseRedirect(question.get_absolute_url())

def __generate_comments_json(obj, user):#non-view generates json data for the post comments
    """non-view generates json data for the post comments
    """
    comments = obj.get_comments(visitor = user)
    # {"Id":6,"PostId":38589,"CreationDate":"an hour ago","Text":"hello there!","UserDisplayName":"Jarrod Dixon","UserUrl":"/users/3/jarrod-dixon","DeleteUrl":null}
    json_comments = []
    for comment in comments:

        if user != None and user.is_authenticated():
            try:
                user.assert_can_delete_comment(comment)
                #/posts/392845/comments/219852/delete
                #todo translate this url
                is_deletable = True
            except exceptions.PermissionDenied:
                is_deletable = False
            is_editable = template_filters.can_edit_comment(comment.user, comment)
        else:
            is_deletable = False
            is_editable = False


        comment_owner = comment.get_owner()
        comment_data = {'id' : comment.id,
            'object_id': obj.id,
            'comment_age': diff_date(comment.added_at),
            'html': comment.html,
            'user_display_name': comment_owner.username,
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

@decorators.check_spam('comment')
def post_comments(request):#generic ajax handler to load comments to an object
    # only support get post comments by ajax now
    user = request.user
    if request.is_ajax():
        post_type = request.REQUEST['post_type']
        id = request.REQUEST['post_id']
        if post_type == 'question':
            post_model = models.Question
        elif post_type == 'answer':
            post_model = models.Answer
        else:
            raise Http404

        obj = get_object_or_404(post_model, id=id)
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
                user.post_comment(
                            parent_post = obj,
                            body_text = request.POST.get('comment')
                        )
                response = __generate_comments_json(obj, user)
            except exceptions.PermissionDenied, e:
                response = HttpResponseForbidden(
                                        unicode(e),
                                        mimetype="application/json"
                                    )
        return response
    else:
        raise Http404

@decorators.ajax_only
@decorators.check_spam('comment')
def edit_comment(request):
    if request.user.is_authenticated():
        comment_id = int(request.POST['comment_id'])
        comment = models.Comment.objects.get(id = comment_id)

        request.user.edit_comment(
                        comment = comment,
                        body_text = request.POST['comment']
                    )

        is_deletable = template_filters.can_delete_comment(comment.user, comment)
        is_editable = template_filters.can_edit_comment(comment.user, comment)

        return {'id' : comment.id,
            'object_id': comment.content_object.id,
            'comment_age': diff_date(comment.added_at),
            'html': comment.html,
            'user_display_name': comment.user.username,
            'user_url': comment.user.get_profile_url(),
            'user_id': comment.user.id,
            'is_deletable': is_deletable,
            'is_editable': is_editable,
            'score': comment.score,
            'voted': comment.is_upvoted_by(request.user),
        }
    else:
        raise exceptions.PermissionDenied(
                _('Sorry, anonymous users cannot edit comments')
            )

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
            comment = get_object_or_404(models.Comment, id=comment_id)
            request.user.assert_can_delete_comment(comment)

            obj = comment.content_object
            #todo: are the removed comments actually deleted?
            obj.comments.remove(comment)
            #attn: recalc denormalized field
            obj.comment_count = obj.comment_count - 1
            obj.save()

            return __generate_comments_json(obj, request.user)

        raise exceptions.PermissionDenied(
                    _('sorry, we seem to have some technical difficulties')
                )
    except exceptions.PermissionDenied, e:
        return HttpResponseForbidden(
                    unicode(e),
                    mimetype = 'application/json'
                )
