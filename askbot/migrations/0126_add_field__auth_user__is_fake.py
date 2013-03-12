# -*- coding: utf-8 -*-
from south.db import db
from south.v2 import SchemaMigration
from askbot.migrations_api import safe_add_column

class Migration(SchemaMigration):

    def forwards(self, orm):
        safe_add_column(
            u'auth_user', 'is_fake',
            self.gf('django.db.models.fields.BooleanField')(default=False), keep_default=False)

    def backwards(self, orm):
        db.delete_column('auth_user', 'is_fake')

    complete_apps = ['askbot']
