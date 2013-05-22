"""importer from zendesk data dump
the dump must be a tar/gzipped file, containing one directory
with all the .xml files.

Run this command as::

    python manage.py import_zendesk path/to/dump.tgz
"""
import os
import re
import sys
import tarfile
import tempfile
from datetime import datetime, date
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from lxml import etree
from askbot import models as askbot_models
from askbot.utils import console
from askbot.utils.html import unescape

from askbot.importers.zendesk import models as zendesk_models

#a hack, did not know how to parse timezone offset
ZERO_TIME = datetime.strptime('00:00', '%H:%M')

def get_unique_username(name_seed):
    """returns unique user name, by modifying the
    name if the same name exists in the database
    until the modified name is unique
    """
    original_name = name_seed
    attempt_no = 1
    while True:
        try:
            askbot_models.User.objects.get(username = name_seed)
            name_seed = original_name + str(attempt_no)
            attempt_no += 1
        except askbot_models.User.DoesNotExist:
            return name_seed

def clean_username(name_seed):
    """makes sure that the name is unique
    and is no longer than 30 characters"""
    username = get_unique_username(name_seed)
    if len(username) > 30:
        username = get_unique_username(username[:28])
        if len(username) > 30:
            #will allow about a million extra possible unique names
            username = get_unique_username(username[:24])
    return username

def create_askbot_user(zd_user):
    """create askbot user from zendesk user record
    return askbot user or None, if there is error
    """
    #special treatment for the user name
    raw_username = unescape(zd_user.name)
    username = clean_username(raw_username)
    if len(username) > 30:#nearly impossible skip such user
        print "Warning: could not import user %s" % raw_username
        return None

    if zd_user.email is None:
        email = ''
    else:
        email = zd_user.email

    ab_user = askbot_models.User(
        email = email,
        email_isvalid = zd_user.is_verified,
        date_joined = zd_user.created_at,
        last_seen = zd_user.created_at,#add initial date for now
        username = username,
        is_active = zd_user.is_active
    )
    ab_user.save()
    return ab_user

def post_question(zendesk_post):
    """posts question to askbot, using zendesk post item"""
    try:
        return zendesk_post.get_author().post_question(
            title = zendesk_post.get_fake_title(),
            body_text = zendesk_post.get_body_text(),
            tags = zendesk_post.get_tag_name(),
            timestamp = zendesk_post.created_at
        )
    except Exception, e:
        msg = unicode(e)
        print "Warning: post %d dropped: %s" % (zendesk_post.post_id, msg)

def post_answer(zendesk_post, question = None):
    try:
        zendesk_post.get_author().post_answer(
            question = question,
            body_text = zendesk_post.get_body_text(),
            timestamp = zendesk_post.created_at
        )
    except Exception, e:
        msg = unicode(e)
        print "Warning: post %d dropped: %s" % (zendesk_post.post_id, msg)

def get_val(elem, field_name):
    field = elem.find(field_name)
    if field is None:
        return None
    try:
        field_type = field.attrib['type']
    except KeyError:
        field_type = ''
    raw_val = field.text
    if raw_val is None:
        return None

    if field_type == 'boolean':
        if raw_val == 'true':
            return True
        elif raw_val == 'false':
            return False
        else:
            raise ValueError('"true" or "false" expected, found "%s"' % raw_val)
    elif field_type.endswith('integer'):
        return int(raw_val)
    elif field_type == 'datetime':
        if raw_val is None:
            return None
        raw_datetime = raw_val[:19]
        tzoffset_sign = raw_val[19]
        raw_tzoffset = raw_val[20:]
        if raw_val:
            dt = datetime.strptime(raw_datetime, '%Y-%m-%dT%H:%M:%S')
            tzoffset_amt = datetime.strptime(raw_tzoffset, '%H:%M')
            tzoffset = tzoffset_amt - ZERO_TIME
            if tzoffset_sign == '-':
                return dt - tzoffset
            else:
                return dt + tzoffset
        else:
            return None
    else:
        return raw_val

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        if len(args) != 1:
            raise CommandError('please provide path to tarred and gzipped cnprog dump')

        self.tar = tarfile.open(args[0], 'r:gz')

        sys.stdout.write('Reading users.xml: ')
        self.read_users()
        sys.stdout.write('Reading posts.xml: ')
        self.read_posts()
        sys.stdout.write('Reading forums.xml: ')
        self.read_forums()

        sys.stdout.write("Importing user accounts: ")
        self.import_users()
        sys.stdout.write("Loading threads: ")
        self.import_content()

    def get_file(self, file_name):
        first_item = self.tar.getnames()[0]
        file_path = file_name
        if not first_item.endswith('.xml'):
            file_path = os.path.join(first_item, file_path)
            
        file_info = self.tar.getmember(file_path)
        xml_file = self.tar.extractfile(file_info)
        return etree.parse(xml_file)

    @transaction.commit_manually
    def read_xml_file(self,
            file_name = None,
            entry_name = None,
            model = None,
            fields = None,
            extra_field_mappings = None
        ):
        """
        * file_name - is name of xml file,
        * entry_name - name of entries to read from the xml file
        * model - model, which is to receive data
        * fields - list of field names in xml that will be translated to model fields
                   by simple substitiution of '-' with '_'
        * extra field mappings - list of two tuples where xml field names are
          translated to model fields in a special way
        """
        xml = self.get_file(file_name)
        items_saved = 0
        for xml_entry in xml.findall(entry_name):
            instance = model()
            for field in fields:
                value = get_val(xml_entry, field)
                model_field_name = field.replace('-', '_')
                max_length = instance._meta.get_field(model_field_name).max_length
                if value and max_length:
                    value = value[:max_length]
                setattr(instance, model_field_name, value)
            if extra_field_mappings:
                for (field, model_field_name) in extra_field_mappings:
                    value = get_val(xml_entry, field)
                    setattr(instance, model_field_name, value)
            instance.save()
            transaction.commit()
            items_saved += 1
            console.print_action('%d items' % items_saved)
        console.print_action('%d items' % items_saved, nowipe = True)


    def read_users(self):
        self.read_xml_file(
            file_name = 'users.xml',
            entry_name = 'user',
            model = zendesk_models.User,
            fields = (
                'created-at', 'is-active', 'last-login', 'name',
                'openid-url', 'organization-id', 'phone', 'restriction-id',
                'roles', 'time-zone', 'updated-at', 'uses-12-hour-clock',
                'email', 'is-verified', 'photo-url'
            ),
            extra_field_mappings = (('id', 'user_id'),)
        )

    def read_posts(self):
        self.read_xml_file(
            file_name = 'posts.xml',
            entry_name = 'post',
            model = zendesk_models.Post,
            fields = (
                'body', 'created-at', 'updated-at', 'entry-id',
                'forum-id', 'user-id', 'is-informative'
            ),
            extra_field_mappings = (
                ('id', 'post_id'),
            )
        )

    def read_forums(self):
        self.read_xml_file(
            file_name = 'forums.xml',
            entry_name = 'forum',
            model = zendesk_models.Forum,
            fields = (
                'description', 'display-type-id',
                'entries-count', 'is-locked',
                'name', 'organization-id',
                'position', 'updated-at',
                'translation-locale-id',
                'use-for-suggestions',
                'visibility-restriction-id',
                'is-public'
            ),
            extra_field_mappings = (('id', 'forum_id'),)
        )

    @transaction.commit_manually
    def import_users(self):
        added_users = 0
        for zd_user in zendesk_models.User.objects.all():
            #a whole bunch of fields are actually dropped now
            #see what's available in users.xml meanings of some
            #values there is not clear

            #if email is blank, just create a new user
            if zd_user.email == '':
                ab_user = create_askbot_user(zd_user)
                if ab_user in None:
                    print 'Warning: could not create user %s ' % zd_user.name
                    continue
                console.print_action(ab_user.username)
            else:
            #else see if user with the same email already exists
            #and only create new askbot user if email is not yet in the
            #database
                try:
                    ab_user = askbot_models.User.objects.get(email = zd_user.email)
                except askbot_models.User.DoesNotExist:
                    ab_user = create_askbot_user(zd_user)
                    if ab_user is None:
                        continue
                    console.print_action(ab_user.username, nowipe = True)
                    added_users += 1
            zd_user.askbot_user_id = ab_user.id
            zd_user.save()

            if zd_user.openid_url != None and \
                'askbot.deps.django_authopenid' in settings.INSTALLED_APPS:
                from askbot.deps.django_authopenid.models import UserAssociation
                from askbot.deps.django_authopenid.util import get_provider_name
                try:
                    assoc = UserAssociation(
                        user = ab_user,
                        openid_url = zd_user.openid_url,
                        provider_name = get_provider_name(zd_user.openid_url)
                    )
                    assoc.save()
                except:
                    #drop user association
                    pass

            transaction.commit()
        console.print_action('%d users added' % added_users, nowipe = True)

    @transaction.commit_manually
    def import_content(self):
        thread_ids = zendesk_models.Post.objects.values_list(
                                                        'entry_id',
                                                        flat = True
                                                    ).distinct()
        threads_posted = 0
        for thread_id in thread_ids:
            thread_entries = zendesk_models.Post.objects.filter(
                entry_id = thread_id
            ).order_by('created_at')
            question_post = thread_entries[0]
            question = post_question(question_post)
            question_post.is_processed = True
            question_post.save()
            transaction.commit()
            entry_count = thread_entries.count()
            threads_posted += 1
            console.print_action(str(threads_posted))
            if entry_count > 1:
                for answer_post in thread_entries[1:]:
                    post_answer(answer_post, question = question)
                    answer_post.is_processed = True
                    answer_post.save()
                    transaction.commit()
        console.print_action(str(threads_posted), nowipe = True)
