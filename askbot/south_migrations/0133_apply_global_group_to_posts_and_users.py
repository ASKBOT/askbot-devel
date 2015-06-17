# -*- coding: utf-8 -*-
import datetime
import re
from south.db import db
from south.v2 import DataMigration
from django.db import models
from django.core.management.base import CommandError
from askbot.conf import settings as askbot_settings
from askbot.utils.console import ProgressBar

def clean_group_name(name):
    """group names allow spaces,
    tag names do not, so we use this method
    to replace spaces with dashes"""
    return re.sub('\s+', '-', name.strip())

def get_superuser(orm):
    """returns superuser, assumes that user
    with the lowest id with the superuser status
    otherwise - if there are no users at all -
    will return None
    and finally if there are users, but no super -
    will fail and ask create a superuser
    """
    try:
        return orm['auth.User'].objects.filter(
                        is_superuser=True
                    ).order_by('id')[0]
    except IndexError:
        if orm['auth.User'].objects.count() > 0:
            raise CommandError('Please create a superuser to continue')
        else:
            return None

def create_group(orm, name=None, created_by=None):
    """creates a group with a given name and the founder"""
    group = orm['askbot.Tag']()
    group.name = name
    group.created_by = created_by
    group.save()

    group_profile = orm['askbot.GroupProfile']()
    group_profile.group_tag = group
    group_profile.save()

    return group

def get_global_group(orm):
    """returns the "global user group" if exists
    otherwise will attempt to create the group -
    if a superuser exists (which may fail)
    and if superuser does not exist - then
    return None
    """
    group_name = clean_group_name(askbot_settings.GLOBAL_GROUP_NAME)
    model = orm['askbot.Tag']
    try:
        return model.objects.get(name=group_name)
    except model.DoesNotExist:
        superuser = get_superuser(orm)
        if superuser:
            return create_group(
                            orm,
                            name=group_name,
                            created_by=superuser
                    )
        else:
            return None


class Migration(DataMigration):

    def forwards(self, orm):
        "Write your forwards methods here."
        group = get_global_group(orm)

        items = orm['askbot.Thread'].objects.all()
        message = 'Moving group-less threads to the global group'
        done_count = 0
        for thread in ProgressBar(items.iterator(), items.count(), message):
            if thread.groups.count() == 0:
                thread.groups.add(group)
                done_count += 1

        if items.count():
            print 'Added global group to %d threads.\n' % done_count

        post_types = ('question', 'answer')
        posts = orm['askbot.Post'].objects.filter(post_type__in=post_types)
        message = 'Move groupless questions and answers to the global group'
        done_count = 0
        for post in ProgressBar(posts.iterator(), posts.count(), message):
            if post.groups.count() == 0:
                post.groups.add(group)
                done_count += 1

        if posts.count():
            print 'Added global group to %d posts.\n' % done_count

        comments = orm['askbot.Post'].objects.filter(post_type='comment')
        message = 'Copying group information from answers ' +\
            'and questions to comments'
        done_count = 0
        for comment in ProgressBar(comments.iterator(), comments.count(), message):
            if comment.groups.count() == 0:
                parent_post_groups = comment.parent.groups.all()
                comment.groups.add(*parent_post_groups)
                done_count += 1

        if comments.count():
            print 'Added global group to %d comments.\n' % done_count

        users = orm['auth.User'].objects.all()
        message = 'Adding all users to the global group'
        done_count = 0
        for user in ProgressBar(users.iterator(), users.count(), message):
            cls = orm['askbot.GroupMembership']
            if not cls.objects.filter(user=user, group=group).exists():
                membership = cls(user=user, group=group)
                membership.save()
                done_count += 1

        if users.count():
            print 'Added global group to %d users.' % done_count


    def backwards(self, orm):
        "Write your backwards methods here."
        pass


    models = {
        'askbot.activity': {
            'Meta': {'object_name': 'Activity', 'db_table': "u'activity'"},
            'active_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'activity_type': ('django.db.models.fields.SmallIntegerField', [], {}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_auditted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'question': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['askbot.Post']", 'null': 'True'}),
            'receiving_users': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'received_activity'", 'symmetrical': 'False', 'to': "orm['auth.User']"}),
            'recipients': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'incoming_activity'", 'symmetrical': 'False', 'through': "orm['askbot.ActivityAuditStatus']", 'to': "orm['auth.User']"}),
            'summary': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'askbot.activityauditstatus': {
            'Meta': {'unique_together': "(('user', 'activity'),)", 'object_name': 'ActivityAuditStatus'},
            'activity': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['askbot.Activity']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'status': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'askbot.anonymousanswer': {
            'Meta': {'object_name': 'AnonymousAnswer'},
            'added_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'author': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip_addr': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'question': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'anonymous_answers'", 'to': "orm['askbot.Post']"}),
            'session_key': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'summary': ('django.db.models.fields.CharField', [], {'max_length': '180'}),
            'text': ('django.db.models.fields.TextField', [], {}),
            'wiki': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'askbot.anonymousquestion': {
            'Meta': {'object_name': 'AnonymousQuestion'},
            'added_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'author': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip_addr': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'is_anonymous': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'session_key': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'summary': ('django.db.models.fields.CharField', [], {'max_length': '180'}),
            'tagnames': ('django.db.models.fields.CharField', [], {'max_length': '125'}),
            'text': ('django.db.models.fields.TextField', [], {}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
            'wiki': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'askbot.award': {
            'Meta': {'object_name': 'Award', 'db_table': "u'award'"},
            'awarded_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'badge': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'award_badge'", 'to': "orm['askbot.BadgeData']"}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'notified': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'award_user'", 'to': "orm['auth.User']"})
        },
        'askbot.badgedata': {
            'Meta': {'ordering': "('slug',)", 'object_name': 'BadgeData'},
            'awarded_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'awarded_to': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'badges'", 'symmetrical': 'False', 'through': "orm['askbot.Award']", 'to': "orm['auth.User']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '50'})
        },
        'askbot.draftanswer': {
            'Meta': {'object_name': 'DraftAnswer'},
            'author': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'draft_answers'", 'to': "orm['auth.User']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'text': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'thread': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'draft_answers'", 'to': "orm['askbot.Thread']"})
        },
        'askbot.draftquestion': {
            'Meta': {'object_name': 'DraftQuestion'},
            'author': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'tagnames': ('django.db.models.fields.CharField', [], {'max_length': '125', 'null': 'True'}),
            'text': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '300', 'null': 'True'})
        },
        'askbot.emailfeedsetting': {
            'Meta': {'unique_together': "(('subscriber', 'feed_type'),)", 'object_name': 'EmailFeedSetting'},
            'added_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'feed_type': ('django.db.models.fields.CharField', [], {'max_length': '16'}),
            'frequency': ('django.db.models.fields.CharField', [], {'default': "'n'", 'max_length': '8'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'reported_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'subscriber': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'notification_subscriptions'", 'to': "orm['auth.User']"})
        },
        'askbot.favoritequestion': {
            'Meta': {'object_name': 'FavoriteQuestion', 'db_table': "u'favorite_question'"},
            'added_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'thread': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['askbot.Thread']"}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'user_favorite_questions'", 'to': "orm['auth.User']"})
        },
        'askbot.groupmembership': {
            'Meta': {'unique_together': "(('group', 'user'),)", 'object_name': 'GroupMembership'},
            'group': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'user_memberships'", 'to': "orm['askbot.Tag']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'group_memberships'", 'to': "orm['auth.User']"})
        },
        'askbot.groupprofile': {
            'Meta': {'object_name': 'GroupProfile'},
            'group_tag': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'group_profile'", 'unique': 'True', 'to': "orm['askbot.Tag']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_open': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'logo_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True'}),
            'moderate_email': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'preapproved_email_domains': ('django.db.models.fields.TextField', [], {'default': "''", 'null': 'True', 'blank': 'True'}),
            'preapproved_emails': ('django.db.models.fields.TextField', [], {'default': "''", 'null': 'True', 'blank': 'True'})
        },
        'askbot.markedtag': {
            'Meta': {'object_name': 'MarkedTag'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'reason': ('django.db.models.fields.CharField', [], {'max_length': '16'}),
            'tag': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'user_selections'", 'to': "orm['askbot.Tag']"}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'tag_selections'", 'to': "orm['auth.User']"})
        },
        'askbot.post': {
            'Meta': {'object_name': 'Post'},
            'added_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'approved': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'db_index': 'True'}),
            'author': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'posts'", 'to': "orm['auth.User']"}),
            'comment_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'deleted_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'deleted_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'deleted_posts'", 'null': 'True', 'to': "orm['auth.User']"}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'group_posts'", 'symmetrical': 'False', 'to': "orm['askbot.Tag']"}),
            'html': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_anonymous': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_edited_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'last_edited_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'last_edited_posts'", 'null': 'True', 'to': "orm['auth.User']"}),
            'locked': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'locked_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'locked_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'locked_posts'", 'null': 'True', 'to': "orm['auth.User']"}),
            'offensive_flag_count': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'old_answer_id': ('django.db.models.fields.PositiveIntegerField', [], {'default': 'None', 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'old_comment_id': ('django.db.models.fields.PositiveIntegerField', [], {'default': 'None', 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'old_question_id': ('django.db.models.fields.PositiveIntegerField', [], {'default': 'None', 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'comments'", 'null': 'True', 'to': "orm['askbot.Post']"}),
            'post_type': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'score': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'summary': ('django.db.models.fields.CharField', [], {'max_length': '180'}),
            'text': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'thread': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'posts'", 'null': 'True', 'blank': 'True', 'to': "orm['askbot.Thread']"}),
            'vote_down_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'vote_up_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'wiki': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'wikified_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        'askbot.postflagreason': {
            'Meta': {'object_name': 'PostFlagReason'},
            'added_at': ('django.db.models.fields.DateTimeField', [], {}),
            'author': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"}),
            'details': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'post_reject_reasons'", 'to': "orm['askbot.Post']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '128'})
        },
        'askbot.postrevision': {
            'Meta': {'ordering': "('-revision',)", 'unique_together': "(('post', 'revision'),)", 'object_name': 'PostRevision'},
            'approved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'approved_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'approved_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'author': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'postrevisions'", 'to': "orm['auth.User']"}),
            'by_email': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'email_address': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_anonymous': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'post': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'revisions'", 'null': 'True', 'to': "orm['askbot.Post']"}),
            'revised_at': ('django.db.models.fields.DateTimeField', [], {}),
            'revision': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'summary': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
            'tagnames': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '125', 'blank': 'True'}),
            'text': ('django.db.models.fields.TextField', [], {}),
            'title': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '300', 'blank': 'True'})
        },
        'askbot.questionview': {
            'Meta': {'object_name': 'QuestionView'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'question': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'viewed'", 'to': "orm['askbot.Post']"}),
            'when': ('django.db.models.fields.DateTimeField', [], {}),
            'who': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'question_views'", 'to': "orm['auth.User']"})
        },
        'askbot.replyaddress': {
            'Meta': {'object_name': 'ReplyAddress'},
            'address': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '25'}),
            'allowed_from_email': ('django.db.models.fields.EmailField', [], {'max_length': '150'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'post': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'reply_addresses'", 'null': 'True', 'to': "orm['askbot.Post']"}),
            'reply_action': ('django.db.models.fields.CharField', [], {'default': "'auto_answer_or_comment'", 'max_length': '32'}),
            'response_post': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'edit_addresses'", 'null': 'True', 'to': "orm['askbot.Post']"}),
            'used_at': ('django.db.models.fields.DateTimeField', [], {'default': 'None', 'null': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'askbot.repute': {
            'Meta': {'object_name': 'Repute', 'db_table': "u'repute'"},
            'comment': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'negative': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'positive': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'question': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['askbot.Post']", 'null': 'True', 'blank': 'True'}),
            'reputation': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'reputation_type': ('django.db.models.fields.SmallIntegerField', [], {}),
            'reputed_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'askbot.tag': {
            'Meta': {'ordering': "('-used_count', 'name')", 'object_name': 'Tag', 'db_table': "u'tag'"},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'created_tags'", 'to': "orm['auth.User']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'deleted_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'deleted_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'deleted_tags'", 'null': 'True', 'to': "orm['auth.User']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'status': ('django.db.models.fields.SmallIntegerField', [], {'default': '1'}),
            'suggested_by': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'suggested_tags'", 'symmetrical': 'False', 'to': "orm['auth.User']"}),
            'tag_wiki': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'described_tag'", 'unique': 'True', 'null': 'True', 'to': "orm['askbot.Post']"}),
            'used_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'})
        },
        'askbot.thread': {
            'Meta': {'object_name': 'Thread'},
            'accepted_answer': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'+'", 'null': 'True', 'to': "orm['askbot.Post']"}),
            'added_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'answer_accepted_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'answer_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'approved': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'db_index': 'True'}),
            'close_reason': ('django.db.models.fields.SmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'closed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'closed_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'closed_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'favorited_by': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'unused_favorite_threads'", 'symmetrical': 'False', 'through': "orm['askbot.FavoriteQuestion']", 'to': "orm['auth.User']"}),
            'favourite_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'followed_by': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'followed_threads'", 'symmetrical': 'False', 'to': "orm['auth.User']"}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'group_threads'", 'symmetrical': 'False', 'to': "orm['askbot.Tag']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_activity_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_activity_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'unused_last_active_in_threads'", 'to': "orm['auth.User']"}),
            'score': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'tagnames': ('django.db.models.fields.CharField', [], {'max_length': '125'}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'threads'", 'symmetrical': 'False', 'to': "orm['askbot.Tag']"}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
            'view_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'})
        },
        'askbot.vote': {
            'Meta': {'unique_together': "(('user', 'voted_post'),)", 'object_name': 'Vote', 'db_table': "u'vote'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'votes'", 'to': "orm['auth.User']"}),
            'vote': ('django.db.models.fields.SmallIntegerField', [], {}),
            'voted_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'voted_post': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'votes'", 'to': "orm['askbot.Post']"})
        },
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'about': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'avatar_type': ('django.db.models.fields.CharField', [], {'default': "'n'", 'max_length': '1'}),
            'bronze': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'consecutive_days_visit_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'country': ('django_countries.fields.CountryField', [], {'max_length': '2', 'blank': 'True'}),
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'date_of_birth': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'display_tag_filter_strategy': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'email_isvalid': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'email_key': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'email_signature': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'email_tag_filter_strategy': ('django.db.models.fields.SmallIntegerField', [], {'default': '1'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'gold': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'gravatar': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ignored_tags': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'interesting_tags': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_fake': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'last_seen': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'location': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'new_response_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'questions_per_page': ('django.db.models.fields.SmallIntegerField', [], {'default': '10'}),
            'real_name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'reputation': ('django.db.models.fields.PositiveIntegerField', [], {'default': '1'}),
            'seen_response_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'show_country': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'show_marked_tags': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'silver': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'w'", 'max_length': '2'}),
            'subscribed_tags': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'}),
            'website': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        }
    }

    complete_apps = ['askbot']
    symmetrical = True
