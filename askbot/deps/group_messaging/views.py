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
from django.template import Context
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.forms import IntegerField
from django.http import HttpResponse
from django.http import HttpResponseNotAllowed
from django.http import HttpResponseForbidden
import json
from django.utils import timezone
from askbot.utils.views import PjaxView
from askbot.deps.group_messaging.models import Message
from askbot.deps.group_messaging.models import MessageMemo
from askbot.deps.group_messaging.models import SenderList
from askbot.deps.group_messaging.models import LastVisitTime
from askbot.deps.group_messaging.models import get_personal_group_by_user_id
from askbot.deps.group_messaging.models import get_personal_groups_for_users
from askbot.deps.group_messaging.models import get_unread_inbox_counter

# Notifications section
#elif section == 'messages':
#    #this is for the private messaging feature
#    if request.user != user:
#        if askbot_settings.ADMIN_INBOX_ACCESS_ENABLED == False:
#            raise Http404
#        elif not(request.user.is_moderator() or request.user.is_administrator()):
#            raise Http404

#    from askbot.deps.group_messaging.views import SendersList, ThreadsList
#    context.update(SendersList().get_context(request))
#    context.update(ThreadsList().get_context(request, user))
#    data = {
#        'inbox_threads_count': context['threads_count'],#a hackfor the inbox count
#        'active_tab':'users',
#        'tab_name' : 'inbox',
#        'inbox_section': section,
#        'page_title' : _('profile - messages')
#    }
#    context.update(data)
#    if 'thread_id' in request.GET:
#        from askbot.deps.group_messaging.models import Message
#        from askbot.deps.group_messaging.views import ThreadDetails
#        try:
#            thread_id = request.GET['thread_id']
#            context.update(ThreadDetails().get_context(request, thread_id))
#            context['group_messaging_template_name'] = \
#                'group_messaging/home_thread_details.html'
#        except Message.DoesNotExist:
#            raise Http404
#    else:
#        context['group_messaging_template_name'] = 'group_messaging/home.html'
#        #here we take shortcut, because we don't care about
#        #all the extra context loaded below
#    return render(request, 'user_inbox/messages.html', context)


class NewThread(PjaxView):
    """view for creation of new thread"""
    http_method_list = ('POST',)

    def post(self, request):
        """creates a new thread on behalf of the user
        response is blank, because on the client side we just
        need to go back to the thread listing view whose
        content should be cached in the client'
        """
        usernames = request.POST['to_usernames']
        usernames = [v.strip() for v in usernames.split(',')]
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
        return HttpResponse(json.dumps(result), content_type='application/json')


class PostReply(PjaxView):
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
            Context({'post': message, 'user': request.user}),
            template_name='group_messaging/stored_message.html'
        )


class ThreadsList(PjaxView):
    """shows list of threads for a given user"""
    template_name = 'group_messaging/threads_list.html'
    http_method_list = ('GET',)

    def get_context(self, request, *args):
        """returns thread list data"""

        if len(args):
            user = args[0]
        else:
            user = request.user

        #get threads and the last visit time
        sender_id = IntegerField().clean(request.GET.get('sender_id',request.POST.get('sender_id', '-1')))

        if sender_id == -2:
            received = Message.objects.get_threads(recipient=user, deleted=True)
            sent = Message.objects.get_threads(sender=user, deleted=True)
            threads = (received | sent).distinct()
        elif sender_id == -1:
            threads = Message.objects.get_threads(recipient=user)
        elif sender_id == user.id:
            threads = Message.objects.get_sent_threads(sender=user)
        else:
            sender = User.objects.get(id=sender_id)
            threads = Message.objects.get_threads(
                                            recipient=user,
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
            if user.username in senders_names:
                senders_names.remove(user.username)
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
                                            user=user,
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

    def __init__(self, action, *args, **kwargs):
        self.thread_action = action or 'delete'
        super().__init__(*args, **kwargs)

    def post(self, request, thread_id=None):
        """process the post request:
        * delete or restore thread
        * recalculate the threads list and return it for display
          by reusing the threads list "get" function
        """
        #part of the threads list context
        sender_id = IntegerField().clean(request.POST['sender_id'])

        #sender_id==-2 means deleted post
        if self.thread_action == 'delete':
            if sender_id == -2:
                action = 'delete'
            else:
                action = 'archive'
        else:
            action = 'restore'

        thread = Message.objects.get(id=thread_id)
        memo, created = MessageMemo.objects.get_or_create(
                                    user=request.user,
                                    message=thread
                                )

        if created and action == 'archive':
            #unfortunately we lose "unseen" status when archiving
            counter = get_unread_inbox_counter(request.user)
            counter.decrement()
            counter.save()

        if action == 'archive':
            memo.status = MessageMemo.ARCHIVED
        elif action == 'restore':
            memo.status = MessageMemo.SEEN
        else:
            memo.status = MessageMemo.DELETED
        memo.save()

        context = self.get_context(request)
        return self.render_to_response(Context(context))


class SendersList(PjaxView):
    """shows list of senders for a user"""
    template_name = 'group_messaging/senders_list.html'
    http_method_names = ('GET',)

    def get_context(self, request):
        """get data about senders for the user"""
        senders = SenderList.objects.get_senders_for_user(request.user)
        senders = senders.values('id', 'username')
        return {'senders': senders, 'request_user_id': request.user.id}


class ThreadDetails(PjaxView):
    """shows entire thread in the unfolded form"""
    template_name = 'group_messaging/thread_details.html'
    http_method_names = ('GET',)

    def get_context(self, request, thread_id=None):
        """shows individual thread"""
        #todo: assert that current thread is the root
        root = Message.objects.get(id=thread_id)
        responses = Message.objects.filter(root__id=thread_id).order_by('sent_at')
        last_visit, created = LastVisitTime.objects.get_or_create(
                                                            message=root,
                                                            user=request.user
                                                        )
        root.mark_as_seen(request.user)
        if created is False:
            last_visit.at = timezone.now()
            last_visit.save()

        return {
            'root_message': root,
            'responses': responses,
            'request': request
        }
