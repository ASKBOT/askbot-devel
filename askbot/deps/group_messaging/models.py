"""models for the ``group_messaging`` app
"""
from askbot.mail import send_mail #todo: remove dependency?
from askbot.mail.messages import GroupMessagingEmailAlert
from django.conf import settings as django_settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.db import models
from django.db.models import signals
from django.template import Context
from django.template.loader import get_template
from django.utils import timezone
try:
    from importlib import import_module
except ImportError:
    from django.utils.importlib import import_module
from django.utils.translation import gettext as _
from askbot.deps.group_messaging.signals import response_created
from askbot.deps.group_messaging.signals import thread_created
import copy
import datetime
import urllib.request, urllib.parse, urllib.error

MAX_HEADLINE_LENGTH = 80
MAX_SUBJECT_LINE_LENGTH = 30

#dummy parse message function
parse_message = lambda v: v

GROUP_NAME_TPL = '_personal_%s'

def get_recipient_names(recipient_groups):
    """returns list of user names if groups are private,
    or group names, otherwise"""
    names = set()
    for group in recipient_groups:
        if group.name.startswith('_personal_'):
            names.add(group.user_set.all()[0].username)
        else:
            names.add(group.name)
    return names


def get_personal_group_by_user_id(user_id):
    return Group.objects.get(name=GROUP_NAME_TPL % user_id)


def get_personal_groups_for_users(users):
    """for a given list of users return their personal groups"""
    group_names = [(GROUP_NAME_TPL % user.id) for user in users]
    return Group.objects.filter(name__in=group_names)


def get_personal_group(user):
    """returns personal group for the user"""
    return get_personal_group_by_user_id(user.id)


def get_unread_inbox_counter(user):
    """returns unread inbox counter for the user"""
    counter, junk = UnreadInboxCounter.objects.get_or_create(user=user)
    return counter


def create_personal_group(user):
    """creates a personal group for the user"""
    group = Group(name=GROUP_NAME_TPL % user.id)
    group.save()
    return group


class LastVisitTime(models.Model):
    """just remembers when a user has
    last visited a given thread
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.ForeignKey('Message', on_delete=models.CASCADE)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'message')
        app_label = 'group_messaging'


class SenderListManager(models.Manager):
    """model manager for the :class:`SenderList`"""

    def get_senders_for_user(self, user=None):
        """returns query set of :class:`User`"""
        user_groups = user.groups.all()
        lists = self.filter(recipient__in=user_groups)
        user_ids = lists.values_list(
                        'senders__id', flat=True
                    ).distinct()
        return User.objects.filter(id__in=user_ids)


class SenderList(models.Model):
    """a model to store denormalized data
    about who sends messages to any given person
    sender list is populated automatically
    as new messages are created
    """
    recipient = models.OneToOneField(Group, on_delete=models.CASCADE)
    senders = models.ManyToManyField(User)
    objects = SenderListManager()

    class Meta:
        app_label = 'group_messaging'


class MessageMemo(models.Model):
    """A bridge between message recipients and messages
    these records are only created when user sees a message.
    The idea is that using groups as recipients, we can send
    messages to massive numbers of users, without cluttering
    the database.

    Instead we'll be creating a "seen" message after user
    reads the message.
    """
    SEEN = 0
    ARCHIVED = 1
    DELETED = 2
    STATUS_CHOICES = (
        (SEEN, 'seen'),
        (ARCHIVED, 'archived'),
        (DELETED, 'deleted')
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.ForeignKey('Message', related_name='memos', on_delete=models.CASCADE)
    status = models.SmallIntegerField(
            choices=STATUS_CHOICES, default=SEEN
        )

    class Meta:
        unique_together = ('user', 'message')
        app_label = 'group_messaging'


class MessageManager(models.Manager):
    """model manager for the :class:`Message`"""

    def get_sent_threads(self, sender=None):
        """returns list of threads for the "sent" mailbox
        this function does not deal with deleted=True
        """
        responses = self.filter(sender=sender)
        responded_to = models.Q(descendants__in=responses, root=None)
        seen_filter = models.Q(
            memos__status=MessageMemo.SEEN,
            memos__user=sender
        )
        seen_responses = self.filter(responded_to & seen_filter)
        unseen_responses = self.filter(responded_to & ~models.Q(memos__user=sender))
        return (
            self.get_threads(sender=sender) \
            | seen_responses.distinct() \
            | unseen_responses.distinct()
        ).distinct()

    def get_threads(self, recipient=None, sender=None, deleted=False):
        """returns query set of first messages in conversations,
        based on recipient, sender and whether to
        load deleted messages or not"""

        if sender and recipient and sender.pk == recipient.pk:
            raise ValueError('sender cannot be the same as recipient')

        filter_kwargs = {
            'root': None,
            'message_type': Message.STORED
        }
        if recipient:
            filter_kwargs['recipients__in'] = recipient.groups.all()
        else:
            #todo: possibly a confusing hack - for this branch -
            #sender but no recipient in the args - we need "sent" origin threads
            recipient = sender

        user_thread_filter = models.Q(**filter_kwargs)

        message_filter = user_thread_filter
        if sender:
            message_filter = message_filter & models.Q(sender=sender)

        if deleted:
            deleted_filter = models.Q(
                memos__status=MessageMemo.ARCHIVED,
                memos__user=recipient
            )
            return self.filter(message_filter & deleted_filter)
        else:
            #rather a tricky query (may need to change the idea to get rid of this)
            #select threads that have a memo for the user, but the memo is not ARCHIVED
            #in addition, select threads that have zero memos for the user
            marked_as_non_deleted_filter = models.Q(
                                            memos__status=MessageMemo.SEEN,
                                            memos__user=recipient
                                        )
            #part1 - marked as non-archived
            part1 = self.filter(message_filter & marked_as_non_deleted_filter)
            #part2 - messages for the user without an attached memo
            part2 = self.filter(message_filter & ~models.Q(memos__user=recipient))
            #strange that (part1 | part2).distinct() sometimes gives wrong result
            threads = list(set(part1) | set(part2))
            thread_ids = [thread.id for thread in threads]
            return Message.objects.filter(id__in=thread_ids).distinct()

    def create(self, **kwargs):
        """creates a message"""
        root = kwargs.get('root', None)
        if root is None:
            parent = kwargs.get('parent', None)
            if parent:
                if parent.root:
                    root = parent.root
                else:
                    root = parent
        kwargs['root'] = root

        headline = kwargs.get('headline', kwargs['text'])
        kwargs['headline'] = headline[:MAX_HEADLINE_LENGTH]
        kwargs['html'] = parse_message(kwargs['text'])

        message = super().create(**kwargs)
        #creator of message saw it by definition
        #crate a "seen" memo for the sender, because we
        #don't want to inform the user about his/her own post
        sender = kwargs['sender']
        MessageMemo.objects.create(
            message=message, user=sender, status=MessageMemo.SEEN
        )
        return message

    def create_thread(self, sender=None, recipients=None, text=None):
        """creates a stored message and adds recipients"""
        message = self.create(
                    message_type=Message.STORED,
                    sender=sender,
                    senders_info=sender.username,
                    text=text,
                )
        now = timezone.now()
        LastVisitTime.objects.create(message=message, user=sender, at=now)
        names = get_recipient_names(recipients)
        message.add_recipient_names_to_senders_info(recipients)
        message.save()
        message.add_recipients(recipients)

        thread_created.send(None, message=message)
        return message

    def create_response(self, sender=None, text=None, parent=None):
        message = self.create(
                    parent=parent,
                    message_type=Message.STORED,
                    sender=sender,
                    text=text,
                )
        #recipients are parent's recipients + sender
        #creator of response gets memo in the "read" status
        recipients = set(parent.recipients.all())

        if sender != parent.sender:
            senders_group = get_personal_group(parent.sender)
            parent.add_recipients([senders_group])
            recipients.add(senders_group)

        message.add_recipients(recipients)
        #add author of the parent as a recipient to parent
        #update headline
        message.root.headline = text[:MAX_HEADLINE_LENGTH]
        #mark last active timestamp for the root message
        message.root.last_active_at = timezone.now()
        #update senders info - stuff that is shown in the thread heading
        message.root.update_senders_info()
        #signal response as created, upon signal increment counters
        response_created.send(None, message=message)
        #move the thread to inboxes of all recipients
        message.root.move_to_inbox()
        return message


class Message(models.Model):
    """the message model allowing users to send
    messages to other users and groups, via
    personal groups.
    """
    STORED = 0
    TEMPORARY = 1
    ONE_TIME = 2
    MESSAGE_TYPE_CHOICES = (
        (STORED, 'email-like message, stored in the inbox'),
        (ONE_TIME, 'will be shown just once'),
        (TEMPORARY, 'will be shown until certain time')
    )

    message_type = models.SmallIntegerField(
        choices=MESSAGE_TYPE_CHOICES,
        default=STORED,
    )

    sender = models.ForeignKey(User, related_name='group_messaging_sent_messages', on_delete=models.CASCADE)

    #comma-separated list of a few names
    senders_info = models.TextField(default='')

    recipients = models.ManyToManyField(Group)

    root = models.ForeignKey(
        'self', null=True,
        blank=True, related_name='descendants', on_delete=models.CASCADE
    )

    parent = models.ForeignKey(
        'self', null=True,
        blank=True, related_name='children', on_delete=models.CASCADE
    )

    headline = models.CharField(max_length=MAX_HEADLINE_LENGTH)

    text = models.TextField(
        null=True, blank=True,
        help_text='source text for the message, e.g. in markdown format'
    )

    html = models.TextField(
        null=True, blank=True,
        help_text='rendered html of the message'
    )

    sent_at = models.DateTimeField(auto_now_add=True)
    last_active_at = models.DateTimeField(auto_now_add=True)
    active_until = models.DateTimeField(blank=True, null=True)

    objects = MessageManager()

    def add_recipient_names_to_senders_info(self, recipient_groups):
        names = get_recipient_names(recipient_groups)
        old_names = set(self.senders_info.split(','))
        names |= old_names
        self.senders_info = ','.join(names)

    def add_recipients(self, recipients):
        """adds recipients to the message
        and updates the sender lists for all recipients
        todo: sender lists may be updated in a lazy way - per user
        """
        self._cached_recipients_users = None #invalidate internal cache
        self.recipients.add(*recipients)
        for recipient in recipients:
            sender_list, created = SenderList.objects.get_or_create(recipient=recipient)
            sender_list.senders.add(self.sender)

    def get_absolute_url(self, user=None):
        """returns absolute url to the thread"""
        assert(user != None)
        settings = django_settings.GROUP_MESSAGING
        func_path = settings['BASE_URL_GETTER_FUNCTION']
        path_bits = func_path.split('.')
        url_getter = getattr(
                        import_module('.'.join(path_bits[:-1])),
                        path_bits[-1]
                    )
        params = copy.copy(settings['BASE_URL_PARAMS'])
        params['thread_id'] = self.id
        url = url_getter(user) + '?' + urllib.parse.urlencode(params)
        #if include_domain_name: #don't need this b/c
        #    site = Site.objects.get_current()
        #    url = 'http://' + site.domain + url
        return url

    def get_email_subject_line(self):
        """forms subject line based on the root message
        and prepends 'Re': if message is non-root
        """
        subject = self.get_root_message().text[:MAX_SUBJECT_LINE_LENGTH]
        if self.root:
            subject = _('Re: ') + subject
        return subject

    def get_root_message(self):
        """returns root message or self
        if current message is root
        """
        if getattr(self, '_cached_root', None):
            return self._cached_root
        self._cached_root = self.root or self
        return self._cached_root

    def get_recipients_users(self):
        """returns query set of users"""
        if getattr(self, '_cached_recipients_users', None):
            return self._cached_recipients_users

        groups = self.recipients.all()
        recipients_users = User.objects.filter(
                                    group_membership__group__in=groups
                                ).exclude(
                                    id=self.sender.id
                                ).distinct()
        self._cached_recipients_users = recipients_users
        return recipients_users


    def get_timeline(self):
        """returns ordered query set of messages in the thread
        with the newest first"""
        root = self.get_root_message()
        root_qs = Message.objects.filter(id=root.id)
        return (root.descendants.all() | root_qs).order_by('-sent_at')


    def is_archived_or_deleted(self, user):
        memos = MessageMemo.objects.filter(
                                    user=user,
                                    message=self,
                                    status__gt=MessageMemo.SEEN
                                )
        return bool(memos.count())


    def is_unread_by_user(self, user, ignore_message=None):
        """True, if there is no "last visit timestamp"
        or if there are new child messages created after
        the last visit timestamp"""
        try:
            timer = LastVisitTime.objects.get(user=user, message=self)
        except LastVisitTime.DoesNotExist:
            #no last visit timestamp, so indeed unread
            return True
        else:
            #see if there are new messages after the last visit
            last_visit_timestamp = timer.at
            descendants_filter = models.Q(sent_at__gt=last_visit_timestamp)
            if ignore_message:
                #ignore message used for the newly posted message
                #in the same request cycle. The idea is that
                #this way we avoid multiple-counting of the unread
                #threads
                descendants_filter &= ~models.Q(id=ignore_message.id)
            follow_up_messages = self.descendants.filter(descendants_filter)
            #unread, if we have new followup messages
            return bool(follow_up_messages.count())


    def send_email_alert(self):
        """signal handler for the message post-save"""
        root_message = self.get_root_message()
        data = {
            'messages': self.get_timeline(),
            'message': self
        }
        for user in self.get_recipients_users():
            #todo change url scheme so that all users have the same
            #urls within their personal areas of the user profile
            #so that we don't need to have loops like this one
            thread_url = root_message.get_absolute_url(user)
            thread_url = thread_url.replace('&', '&amp;')
            #in the template we have a placeholder to be replaced like this:
            data['recipient_user'] = user
            email = GroupMessagingEmailAlert(data)
            body_text = email.render_body()
            body_text = body_text.replace('THREAD_URL_HOLE', thread_url)
            send_mail(
                email.render_subject(),
                body_text,
                django_settings.DEFAULT_FROM_EMAIL,
                [user.email,],
            )


    def update_senders_info(self):
        """update the contributors info,
        meant to be used on a root message only
        """
        senders_names = self.senders_info.split(',')

        if self.sender.username in senders_names:
            senders_names.remove(self.sender.username)
        senders_names.insert(0, self.sender.username)

        self.senders_info = (','.join(senders_names))[:64]
        self.save()

    def move_to_inbox(self, user=None):
        """unarchive message for all recipients"""
        archived_filter = {}
        if user:
            archived_filter['user'] = user
        memos = self.memos.filter(**archived_filter)
        memos.delete()

    def set_status_for_user(self, status, user):
        """set specific status to the message for the user"""
        memo, created = MessageMemo.objects.get_or_create(user=user, message=self)
        memo.status = status
        memo.save()
        return created

    def archive(self, user):
        """mark message as archived"""
        return self.set_status_for_user(MessageMemo.ARCHIVED, user)

    def mark_as_seen(self, user):
        """mark message as seen"""
        is_first_time = self.set_status_for_user(MessageMemo.SEEN, user)
        root = self.get_root_message()
        if is_first_time or root.is_unread_by_user(user):
            inbox_counter = get_unread_inbox_counter(user)
            inbox_counter.decrement()
            inbox_counter.save()

    class Meta:
        app_label = 'group_messaging'


class UnreadInboxCounter(models.Model):
    """Stores number of unread messages
    per recipient group.

    It is relatively expensive to calculate this number,
    therefore we store it in the database.

    In order to know number of uread messages for a given
    user, one has to get all groups user belongs to
    and add up the corresponding counts of unread messages.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    count = models.PositiveIntegerField(default=0)

    def decrement(self):
        """decrements count if > 1
        does not save the object"""
        if self.count > 0:
            self.count -= 1

    def increment(self):
        self.count += 1

    def reset(self):
        self.count = 0

    def recalculate(self):
        """recalculates count of unread messages
        for the user and sets the updated value.
        Does not call .save()"""
        self.reset()
        for thread in Message.objects.get_threads(recipient=self.user):
            if thread.is_unread_by_user(self.user):
                self.increment()

    class Meta:
        app_label = 'group_messaging'


def increment_unread_inbox_counters(sender, message, **kwargs):
    root_message = message.get_root_message()
    for user in message.get_recipients_users():
        if message == root_message \
            or not root_message.is_unread_by_user(user, ignore_message=message) \
            or root_message.is_archived_or_deleted(user):

            # 1) if message is root - we have new thread,
            # so it's safe to increment the inbox counter
            # 2) if the message is a reply - the counter might
            # have already been incremented. Therefore - we check
            # whether the message was unread by the user,
            # excluding the current message, which is obviously unread
            # 3) if root message is deleted or archived then increment

            counter = get_unread_inbox_counter(user)
            counter.increment()
            counter.save()


def send_email(sender, message, **kwargs):
    message.send_email_alert()


thread_created.connect(
    receiver=send_email,
    dispatch_uid="thread_send_email"
)

thread_created.connect(
    receiver=increment_unread_inbox_counters,
    dispatch_uid="thread_increment_unread_inbox_counters"
)

response_created.connect(
    receiver=send_email,
    dispatch_uid="message_reply_send_email"
)

response_created.connect(
    receiver=increment_unread_inbox_counters,
    dispatch_uid="response_increment_unread_inbox_counters"
)
