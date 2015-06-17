from askbot.tests.utils import with_settings
from bs4 import BeautifulSoup
from django.contrib.auth.models import User, Group
from django.test import TestCase
from group_messaging.models import LastVisitTime
from group_messaging.models import Message
from group_messaging.models import MessageMemo
from group_messaging.models import SenderList
from group_messaging.models import create_personal_group
from group_messaging.models import get_personal_group
from group_messaging.models import get_unread_inbox_counter
from group_messaging.views import ThreadsList
from mock import Mock
import datetime
import time
import urlparse

MESSAGE_TEXT = 'test message text'

def create_user(name):
    """creates a user and a personal group,
    returns the created user"""
    user = User.objects.create_user(name, name + '@example.com')
    #note that askbot will take care of three lines below automatically
    try:
        group = get_personal_group(user)
    except Group.DoesNotExist:
        group = create_personal_group(user)
    group_name = '_personal_%d' % user.id
    group, created = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)
    return user

def get_html_message(mail_message):
    """mail message is an item from the django.core.mail.outbox"""
    return mail_message.alternatives[0][0]

class GroupMessagingTests(TestCase):
    """base class for the test cases in this app"""

    def setUp(self):
        self.sender = create_user('sender')
        self.recipient = create_user('recipient')

    def create_thread(self, sender, recipient_groups):
        return Message.objects.create_thread(
            sender=sender, recipients=recipient_groups,
            text=MESSAGE_TEXT
        )

    def create_thread_for_user(self, sender, recipient):
        group = get_personal_group(recipient)
        return self.create_thread(sender, [group])

    def visit_thread(self, thread, user):
        last_visit_time, created = LastVisitTime.objects.get_or_create(
                                                user=user,
                                                message=thread
                                            )
        last_visit_time.at = datetime.datetime.now()
        last_visit_time.save()
        time.sleep(1.5)
        return last_visit_time

    def setup_three_message_thread(self, original_poster=None, responder=None):
        """talk in this order: sender, recipient, sender"""
        original_poster = original_poster or self.sender
        responder = responder or self.recipient

        root_message = self.create_thread_for_user(original_poster, responder)
        response = Message.objects.create_response(
                                        sender=responder,
                                        text='some response',
                                        parent=root_message
                                    )
        response2 = Message.objects.create_response(
                                        sender=original_poster,
                                        text='some response2',
                                        parent=response
                                    )
        return root_message, response, response2


class ViewsTests(GroupMessagingTests):

    def get_view_context(self, view_class, data=None, user=None, method='GET'):
        spec = ['REQUEST', 'user']
        assert(method in ('GET', 'POST'))
        spec.append(method)
        request = Mock(spec=spec)
        request.REQUEST = data
        setattr(request, method, data)
        request.user = user
        return view_class().get_context(request)

    def test_new_response_marks_thread_heading_as_new(self):
        root = self.create_thread_for_user(self.sender, self.recipient)
        response = Message.objects.create_response(
                                        sender=self.recipient,
                                        text='some response',
                                        parent=root
                                    )
        #response must show as "new" to the self.sender
        context = self.get_view_context(
                                ThreadsList,
                                data={'sender_id': '-1'},
                                user=self.sender
                            )
        self.assertEqual(context['threads_data'][root.id]['status'], 'new')
        #"visit" the thread: todo - make a method
        self.visit_thread(root, self.sender)

        #response must show as "seen"
        context = self.get_view_context(
                                ThreadsList,
                                data={'sender_id': '-1'},
                                user=self.sender
                            )
        self.assertEqual(context['threads_data'][root.id]['status'], 'seen')
        #self.recipient makes another response
        response = Message.objects.create_response(
                                        sender=self.recipient,
                                        text='some response',
                                        parent=response
                                    )
        #thread must be "new" again
        context = self.get_view_context(
                                ThreadsList,
                                data={'sender_id': '-1'},
                                user=self.sender
                            )
        self.assertEqual(context['threads_data'][root.id]['status'], 'new')

    def test_answer_to_deleted_thread_undeletes_thread(self):
        #setup: message, reply, responder deletes thread
        root_message = self.create_thread_for_user(self.sender, self.recipient)
        response = Message.objects.create_response(
                                        sender=self.recipient,
                                        text='some response',
                                        parent=root_message
                                    )
        memo1, created = MessageMemo.objects.get_or_create(
                                        message=root_message,
                                        user=self.recipient,
                                        status=MessageMemo.ARCHIVED
                                    )
        #OP sends reply to reply
        response2 = Message.objects.create_response(
                                        sender=self.sender,
                                        text='some response2',
                                        parent=response
                                    )

        context = self.get_view_context(
                                ThreadsList,
                                data={'sender_id': '-1'},
                                user=self.recipient
                            )

        self.assertEqual(len(context['threads']), 1)
        thread_id = context['threads'][0].id
        thread_data = context['threads_data'][thread_id]
        self.assertEqual(thread_data['status'], 'new')

    @with_settings(APP_URL='http://localhost/')
    def test_emailed_message_url_works_for_post_recipient(self):
        root = self.create_thread_for_user(self.sender, self.recipient)
        from django.core.mail import outbox
        html_message = get_html_message(outbox[0])
        link = BeautifulSoup(html_message).find('a', attrs={'class': 'thread-link'})
        url = link['href'].replace('&amp;', '&')
        parsed_url = urlparse.urlparse(url)
        url_data = urlparse.parse_qsl(parsed_url.query)
        self.client.login(user_id=self.recipient.id, method='force')
        response = self.client.get(parsed_url.path, url_data)
        dom = BeautifulSoup(response.content)
        threads = dom.find_all('ul', attrs={'class': 'js-thread'})
        self.assertEquals(len(threads), 1)
        thread_lists = dom.find_all('table', attrs={'class': 'js-thread-list'})
        self.assertEquals(len(thread_lists), 0)

    def test_sent_thread_is_visited_by_sender(self):
        root = self.create_thread_for_user(self.sender, self.recipient)
        context = self.get_view_context(
                                ThreadsList,
                                data={'sender_id': str(self.sender.id)},
                                user=self.sender
                            )
        thread_data = context['threads_data'][root.id]
        self.assertEqual(thread_data['status'], 'seen')

class ModelsTests(GroupMessagingTests):
    """test cases for the `private_messaging` models"""

    def test_create_thread_for_user(self):
        """the basic create thread with one recipient
        tests that the recipient is there"""
        message = self.create_thread_for_user(self.sender, self.recipient)
        #message type is stored
        self.assertEqual(message.message_type, Message.STORED)
        #recipient is in the list of recipients
        recipients = set(message.recipients.all())
        recipient_group = get_personal_group(self.recipient)
        #sender_group = get_personal_group(self.sender) #maybe add this too
        expected_recipients = set([recipient_group])
        self.assertEqual(recipients, expected_recipients)
        #self.assertRaises(
        #    MessageMemo.DoesNotExist,
        #    MessageMemo.objects.get,
        #    message=message
        #)
        #make sure that the original senders memo to the root
        #message is marke ad seen
        memos = MessageMemo.objects.filter(
                                message=message,
                                user=self.sender
                            )
        self.assertEquals(memos.count(), 1)
        self.assertEqual(memos[0].status, MessageMemo.SEEN)

    def test_get_senders_for_user(self):
        """this time send thread to a real group test that
        member of the group has updated the sender list"""
        group = Group.objects.create(name='somegroup')
        self.recipient.groups.add(group)
        message = self.create_thread(self.sender, [group])
        senders = SenderList.objects.get_senders_for_user(self.recipient)
        self.assertEqual(set(senders), set([self.sender]))

    def test_unread_counter_new_thread1(self):
        counter = get_unread_inbox_counter(self.recipient)
        self.assertEqual(counter.count, 0)

        thread = self.create_thread_for_user(self.sender, self.recipient)
        counter = get_unread_inbox_counter(self.recipient)
        self.assertEqual(counter.count, 1)

        counter = get_unread_inbox_counter(self.sender)
        self.assertEqual(counter.count, 0)

    def test_unread_counter_new_thread2(self):
        thread = self.create_thread_for_user(self.sender, self.recipient)
        thread.mark_as_seen(self.recipient)
        counter = get_unread_inbox_counter(self.recipient)
        self.assertEqual(counter.count, 0)

        counter = get_unread_inbox_counter(self.sender)
        self.assertEqual(counter.count, 0)

    def test_recalculate_unread_counter(self):
        thread = self.create_thread_for_user(self.sender, self.recipient)
        counter = get_unread_inbox_counter(self.recipient)
        counter.reset()
        self.assertEqual(counter.count, 0)
        counter.recalculate()
        self.assertEqual(counter.count, 1)

    def test_create_thread_response(self):
        """create a thread with one response,
        then load thread for the user
        test that only the root message is retrieved"""
        root_message = self.create_thread_for_user(self.sender, self.recipient)
        response = Message.objects.create_response(
                                        sender=self.recipient,
                                        text='some response',
                                        parent=root_message
                                    )
        self.assertEqual(response.message_type, Message.STORED)

        #assert that there is only one "seen" memo for the response
        memos = MessageMemo.objects.filter(message=response)
        self.assertEqual(memos.count(), 1)
        self.assertEqual(memos[0].user, self.recipient)
        self.assertEqual(memos[0].status, MessageMemo.SEEN)

        #assert that recipients are the two people who are part of
        #this conversation
        recipients = set(response.recipients.all())
        sender_group = get_personal_group(self.sender)
        recipient_group = get_personal_group(self.recipient)
        expected_recipients = set([sender_group, recipient_group])
        self.assertEqual(recipients, expected_recipients)

    def test_get_threads(self):
        root_message = self.create_thread_for_user(self.sender, self.recipient)
        threads = set(Message.objects.get_threads(recipient=self.sender))
        self.assertEqual(threads, set([]))
        threads = set(Message.objects.get_threads(recipient=self.recipient))
        self.assertEqual(threads, set([root_message]))

        response = Message.objects.create_response(
                                        sender=self.recipient,
                                        text='some response',
                                        parent=root_message
                                    )
        threads = set(Message.objects.get_threads(recipient=self.sender))
        self.assertEqual(threads, set([root_message]))
        threads = set(Message.objects.get_threads(recipient=self.recipient))
        self.assertEqual(threads, set([root_message]))

    def test_deleting_thread_is_user_specific(self):
        """when one user deletes thread, that same thread
        should not end up deleted by another user
        """
        root, response, response2 = self.setup_three_message_thread()

        threads = Message.objects.get_threads(recipient=self.sender)
        self.assertEquals(threads.count(), 1)
        threads = Message.objects.get_threads(recipient=self.recipient)
        self.assertEquals(threads.count(), 1)

        memo1, created = MessageMemo.objects.get_or_create(
                                        message=root,
                                        user=self.recipient,
                                        status=MessageMemo.ARCHIVED
                                    )

        threads = Message.objects.get_threads(recipient=self.sender)
        self.assertEquals(threads.count(), 1)
        threads = Message.objects.get_threads(recipient=self.recipient)
        self.assertEquals(threads.count(), 0)
        threads = Message.objects.get_threads(
                                recipient=self.recipient, deleted=True
                            )
        self.assertEquals(threads.count(), 1)

    def test_user_specific_inboxes(self):
        self.create_thread_for_user(self.sender, self.recipient)

        threads = Message.objects.get_threads(
                        recipient=self.recipient, sender=self.sender
                    )
        self.assertEqual(threads.count(), 1)
        threads = Message.objects.get_threads(
                        recipient=self.sender, sender=self.recipient
                    )
        self.assertEqual(threads.count(), 0)

    def test_response_updates_thread_headline(self):
        root = self.create_thread_for_user(self.sender, self.recipient)
        response = Message.objects.create_response(
                                        sender=self.recipient,
                                        text='some response',
                                        parent=root
                                    )
        self.assertEqual(root.headline, 'some response')

    def test_email_alert_sent(self):
        root = self.create_thread_for_user(self.sender, self.recipient)
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 1)
        self.assertEqual(len(outbox[0].recipients()), 1)
        self.assertEqual(outbox[0].recipients()[0], self.recipient.email)
        html_message = get_html_message(outbox[0])
        self.assertTrue(root.text in html_message)
        soup = BeautifulSoup(html_message)
        links = soup.find_all('a', attrs={'class': 'thread-link'})
        self.assertEqual(len(links), 1)
        parse_result = urlparse.urlparse(links[0]['href'])
        query = urlparse.parse_qs(parse_result.query.replace('&amp;', '&'))
        self.assertEqual(query['thread_id'][0], str(root.id))

    def test_get_sent_threads(self):
        root1, re11, re12 = self.setup_three_message_thread()
        root2, re21, re22 = self.setup_three_message_thread(
                        original_poster=self.recipient, responder=self.sender
                    )
        root3, re31, re32 = self.setup_three_message_thread()

        #mark root2 as seen
        root2.mark_as_seen(self.sender)
        #mark root3 as deleted
        root3.archive(self.sender)

        threads = Message.objects.get_sent_threads(sender=self.sender)
        self.assertEqual(threads.count(), 2)
        self.assertEqual(set(threads), set([root1, root2]))#root3 is deleted

    def test_recipient_lists_are_in_senders_info(self):
        thread = self.create_thread_for_user(self.sender, self.recipient)
        self.assertTrue(self.recipient.username in thread.senders_info)

    def test_self_response_not_in_senders_inbox(self):
        root = self.create_thread_for_user(self.sender, self.recipient)
        response = Message.objects.create_response(
                                        sender=self.sender,
                                        text='some response',
                                        parent=root
                                    )
        threads = Message.objects.get_threads(recipient=self.sender)
        self.assertEqual(threads.count(), 0)

    def test_sent_message_is_seen_by_the_sender(self):
        root = self.create_thread_for_user(self.sender, self.recipient)
        time.sleep(1.5)
        last_visits = LastVisitTime.objects.filter(message=root, user=self.sender)
        self.assertEqual(last_visits.count(), 1)
