"""semi-views for the `group_messaging` application
These are not really views - rather context generator
functions, to be used separately, when needed.

For example, some other application can call these
in order to render messages within the page.

Notice that :mod:`urls` module decorates all these functions
and turns them into complete views
"""
import copy
from django.template.loader import get_template
from django.contrib.auth.models import User
from django.db import models
from django.forms import IntegerField
from django.http import HttpResponse
from django.http import HttpResponseNotAllowed
from django.http import HttpResponseForbidden
from django.utils import simplejson
from django.utils import timezone
from group_messaging.models import Message
from group_messaging.models import MessageMemo
from group_messaging.models import SenderList
from group_messaging.models import LastVisitTime
from group_messaging.models import get_personal_group_by_user_id
from group_messaging.models import get_personal_groups_for_users

class InboxView(object):
    """custom class-based view
    to be used for pjax use and for generation
    of content in the traditional way, where
    the only the :method:`get_context` would be used.
    """
    template_name = None #used only for the "GET" method
    http_method_names = ('GET', 'POST')

    def render_to_response(self, context, template_name=None):
        """like a django's shortcut, except will use
        template_name from self, if `template_name` is not given.
        Also, response is packaged as json with an html fragment
        for the pjax consumption
        """
        if template_name is None:
            template_name = self.template_name
        template = get_template(template_name)
        html = template.render(context)
        json = simplejson.dumps({'html': html, 'success': True})
        return HttpResponse(json, mimetype='application/json')
            

    def get(self, request, *args, **kwargs):
        """view function for the "GET" method"""
        context = self.get_context(request, *args, **kwargs)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        """view function for the "POST" method"""
        pass

    def dispatch(self, request, *args, **kwargs):
        """checks that the current request method is allowed
        and calls the corresponding view function"""
        if request.method not in self.http_method_names:
            return HttpResponseNotAllowed()
        view_func = getattr(self, request.method.lower())
        return view_func(request, *args, **kwargs)

    def get_context(self, request, *args, **kwargs):
        """Returns the context dictionary for the "get"
        method only"""
        return {}

    def as_view(self):
        """returns the view function - for the urls.py"""
        def view_function(request, *args, **kwargs):
            """the actual view function"""
            if request.user.is_authenticated() and request.is_ajax():
                view_method = getattr(self, request.method.lower())
                return view_method(request, *args, **kwargs)
            else:
                return HttpResponseForbidden()

        return view_function


class NewThread(InboxView):
    """view for creation of new thread"""
    http_method_list = ('POST',)

    def post(self, request):
        """creates a new thread on behalf of the user
        response is blank, because on the client side we just 
        need to go back to the thread listing view whose
        content should be cached in the client'
        """
        usernames = request.POST['to_usernames']
        usernames = map(lambda v: v.strip(), usernames.split(','))
        users = User.objects.filter(username__in=usernames)

        missing = copy.copy(usernames)
        for user in users:
            if user.username in missing:
                missing.remove(user.username)

        result = dict()
        if missing:
            result['success'] = False
            result['missing_users'] = missing

        if request.user.username in usernames:
            result['success'] = False
            result['self_message'] = True

        if result.get('success', True):
            recipients = get_personal_groups_for_users(users)
            message = Message.objects.create_thread(
                            sender=request.user,
                            recipients=recipients,
                            text=request.POST['text']
                        )
            result['success'] = True
            result['message_id'] = message.id
        return HttpResponse(simplejson.dumps(result), mimetype='application/json')


class PostReply(InboxView):
    """view to create a new response"""
    http_method_list = ('POST',)

    def post(self, request):
        parent_id = IntegerField().clean(request.POST['parent_id'])
        parent = Message.objects.get(id=parent_id)
        message = Message.objects.create_response(
                                        sender=request.user,
                                        text=request.POST['text'],
                                        parent=parent
                                    )
        last_visit = LastVisitTime.objects.get(
                                        message=message.root,
                                        user=request.user
                                    )
        last_visit.at = timezone.now()
        last_visit.save()
        return self.render_to_response(
            {'post': message, 'user': request.user},
            template_name='group_messaging/stored_message.html'
        )


class ThreadsList(InboxView):
    """shows list of threads for a given user"""  
    template_name = 'group_messaging/threads_list.html'
    http_method_list = ('GET',)

    def get_context(self, request):
        """returns thread list data"""
        #get threads and the last visit time
        sender_id = IntegerField().clean(request.REQUEST.get('sender_id', '-1'))
        if sender_id == -2:
            threads = Message.objects.get_threads(
                                            recipient=request.user,
                                            deleted=True
                                        )
        elif sender_id == -1:
            threads = Message.objects.get_threads(recipient=request.user)
        elif sender_id == request.user.id:
            threads = Message.objects.get_sent_threads(sender=request.user)
        else:
            sender = User.objects.get(id=sender_id)
            threads = Message.objects.get_threads(
                                            recipient=request.user,
                                            sender=sender
                                        )

        threads = threads.order_by('-last_active_at')

        #for each thread we need to know if there is something
        #unread for the user - to mark "new" threads as bold
        threads_data = dict()
        for thread in threads:
            thread_data = dict()
            #determine status
            thread_data['status'] = 'new'
            #determine the senders info
            senders_names = thread.senders_info.split(',')
            if request.user.username in senders_names:
                senders_names.remove(request.user.username)
            thread_data['senders_info'] = ', '.join(senders_names)
            thread_data['thread'] = thread
            threads_data[thread.id] = thread_data

        ids = [thread.id for thread in threads]
        counts = Message.objects.filter(
                                id__in=ids
                            ).annotate(
                                responses_count=models.Count('descendants')
                            ).values('id', 'responses_count')
        for count in counts:
            thread_id = count['id']
            responses_count = count['responses_count']
            threads_data[thread_id]['responses_count'] = responses_count

        last_visit_times = LastVisitTime.objects.filter(
                                            user=request.user,
                                            message__in=threads
                                        )
        for last_visit in last_visit_times:
            thread_data = threads_data[last_visit.message_id]
            if thread_data['thread'].last_active_at <= last_visit.at:
                thread_data['status'] = 'seen'

        return {
            'threads': threads,
            'threads_count': threads.count(),
            'threads_data': threads_data,
            'sender_id': sender_id
        }


class DeleteOrRestoreThread(ThreadsList):
    """subclassing :class:`ThreadsList`, because deletion
    or restoring of thread needs subsequent refreshing
    of the threads list"""

    http_method_list = ('POST',)

    def post(self, request, thread_id=None):
        """process the post request:
        * delete or restore thread
        * recalculate the threads list and return it for display
          by reusing the threads list "get" function
        """
        #part of the threads list context
        sender_id = IntegerField().clean(request.POST['sender_id'])

        #a little cryptic, but works - sender_id==-2 means deleted post
        if sender_id == -2:
            action = 'restore'
        else:
            action = 'delete'

        thread = Message.objects.get(id=thread_id)
        memo, created = MessageMemo.objects.get_or_create(
                                    user=request.user,
                                    message=thread
                                )
        if action == 'delete':
            memo.status = MessageMemo.ARCHIVED
        else:
            memo.status = MessageMemo.SEEN
        memo.save()

        context = self.get_context(request)
        return self.render_to_response(context)


class SendersList(InboxView):
    """shows list of senders for a user"""
    template_name = 'group_messaging/senders_list.html'
    http_method_names = ('GET',)

    def get_context(self, request):
        """get data about senders for the user"""
        senders = SenderList.objects.get_senders_for_user(request.user)
        senders = senders.values('id', 'username')
        return {'senders': senders, 'request_user_id': request.user.id}


class ThreadDetails(InboxView):
    """shows entire thread in the unfolded form"""
    template_name = 'group_messaging/thread_details.html'
    http_method_names = ('GET',)

    def get_context(self, request, thread_id=None):
        """shows individual thread"""
        #todo: assert that current thread is the root
        root = Message.objects.get(id=thread_id)
        responses = Message.objects.filter(root__id=thread_id)
        last_visit, created = LastVisitTime.objects.get_or_create(
                                                            message=root,
                                                            user=request.user
                                                        )
        if created is False:
            last_visit.at = timezone.now()
            last_visit.save()
        return {'root_message': root, 'responses': responses, 'request': request}
