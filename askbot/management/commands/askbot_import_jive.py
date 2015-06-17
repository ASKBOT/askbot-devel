from askbot import models
from askbot.conf import settings as askbot_settings
from askbot.utils.console import ProgressBar
from askbot.utils.slug import slugify
from askbot.utils.jive import JiveConverter
from askbot.utils.jive import internal_link_re
from askbot.utils.file_utils import make_file_name
from bs4 import BeautifulSoup
from django.conf import settings as django_settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
#from askbot.utils.transaction import dummy_transaction as transaction
from django.forms import EmailField, ValidationError
from django.utils import translation
from datetime import datetime
from optparse import make_option
import re
import os
import shutil

#todo: make a pass through all attachments
#and make sure that mimetypes dictionary is up to date
#raise an error if it's not
FILE_TYPES = {
    "application/java-archive": 'jar',
    "application/msword": 'doc',
    "application/octet-stream": 'txt',
    "application/text": 'txt',
    "application/vnd.visio": 'vsd',
    "application/x-bzip": 'bz',
    "application/x-gzip": 'gz',
    "application/x-java-archive": 'jar',
    "application/x-shellscript": 'sh',
    "application/x-zip-compressed": 'zip',
    "application/xml": 'xml',
    "application/zip": 'zip',
    "image/bmp": 'bmp',
    "image/gif": 'gif',
    "image/jpeg": 'jpeg',
    "image/pjpeg": 'pjpeg',
    "image/png": 'png',
    "image/x-png": 'png',
    "text/html": 'html',
    "text/java": 'java',
    "text/plain": 'txt',
    "text/x-java": 'java',
    "text/x-java-source": 'java',
    "text/x-log": 'log',
    "text/xml": 'xml'
}

jive = JiveConverter()

def parse_date(date_str):
    return datetime.strptime(date_str[:-8], '%Y/%m/%d %H:%M:%S')

def fix_internal_links_in_post(post):
    """will replace old internal urls with the new ones."""

    def link_is_naked(match):
        """naked link either starts at the beginning of string
        or is not inside the jive link construct: [...]"""
        pos = match.start()
        # the second test is rather naive as it assumes that a
        # | will be preceded by something like [some link
        # which we don't test here
        return pos < 2 or post.text[pos-2] not in ('[', '|')

    def internal_link_sub(match):
        """pull post by the matched pars in the old link
        and returns link to the new post"""
        link_type = match.group(1)
        item_id = int(match.group(2))
        lookup_key = (link_type == 'message' and 'old_answer_id' or 'old_question_id')
        try:
            post = models.Post.objects.get(**{lookup_key: item_id})
            # if original link is naked, we put in into brackets
            # so that the formatter will render the result correctly
            # otherwise "naked" /url will stay plain text
            new_url = post.get_absolute_url()
            return (link_is_naked(match) and '[%s]' % new_url or new_url)
        except models.Post.DoesNotExist:
            return ''

    post.text = internal_link_re.sub(internal_link_sub, post.text)
    post.save()

def turn_first_company_user_to_admin(domain):
    company_users = models.User.objects.filter(
                        email__endswith='@' + domain
                    ).order_by('id')
    if company_users.count() == 0:
        return None

    user = company_users[0]
    user.is_staff = True
    user.is_superuser = True
    user.save()
    return user

def thread_get_answer_from_company(thread, domain):
    answers = thread.posts.filter(
                        post_type='answer'
                    ).select_related(
                        'author__email'
                    )
    for answer in answers:
        if answer.author.email.endswith('@' + domain):
            return answer
    return None

def thread_find_first_comment_from_company(thread, domain):
    comments = thread.posts.filter(
                        post_type='comment'
                    ).select_related(
                        'author__email'
                    ).order_by('added_at')
    for comment in comments:
        if comment.author.email.endswith('@' + domain):
            return comment
    return None

COMPANY_DOMAIN_HELP = """If used - first response from user with that domain
then first response in each question from user with matching email address
will be posted as answer and accepted as correct. Also, first user
with a matching email address will be a site administrator."""

JIVE_REDIRECTS_HELP = """This file will contain redirects from the old
posts to new"""

class Command(BaseCommand):
    args = '<jive-dump.xml>'
    option_list = BaseCommand.option_list + (
        make_option('--company-domain',
            action='store',
            type='str',
            dest='company_domain',
            default=None,
            help=COMPANY_DOMAIN_HELP
        ),
        make_option('--redirects_file',
            action='store',
            type='str',
            dest='redirects_file',
            default='',
            help=JIVE_REDIRECTS_HELP
        )
    )

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        #relax certain settings
        askbot_settings.update('LIMIT_ONE_ANSWER_PER_USER', False)
        askbot_settings.update('MAX_COMMENT_LENGTH', 1000000)
        askbot_settings.update('MIN_REP_TO_INSERT_LINK', 1)
        askbot_settings.update('MIN_REP_TO_SUGGEST_LINK', 1)
        askbot_settings.update('COMMENTS_EDITOR_TYPE', 'rich-text')
        askbot_settings.update('MARKUP_CODE_FRIENDLY', True)
        self.bad_email_count = 0
        self.attachments_path = ''
        self.soup = None
        self.jive_url = None

    def handle(self, *args, **kwargs):
        translation.activate(django_settings.LANGUAGE_CODE)
        assert len(args) == 1, 'Dump file name is required'
        dump_file_name = args[0]
        xml = open(dump_file_name, 'r').read()
        soup = BeautifulSoup(xml, ['lxml', 'xml'])
        self.soup = soup
        url_prop = self.soup.find('Property', attrs={'name': 'jiveURL'})
        self.jive_url= url_prop['value']

        dump_dir = os.path.dirname(os.path.abspath(dump_file_name))
        self.attachments_path = os.path.join(dump_dir, 'attachments')

        self.import_users()
        self.import_forums()
        if kwargs['company_domain']:
            self.promote_company_replies(kwargs['company_domain'])
        self.fix_internal_links()
        self.add_legacy_links()
        if kwargs['redirects_file']:
            self.make_redirects(kwargs['redirects_file'])
        self.convert_jive_markup_to_html()
        models.Message.objects.all().delete()

    @transaction.commit_manually
    def add_legacy_links(self):
        questions = models.Post.objects.filter(post_type='question')
        count = questions.count()
        message = 'Adding links to old forum'
        template = """\n\n{quote}This thread was imported from the previous forum.
For your reference, the original is [available here|%s]{quote}"""
        for question in ProgressBar(questions.iterator(), count, message):
            thread_id = question.old_question_id
            jive_url = self.jive_url
            old_url = '%s/thread.jspa?threadID=%s' % (jive_url, thread_id)
            question.text += template % old_url
            question.save()
            transaction.commit()
        transaction.commit()

    @transaction.commit_manually
    def make_redirects(self):
        """todo: implement this when needed"""
        pass


    @transaction.commit_manually
    def convert_jive_markup_to_html(self):
        posts = models.Post.objects.all()
        count = posts.count()
        message = 'Converting jive markup to html'
        for post in ProgressBar(posts.iterator(), count, message):
            post.html = jive.convert(post.text)
            post.summary = post.get_snippet()
            post.save()
            transaction.commit()
        transaction.commit()

    @transaction.commit_manually
    def fix_internal_links(self):
        jive_url = self.jive_url
        print 'Base url of old forum: %s' % jive_url
        posts = models.Post.objects.filter(text__contains=jive_url)
        count = posts.count()
        message = 'Fixing internal links'
        for post in ProgressBar(posts.iterator(), count, message):
            post.text = post.text.replace(jive_url, '')
            fix_internal_links_in_post(post)
            transaction.commit()
        transaction.commit()

    @transaction.commit_manually
    def promote_company_replies(self, domain):
        admin = turn_first_company_user_to_admin(domain)
        if admin is None:
            print "Note: did not find any users with email matching %s" % domain
            return
        message = 'Promoting company replies to accepted answers:'
        threads = models.Thread.objects.all()
        count = threads.count()
        for thread in ProgressBar(threads.iterator(), count, message):
            answer = thread_get_answer_from_company(thread, domain)

            if answer == None:
                comment = thread_find_first_comment_from_company(thread, domain)
                if comment:
                    admin.repost_comment_as_answer(comment)
                    answer = comment

            if answer:
                admin.accept_best_answer(answer=answer, force=True)

            transaction.commit()
        transaction.commit()

    @transaction.commit_manually
    def import_users(self):
        """import users from jive to askbot"""

        user_soup = self.soup.find_all('User')

        message = 'Importing users:'
        for user in ProgressBar(iter(user_soup), len(user_soup), message):
            username = user.find('Username').text
            real_name = user.find('Name').text
            try:
                email = EmailField().clean(user.find('Email').text)
            except ValidationError:
                email = 'unknown%d@example.com' % self.bad_email_count
                self.bad_email_count += 1

            joined_timestamp = parse_date(user.find('CreationDate').text)
            user = models.User(
                username=username,
                email=email,
                real_name=real_name,
                date_joined=joined_timestamp
            )
            user.set_unusable_password()
            user.save()
            transaction.commit()

    def import_forums(self):
        """import forums by associating each with a special tag,
        and then importing all threads for the tag"""
        admin = models.User.objects.get(id=1)
        forum_soup = self.soup.find_all('Forum')
        print 'Have %d forums' % len(forum_soup)
        for forum in forum_soup:
            threads_soup = forum.find_all('Thread')
            self.import_threads(threads_soup, forum.find('Name').text)

    @transaction.commit_manually
    def import_threads(self, threads, tag_name):
        message = 'Importing threads for %s' % tag_name
        for thread in ProgressBar(iter(threads), len(threads), message):
            self.import_thread(thread, tag_name)
            transaction.commit()

    def add_attachments_to_post(self, post, attachments):
        if len(attachments) == 0:
            return

        post.text += '\nh4. Attachments\n'
        for att in attachments:
            att_id, name, mimetype = att
            if mimetype not in FILE_TYPES:
                continue
            ext = '.' + FILE_TYPES[mimetype]
            file_name = make_file_name(ext)
            # copy attachment file to a new place
            source_file = os.path.join(self.attachments_path, att_id + '.bin')
            dest_file = os.path.join(django_settings.MEDIA_ROOT, file_name)
            shutil.copyfile(source_file, dest_file)
            # add link to file to the post text
            post.text += '# [%s|%s%s]\n' % (name, django_settings.MEDIA_URL, file_name)

    def import_thread(self, thread, tag_name):
        """import individual thread"""
        question_soup = thread.find('Message')
        post_id, title, body, attachments, timestamp, user = \
                                        self.parse_post(question_soup)

        if models.Post.objects.filter(old_question_id=thread['id']).count() == 1:
            #this allows restarting the process of importing forums
            #any time
            return

        #post question
        question = user.post_question(
            title=title,
            body_text=body,
            timestamp=timestamp,
            tags=tag_name,
            language=django_settings.LANGUAGE_CODE
        )
        self.add_attachments_to_post(question, attachments)
        question.html = jive.convert(question.text)
        question.old_question_id = int(thread['id'])
        question.old_answer_id = post_id
        question.summary = question.get_snippet()
        question.save()
        #post answers
        message_list = question_soup.find_all('MessageList', recursive=False)
        if len(message_list) == 0:
            return

        for answer_soup in message_list[0].find_all('Message', recursive=False):
            post_id, title, body, attachments, timestamp, user = \
                                            self.parse_post(answer_soup)
            answer = user.post_answer(
                question=question,
                body_text=body,
                timestamp=timestamp
            )
            self.add_attachments_to_post(answer, attachments)
            answer.html = jive.convert(answer.text)
            answer.summary = answer.get_snippet()
            answer.old_answer_id = post_id
            answer.save()
            comments = answer_soup.find_all('Message')
            for comment in comments:
                post_id, title, body, attachments, timestamp, user = \
                                                    self.parse_post(comment)
                comment = user.post_comment(
                    parent_post=answer,
                    body_text=body,
                    timestamp=timestamp
                )
                comment.old_answer_id = post_id
                self.add_attachments_to_post(comment, attachments)
                comment.html = jive.convert(comment.text)
                comment.summary = comment.get_snippet()
                comment.save()


    def parse_post(self, post):
        title = post.find('Subject').text
        added_at = parse_date(post.find('CreationDate').text)
        username = post.find('Username').text
        body = post.find('Body').text
        attachments_soup = post.find_all('Attachment')
        attachments = list()
        for att in attachments_soup:
            att_id = att['id']
            name = att.find('Name').text
            content_type = att['contentType']
            attachments.append((att_id, name, content_type))

        try:
            user = models.User.objects.get(username=username)
        except models.User.DoesNotExist:
            email = 'unknown%d@example.com' % self.bad_email_count
            self.bad_email_count += 1
            user = models.User(username=username, email=email)
            user.save()
        return int(post['id']), title, body, attachments, added_at, user
