"""models for the ``group_messaging`` app
"""
import copy
import datetime
import urllib
from askbot.mail import send_mail #todo: remove dependency?
from django.template.loader import get_template
from django.db import models
from django.db.models import signals
from django.conf import settings as django_settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.utils.importlib import import_module
from django.utils.translation import ugettext as _

MAX_HEADLINE_LENGTH = 80
MAX_SENDERS_INFO_LENGTH = 64
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


def create_personal_group(user):
    """creates a personal group for the user"""
    group = Group(name=GROUP_NAME_TPL % user.id)
    group.save()
    return group


class LastVisitTime(models.Model):
    """just remembers when a user has 
    last visited a given thread
    """
    user = models.ForeignKey(User)
    message = models.ForeignKey('Message')
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'message')


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
    recipient = models.ForeignKey(Group, unique=True)
    senders = models.ManyToManyField(User)
    objects = SenderListManager()


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
    STATUS_CHOICES = (
        (SEEN, 'seen'),
        (ARCHIVED, 'archived')
    )
    user = models.ForeignKey(User)
    message = models.ForeignKey('Message', related_name='memos')
    status = models.SmallIntegerField(
            choices=STATUS_CHOICES, default=SEEN
        )

    class Meta:
        unique_together = ('user', 'message')


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

        if sender and sender == recipient:
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

        filter = user_thread_filter
        if sender:
            filter = filter & models.Q(sender=sender)

        if deleted:
            deleted_filter = models.Q(
                memos__status=MessageMemo.ARCHIVED,
                memos__user=recipient
            )
            return self.filter(filter & deleted_filter)
        else:
            #rather a tricky query (may need to change the idea to get rid of this)
            #select threads that have a memo for the user, but the memo is not ARCHIVED
            #in addition, select threads that have zero memos for the user
            marked_as_non_deleted_filter = models.Q(
                                            memos__status=MessageMemo.SEEN,
                                            memos__user=recipient
                                        )
            #part1 - marked as non-archived
            part1 = self.filter(filter & marked_as_non_deleted_filter)
            #part2 - messages for the user without an attached memo
            part2 = self.filter(filter & ~models.Q(memos__user=recipient))
            return (part1 | part2).distinct()

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

        message = super(MessageManager, self).create(**kwargs)
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
        message.send_email_alert()
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
        #unarchive the thread for all recipients
        message.root.unarchive()
        message.send_email_alert()
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
    
    sender = models.ForeignKey(User, related_name='sent_messages')

    senders_info = models.CharField(
        max_length=MAX_SENDERS_INFO_LENGTH,
        default=''
    )#comma-separated list of a few names
    
    recipients = models.ManyToManyField(Group)

    root = models.ForeignKey(
        'self', null=True,
        blank=True, related_name='descendants'
    )
    
    parent = models.ForeignKey(
        'self', null=True,
        blank=True, related_name='children'
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
        url = url_getter(user) + '?' + urllib.urlencode(params)
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
        return self.root or self

    def get_recipients_users(self):
        """returns query set of users"""
        groups = self.recipients.all()
        return User.objects.filter(
                        groups__in=groups
                    ).exclude(
                        id=self.sender.id
                    ).distinct()

    def get_timeline(self):
        """returns ordered query set of messages in the thread
        with the newest first"""
        root = self.get_root_message()
        root_qs = Message.objects.filter(id=root.id)
        return (root.descendants.all() | root_qs).order_by('-sent_at')


    def send_email_alert(self):
        """signal handler for the message post-save"""
        root_message = self.get_root_message()
        data = {'messages': self.get_timeline()}
        template = get_template('group_messaging/email_alert.html')
        body_text = template.render(data)
        subject = self.get_email_subject_line()
        for user in self.get_recipients_users():
            #todo change url scheme so that all users have the same
            #urls within their personal areas of the user profile
            #so that we don't need to have loops like this one
            thread_url = root_message.get_absolute_url(user)
            thread_url = thread_url.replace('&', '&amp;')
            #in the template we have a placeholder to be replaced like this:
            body_text = body_text.replace('THREAD_URL_HOLE', thread_url)
            send_mail(
                subject,
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

    def unarchive(self, user=None):
        """unarchive message for all recipients"""
        archived_filter = {'status': MessageMemo.ARCHIVED}
        if user:
            archived_filter['user'] = user
        memos = self.memos.filter(**archived_filter)
        memos.update(status=MessageMemo.SEEN)

    def set_status_for_user(self, status, user):
        """set specific status to the message for the user"""
        memo, created = MessageMemo.objects.get_or_create(user=user, message=self)
        memo.status = status
        memo.save()

    def archive(self, user):
        """mark message as archived"""
        self.set_status_for_user(MessageMemo.ARCHIVED, user)

    def mark_as_seen(self, user):
        """mark message as seen"""
        self.set_status_for_user(MessageMemo.SEEN, user)
