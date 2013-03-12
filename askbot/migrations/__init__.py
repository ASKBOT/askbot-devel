from south.db import db
from south.utils import ask_for_it_by_name
from south.v2 import SchemaMigration

if not db.has_ddl_transactions:
    SchemaMigration.no_dry_run = True

# Terminal ANSI codes for printing colored text:
# - http://code.google.com/p/testoob/source/browse/trunk/src/testoob/reporting/colored.py#20
# - http://stackoverflow.com/questions/287871/print-in-terminal-with-colors-using-python
TERM_RED_BOLD = '\x1b[31;01m\x1b[01m'
TERM_YELLOW = "\x1b[33;01m"
TERM_GREEN = "\x1b[32;06m"
TERM_RESET = '\x1b[0m'

def houston_do_we_have_a_problem(table):
    "Checks if we're using MySQL + InnoDB"
    if not db.dry_run and db.backend_name == 'mysql':
        db_table = [db._get_connection().settings_dict['NAME'], table]
        ret = db.execute(
            "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
            "where TABLE_SCHEMA = %s and TABLE_NAME = %s",
            db_table
        )
        assert len(ret) == 1 # There HAVE to be info about this table !
        assert len(ret[0]) == 2
        if ret[0][1] == 'InnoDB':
            print TERM_YELLOW, "!!!", '.'.join(db_table), "is InnoDB - using workarounds !!!", TERM_RESET
            return True
    return False


def innodb_ready_rename_column(orm, models, table, old_column_name, new_column_name, app_model, new_field_name):
    """
    Foreign key renaming which works for InnoDB
    More: http://south.aeracode.org/ticket/466

    Parameters:
    - orm: a reference to 'orm' parameter passed to Migration.forwards()/backwards()
    - models: reference to Migration.models data structure
    - table: e.g. 'askbot_thread'
    - old_column_name: e.g. 'question_post_id'
    - new_column_name: e.g. 'question_id'
    - app_model: e.g. 'askbot.thread' (should be a dict key into 'models')
    - new_field_name: e.g. 'question' (usually it's same as new_column_name, only without trailing '_id')
    """
    use_workaround = houston_do_we_have_a_problem(table)

    # ditch the foreign key
    if use_workaround:
        db.delete_foreign_key(table, old_column_name)

    # rename column
    db.rename_column(table, old_column_name, new_column_name)

    # restore the foreign key
    if not use_workaround:
        return

    model_def = models[app_model][new_field_name]
    assert model_def[0] == 'django.db.models.fields.related.ForeignKey'
    # Copy the dict so that we don't change the original
    # (otherwise the dry run would change it for the "normal" run
    #  and the latter would try to convert str to model once again)
    fkey_params = model_def[2].copy()
    assert 'to' in fkey_params
    assert fkey_params['to'].startswith("orm['")
    assert fkey_params['to'].endswith("']")
    fkey_params['to'] = orm[fkey_params['to'][5:-2]]  # convert "orm['app.models']" string to actual model
    field = ask_for_it_by_name(model_def[0])(**fkey_params)
    # INFO: ask_for_it_by_name() if equivalent to self.gf() which is usually used in migrations, e.g.:
    #          db.alter_column('askbot_badgedata', 'slug', self.gf('django.db.models.fields.SlugField')(unique=True, max_length=50))
    db.alter_column(table, new_column_name, field)
    db.clear_deferred_sql()
