# encoding: utf-8
import os
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

app_dir_name = os.path.basename(os.path.dirname(os.path.dirname(__file__)))

class Migration(SchemaMigration):
    
    def forwards(self, orm):
        
        # Adding model 'Mention'
        db.create_table(u'mention', (
            ('mentioned_by', self.gf('django.db.models.fields.related.ForeignKey')(related_name='mentions_sent', to=orm['auth.User'])),
            ('mentioned_at', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('object_id', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('content_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'])),
            ('mentioned_whom', self.gf('django.db.models.fields.related.ForeignKey')(related_name='mentions_received', to=orm['auth.User'])),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal(app_dir_name, ['Mention'])
    
    
    def backwards(self, orm):
        
        # Deleting model 'Mention'
        db.delete_table(u'mention')
    
    if app_dir_name == 'forum':
        models = {
            'auth.group': {
                'Meta': {'object_name': 'Group'},
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
                'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'blank': 'True'})
            },
            'auth.permission': {
                'Meta': {'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
                'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
                'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
            },
            'auth.user': {
                'Meta': {'object_name': 'User'},
                'about': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
                'bronze': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
                'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'date_of_birth': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
                'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
                'email_isvalid': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'email_key': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
                'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
                'gold': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
                'gravatar': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
                'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'blank': 'True'}),
                'hide_ignored_questions': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'blank': 'True'}),
                'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
                'last_seen': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'location': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
                'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
                'questions_per_page': ('django.db.models.fields.SmallIntegerField', [], {'default': '10'}),
                'real_name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
                'reputation': ('django.db.models.fields.PositiveIntegerField', [], {'default': '1'}),
                'silver': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
                'tag_filter_setting': ('django.db.models.fields.CharField', [], {'default': "'ignored'", 'max_length': '16'}),
                'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'blank': 'True'}),
                'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'}),
                'website': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'})
            },
            'contenttypes.contenttype': {
                'Meta': {'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
                'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
                'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
            },
            'forum.activity': {
                'Meta': {'object_name': 'Activity', 'db_table': "u'activity'"},
                'active_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'activity_type': ('django.db.models.fields.SmallIntegerField', [], {}),
                'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'is_auditted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
            },
            'forum.anonymousanswer': {
                'Meta': {'object_name': 'AnonymousAnswer'},
                'added_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'author': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'ip_addr': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
                'question': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'anonymous_answers'", 'to': "orm['forum.Question']"}),
                'session_key': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
                'summary': ('django.db.models.fields.CharField', [], {'max_length': '180'}),
                'text': ('django.db.models.fields.TextField', [], {}),
                'wiki': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'})
            },
            'forum.anonymousquestion': {
                'Meta': {'object_name': 'AnonymousQuestion'},
                'added_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'author': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'ip_addr': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
                'session_key': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
                'summary': ('django.db.models.fields.CharField', [], {'max_length': '180'}),
                'tagnames': ('django.db.models.fields.CharField', [], {'max_length': '125'}),
                'text': ('django.db.models.fields.TextField', [], {}),
                'title': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
                'wiki': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'})
            },
            'forum.answer': {
                'Meta': {'object_name': 'Answer', 'db_table': "u'answer'"},
                'accepted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'accepted_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
                'added_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'author': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'answers'", 'to': "orm['auth.User']"}),
                'comment_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
                'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'deleted_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
                'deleted_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'deleted_answers'", 'null': 'True', 'to': "orm['auth.User']"}),
                'html': ('django.db.models.fields.TextField', [], {'null': 'True'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'last_edited_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
                'last_edited_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'last_edited_answers'", 'null': 'True', 'to': "orm['auth.User']"}),
                'locked': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'locked_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
                'locked_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'locked_answers'", 'null': 'True', 'to': "orm['auth.User']"}),
                'offensive_flag_count': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
                'question': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'answers'", 'to': "orm['forum.Question']"}),
                'score': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
                'text': ('django.db.models.fields.TextField', [], {'null': 'True'}),
                'vote_down_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
                'vote_up_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
                'wiki': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'wikified_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
            },
            'forum.answerrevision': {
                'Meta': {'object_name': 'AnswerRevision', 'db_table': "u'answer_revision'"},
                'answer': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'to': "orm['forum.Answer']"}),
                'author': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'answerrevisions'", 'to': "orm['auth.User']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'revised_at': ('django.db.models.fields.DateTimeField', [], {}),
                'revision': ('django.db.models.fields.PositiveIntegerField', [], {}),
                'summary': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
                'text': ('django.db.models.fields.TextField', [], {})
            },
            'forum.authkeyuserassociation': {
                'Meta': {'object_name': 'AuthKeyUserAssociation'},
                'added_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'key': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
                'provider': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'auth_keys'", 'to': "orm['auth.User']"})
            },
            'forum.award': {
                'Meta': {'object_name': 'Award', 'db_table': "u'award'"},
                'awarded_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'badge': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'award_badge'", 'to': "orm['forum.Badge']"}),
                'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'notified': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'award_user'", 'to': "orm['auth.User']"})
            },
            'forum.badge': {
                'Meta': {'unique_together': "(('name', 'type'),)", 'object_name': 'Badge', 'db_table': "u'badge'"},
                'awarded_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
                'awarded_to': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'badges'", 'through': "'Award'", 'to': "orm['auth.User']"}),
                'description': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'multiple': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'name': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
                'slug': ('django.db.models.fields.SlugField', [], {'db_index': 'True', 'max_length': '50', 'blank': 'True'}),
                'type': ('django.db.models.fields.SmallIntegerField', [], {})
            },
            'forum.book': {
                'Meta': {'object_name': 'Book', 'db_table': "u'book'"},
                'added_at': ('django.db.models.fields.DateTimeField', [], {}),
                'author': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
                'cover_img': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'last_edited_at': ('django.db.models.fields.DateTimeField', [], {}),
                'pages': ('django.db.models.fields.SmallIntegerField', [], {}),
                'price': ('django.db.models.fields.DecimalField', [], {'max_digits': '6', 'decimal_places': '2'}),
                'publication': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
                'published_at': ('django.db.models.fields.DateTimeField', [], {}),
                'questions': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'book'", 'db_table': "'book_question'", 'to': "orm['forum.Question']"}),
                'short_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
                'tagnames': ('django.db.models.fields.CharField', [], {'max_length': '125'}),
                'title': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
            },
            'forum.bookauthorinfo': {
                'Meta': {'object_name': 'BookAuthorInfo', 'db_table': "u'book_author_info'"},
                'added_at': ('django.db.models.fields.DateTimeField', [], {}),
                'blog_url': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
                'book': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['forum.Book']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'last_edited_at': ('django.db.models.fields.DateTimeField', [], {}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
            },
            'forum.bookauthorrss': {
                'Meta': {'object_name': 'BookAuthorRss', 'db_table': "u'book_author_rss'"},
                'added_at': ('django.db.models.fields.DateTimeField', [], {}),
                'book': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['forum.Book']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'rss_created_at': ('django.db.models.fields.DateTimeField', [], {}),
                'title': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
                'url': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
            },
            'forum.comment': {
                'Meta': {'object_name': 'Comment', 'db_table': "u'comment'"},
                'added_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'comment': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
                'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'comments'", 'to': "orm['auth.User']"})
            },
            'forum.emailfeedsetting': {
                'Meta': {'object_name': 'EmailFeedSetting'},
                'added_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
                'feed_type': ('django.db.models.fields.CharField', [], {'max_length': '16'}),
                'frequency': ('django.db.models.fields.CharField', [], {'default': "'n'", 'max_length': '8'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'reported_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
                'subscriber': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'notification_subscriptions'", 'to': "orm['auth.User']"})
            },
            'forum.favoritequestion': {
                'Meta': {'object_name': 'FavoriteQuestion', 'db_table': "u'favorite_question'"},
                'added_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'question': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['forum.Question']"}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'user_favorite_questions'", 'to': "orm['auth.User']"})
            },
            'forum.flaggeditem': {
                'Meta': {'unique_together': "(('content_type', 'object_id', 'user'),)", 'object_name': 'FlaggedItem', 'db_table': "u'flagged_item'"},
                'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
                'flagged_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'flaggeditems'", 'to': "orm['auth.User']"})
            },
            'forum.markedtag': {
                'Meta': {'object_name': 'MarkedTag'},
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'reason': ('django.db.models.fields.CharField', [], {'max_length': '16'}),
                'tag': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'user_selections'", 'to': "orm['forum.Tag']"}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'tag_selections'", 'to': "orm['auth.User']"})
            },
            'forum.mention': {
                'Meta': {'object_name': 'Mention', 'db_table': "u'mention'"},
                'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'mentioned_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'mentioned_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'mentions_sent'", 'to': "orm['auth.User']"}),
                'mentioned_whom': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'mentions_received'", 'to': "orm['auth.User']"}),
                'object_id': ('django.db.models.fields.PositiveIntegerField', [], {})
            },
            'forum.question': {
                'Meta': {'object_name': 'Question', 'db_table': "u'question'"},
                'added_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'answer_accepted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'answer_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
                'author': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'questions'", 'to': "orm['auth.User']"}),
                'close_reason': ('django.db.models.fields.SmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
                'closed': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'closed_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
                'closed_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'closed_questions'", 'null': 'True', 'to': "orm['auth.User']"}),
                'comment_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
                'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'deleted_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
                'deleted_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'deleted_questions'", 'null': 'True', 'to': "orm['auth.User']"}),
                'favorited_by': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'favorite_questions'", 'through': "'FavoriteQuestion'", 'to': "orm['auth.User']"}),
                'favourite_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
                'followed_by': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'followed_questions'", 'to': "orm['auth.User']"}),
                'html': ('django.db.models.fields.TextField', [], {'null': 'True'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'last_activity_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'last_activity_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'last_active_in_questions'", 'to': "orm['auth.User']"}),
                'last_edited_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
                'last_edited_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'last_edited_questions'", 'null': 'True', 'to': "orm['auth.User']"}),
                'locked': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'locked_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
                'locked_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'locked_questions'", 'null': 'True', 'to': "orm['auth.User']"}),
                'offensive_flag_count': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
                'score': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
                'summary': ('django.db.models.fields.CharField', [], {'max_length': '180'}),
                'tagnames': ('django.db.models.fields.CharField', [], {'max_length': '125'}),
                'tags': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'questions'", 'to': "orm['forum.Tag']"}),
                'text': ('django.db.models.fields.TextField', [], {'null': 'True'}),
                'title': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
                'view_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
                'vote_down_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
                'vote_up_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
                'wiki': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'wikified_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
            },
            'forum.questionrevision': {
                'Meta': {'object_name': 'QuestionRevision', 'db_table': "u'question_revision'"},
                'author': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'questionrevisions'", 'to': "orm['auth.User']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'question': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'to': "orm['forum.Question']"}),
                'revised_at': ('django.db.models.fields.DateTimeField', [], {}),
                'revision': ('django.db.models.fields.PositiveIntegerField', [], {}),
                'summary': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
                'tagnames': ('django.db.models.fields.CharField', [], {'max_length': '125'}),
                'text': ('django.db.models.fields.TextField', [], {}),
                'title': ('django.db.models.fields.CharField', [], {'max_length': '300'})
            },
            'forum.questionview': {
                'Meta': {'object_name': 'QuestionView'},
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'question': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'viewed'", 'to': "orm['forum.Question']"}),
                'when': ('django.db.models.fields.DateTimeField', [], {}),
                'who': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'question_views'", 'to': "orm['auth.User']"})
            },
            'forum.repute': {
                'Meta': {'object_name': 'Repute', 'db_table': "u'repute'"},
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'negative': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
                'positive': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
                'question': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['forum.Question']"}),
                'reputation': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
                'reputation_type': ('django.db.models.fields.SmallIntegerField', [], {}),
                'reputed_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
            },
            'forum.tag': {
                'Meta': {'object_name': 'Tag', 'db_table': "u'tag'"},
                'created_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'created_tags'", 'to': "orm['auth.User']"}),
                'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'deleted_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
                'deleted_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'deleted_tags'", 'null': 'True', 'to': "orm['auth.User']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
                'used_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'})
            },
            'forum.validationhash': {
                'Meta': {'unique_together': "(('user', 'type'),)", 'object_name': 'ValidationHash'},
                'expiration': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2010, 5, 17, 13, 4, 34, 910299)'}),
                'hash_code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'seed': ('django.db.models.fields.CharField', [], {'max_length': '12'}),
                'type': ('django.db.models.fields.CharField', [], {'max_length': '12'}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
            },
            'forum.vote': {
                'Meta': {'unique_together': "(('content_type', 'object_id', 'user'),)", 'object_name': 'Vote', 'db_table': "u'vote'"},
                'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'votes'", 'to': "orm['auth.User']"}),
                'vote': ('django.db.models.fields.SmallIntegerField', [], {}),
                'voted_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'})
            }
        }
    else:
        models = {
            'auth.group': {
                'Meta': {'object_name': 'Group'},
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
                'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'blank': 'True'})
            },
            'auth.permission': {
                'Meta': {'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
                'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
                'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
            },
            'auth.user': {
                'Meta': {'object_name': 'User'},
                'about': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
                'bronze': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
                'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'date_of_birth': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
                'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
                'email_isvalid': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'email_key': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
                'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
                'gold': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
                'gravatar': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
                'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'blank': 'True'}),
                'hide_ignored_questions': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'blank': 'True'}),
                'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
                'last_seen': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'location': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
                'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
                'questions_per_page': ('django.db.models.fields.SmallIntegerField', [], {'default': '10'}),
                'real_name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
                'reputation': ('django.db.models.fields.PositiveIntegerField', [], {'default': '1'}),
                'silver': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
                'tag_filter_setting': ('django.db.models.fields.CharField', [], {'default': "'ignored'", 'max_length': '16'}),
                'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'blank': 'True'}),
                'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'}),
                'website': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'})
            },
            'contenttypes.contenttype': {
                'Meta': {'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
                'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
                'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
            },
            'askbot.activity': {
                'Meta': {'object_name': 'Activity', 'db_table': "u'activity'"},
                'active_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'activity_type': ('django.db.models.fields.SmallIntegerField', [], {}),
                'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'is_auditted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
            },
            'askbot.anonymousanswer': {
                'Meta': {'object_name': 'AnonymousAnswer'},
                'added_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'author': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'ip_addr': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
                'question': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'anonymous_answers'", 'to': "orm['askbot.Question']"}),
                'session_key': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
                'summary': ('django.db.models.fields.CharField', [], {'max_length': '180'}),
                'text': ('django.db.models.fields.TextField', [], {}),
                'wiki': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'})
            },
            'askbot.anonymousquestion': {
                'Meta': {'object_name': 'AnonymousQuestion'},
                'added_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'author': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'ip_addr': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
                'session_key': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
                'summary': ('django.db.models.fields.CharField', [], {'max_length': '180'}),
                'tagnames': ('django.db.models.fields.CharField', [], {'max_length': '125'}),
                'text': ('django.db.models.fields.TextField', [], {}),
                'title': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
                'wiki': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'})
            },
            'askbot.answer': {
                'Meta': {'object_name': 'Answer', 'db_table': "u'answer'"},
                'accepted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'accepted_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
                'added_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'author': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'answers'", 'to': "orm['auth.User']"}),
                'comment_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
                'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'deleted_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
                'deleted_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'deleted_answers'", 'null': 'True', 'to': "orm['auth.User']"}),
                'html': ('django.db.models.fields.TextField', [], {'null': 'True'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'last_edited_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
                'last_edited_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'last_edited_answers'", 'null': 'True', 'to': "orm['auth.User']"}),
                'locked': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'locked_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
                'locked_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'locked_answers'", 'null': 'True', 'to': "orm['auth.User']"}),
                'offensive_flag_count': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
                'question': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'answers'", 'to': "orm['askbot.Question']"}),
                'score': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
                'text': ('django.db.models.fields.TextField', [], {'null': 'True'}),
                'vote_down_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
                'vote_up_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
                'wiki': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'wikified_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
            },
            'askbot.answerrevision': {
                'Meta': {'object_name': 'AnswerRevision', 'db_table': "u'answer_revision'"},
                'answer': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'to': "orm['askbot.Answer']"}),
                'author': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'answerrevisions'", 'to': "orm['auth.User']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'revised_at': ('django.db.models.fields.DateTimeField', [], {}),
                'revision': ('django.db.models.fields.PositiveIntegerField', [], {}),
                'summary': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
                'text': ('django.db.models.fields.TextField', [], {})
            },
            'askbot.authkeyuserassociation': {
                'Meta': {'object_name': 'AuthKeyUserAssociation'},
                'added_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'key': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
                'provider': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'auth_keys'", 'to': "orm['auth.User']"})
            },
            'askbot.award': {
                'Meta': {'object_name': 'Award', 'db_table': "u'award'"},
                'awarded_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'badge': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'award_badge'", 'to': "orm['askbot.Badge']"}),
                'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'notified': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'award_user'", 'to': "orm['auth.User']"})
            },
            'askbot.badge': {
                'Meta': {'unique_together': "(('name', 'type'),)", 'object_name': 'Badge', 'db_table': "u'badge'"},
                'awarded_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
                'awarded_to': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'badges'", 'through': "'Award'", 'to': "orm['auth.User']"}),
                'description': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'multiple': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'name': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
                'slug': ('django.db.models.fields.SlugField', [], {'db_index': 'True', 'max_length': '50', 'blank': 'True'}),
                'type': ('django.db.models.fields.SmallIntegerField', [], {})
            },
            'askbot.book': {
                'Meta': {'object_name': 'Book', 'db_table': "u'book'"},
                'added_at': ('django.db.models.fields.DateTimeField', [], {}),
                'author': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
                'cover_img': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'last_edited_at': ('django.db.models.fields.DateTimeField', [], {}),
                'pages': ('django.db.models.fields.SmallIntegerField', [], {}),
                'price': ('django.db.models.fields.DecimalField', [], {'max_digits': '6', 'decimal_places': '2'}),
                'publication': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
                'published_at': ('django.db.models.fields.DateTimeField', [], {}),
                'questions': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'book'", 'db_table': "'book_question'", 'to': "orm['askbot.Question']"}),
                'short_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
                'tagnames': ('django.db.models.fields.CharField', [], {'max_length': '125'}),
                'title': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
            },
            'askbot.bookauthorinfo': {
                'Meta': {'object_name': 'BookAuthorInfo', 'db_table': "u'book_author_info'"},
                'added_at': ('django.db.models.fields.DateTimeField', [], {}),
                'blog_url': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
                'book': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['askbot.Book']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'last_edited_at': ('django.db.models.fields.DateTimeField', [], {}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
            },
            'askbot.bookauthorrss': {
                'Meta': {'object_name': 'BookAuthorRss', 'db_table': "u'book_author_rss'"},
                'added_at': ('django.db.models.fields.DateTimeField', [], {}),
                'book': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['askbot.Book']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'rss_created_at': ('django.db.models.fields.DateTimeField', [], {}),
                'title': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
                'url': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
            },
            'askbot.comment': {
                'Meta': {'object_name': 'Comment', 'db_table': "u'comment'"},
                'added_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'comment': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
                'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'comments'", 'to': "orm['auth.User']"})
            },
            'askbot.emailfeedsetting': {
                'Meta': {'object_name': 'EmailFeedSetting'},
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
                'question': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['askbot.Question']"}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'user_favorite_questions'", 'to': "orm['auth.User']"})
            },
            'askbot.flaggeditem': {
                'Meta': {'unique_together': "(('content_type', 'object_id', 'user'),)", 'object_name': 'FlaggedItem', 'db_table': "u'flagged_item'"},
                'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
                'flagged_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'flaggeditems'", 'to': "orm['auth.User']"})
            },
            'askbot.markedtag': {
                'Meta': {'object_name': 'MarkedTag'},
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'reason': ('django.db.models.fields.CharField', [], {'max_length': '16'}),
                'tag': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'user_selections'", 'to': "orm['askbot.Tag']"}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'tag_selections'", 'to': "orm['auth.User']"})
            },
            'askbot.mention': {
                'Meta': {'object_name': 'Mention', 'db_table': "u'mention'"},
                'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'mentioned_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'mentioned_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'mentions_sent'", 'to': "orm['auth.User']"}),
                'mentioned_whom': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'mentions_received'", 'to': "orm['auth.User']"}),
                'object_id': ('django.db.models.fields.PositiveIntegerField', [], {})
            },
            'askbot.question': {
                'Meta': {'object_name': 'Question', 'db_table': "u'question'"},
                'added_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'answer_accepted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'answer_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
                'author': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'questions'", 'to': "orm['auth.User']"}),
                'close_reason': ('django.db.models.fields.SmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
                'closed': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'closed_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
                'closed_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'closed_questions'", 'null': 'True', 'to': "orm['auth.User']"}),
                'comment_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
                'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'deleted_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
                'deleted_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'deleted_questions'", 'null': 'True', 'to': "orm['auth.User']"}),
                'favorited_by': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'favorite_questions'", 'through': "'FavoriteQuestion'", 'to': "orm['auth.User']"}),
                'favourite_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
                'followed_by': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'followed_questions'", 'to': "orm['auth.User']"}),
                'html': ('django.db.models.fields.TextField', [], {'null': 'True'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'last_activity_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'last_activity_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'last_active_in_questions'", 'to': "orm['auth.User']"}),
                'last_edited_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
                'last_edited_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'last_edited_questions'", 'null': 'True', 'to': "orm['auth.User']"}),
                'locked': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'locked_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
                'locked_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'locked_questions'", 'null': 'True', 'to': "orm['auth.User']"}),
                'offensive_flag_count': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
                'score': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
                'summary': ('django.db.models.fields.CharField', [], {'max_length': '180'}),
                'tagnames': ('django.db.models.fields.CharField', [], {'max_length': '125'}),
                'tags': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'questions'", 'to': "orm['askbot.Tag']"}),
                'text': ('django.db.models.fields.TextField', [], {'null': 'True'}),
                'title': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
                'view_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
                'vote_down_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
                'vote_up_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
                'wiki': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'wikified_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
            },
            'askbot.questionrevision': {
                'Meta': {'object_name': 'QuestionRevision', 'db_table': "u'question_revision'"},
                'author': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'questionrevisions'", 'to': "orm['auth.User']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'question': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'to': "orm['askbot.Question']"}),
                'revised_at': ('django.db.models.fields.DateTimeField', [], {}),
                'revision': ('django.db.models.fields.PositiveIntegerField', [], {}),
                'summary': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
                'tagnames': ('django.db.models.fields.CharField', [], {'max_length': '125'}),
                'text': ('django.db.models.fields.TextField', [], {}),
                'title': ('django.db.models.fields.CharField', [], {'max_length': '300'})
            },
            'askbot.questionview': {
                'Meta': {'object_name': 'QuestionView'},
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'question': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'viewed'", 'to': "orm['askbot.Question']"}),
                'when': ('django.db.models.fields.DateTimeField', [], {}),
                'who': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'question_views'", 'to': "orm['auth.User']"})
            },
            'askbot.repute': {
                'Meta': {'object_name': 'Repute', 'db_table': "u'repute'"},
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'negative': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
                'positive': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
                'question': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['askbot.Question']"}),
                'reputation': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
                'reputation_type': ('django.db.models.fields.SmallIntegerField', [], {}),
                'reputed_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
            },
            'askbot.tag': {
                'Meta': {'object_name': 'Tag', 'db_table': "u'tag'"},
                'created_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'created_tags'", 'to': "orm['auth.User']"}),
                'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
                'deleted_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
                'deleted_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'deleted_tags'", 'null': 'True', 'to': "orm['auth.User']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
                'used_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'})
            },
            'askbot.validationhash': {
                'Meta': {'unique_together': "(('user', 'type'),)", 'object_name': 'ValidationHash'},
                'expiration': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2010, 5, 17, 13, 4, 34, 910299)'}),
                'hash_code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'seed': ('django.db.models.fields.CharField', [], {'max_length': '12'}),
                'type': ('django.db.models.fields.CharField', [], {'max_length': '12'}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
            },
            'askbot.vote': {
                'Meta': {'unique_together': "(('content_type', 'object_id', 'user'),)", 'object_name': 'Vote', 'db_table': "u'vote'"},
                'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
                'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
                'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
                'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'votes'", 'to': "orm['auth.User']"}),
                'vote': ('django.db.models.fields.SmallIntegerField', [], {}),
                'voted_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'})
            }
        }
        
    complete_apps = [app_dir_name]
