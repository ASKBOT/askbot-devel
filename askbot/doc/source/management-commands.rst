==========================
Askbot management commands
==========================

There are a number of command line utilities help the forum administrator
perform a range of tasks such as add or revoke administration privileges, back up and restore
the forum data, fix database errors if such occur, etc.

To run these commands there is a general pattern::

    cd project_directory
    python manage.py some_command [possible arguments and parameters]

I.e. the commands are generally run from the project directory (the same 
one that contains your settings.py file) and they may use additional parameters and options.

Data and User administration commands
=====================================

The bulk of the management commands fall into this group and will probably be the most frequently used.

+--------------------------------------+-------------------------------------------------------------+
| command                              | purpose                                                     |
+======================================+=============================================================+
| `add_admin <user_id>`                | Turn user into an administrator                             |
|                                      | `<user_id>` is a numeric user id of the account             |
+--------------------------------------+-------------------------------------------------------------+
| `apply_hinted_tags                   | Apply tags to all questions in batch given the list of tags |
| --tag-names <file>`                  | provided with a file. The file must contain tags -          |
|                                      | one per line. If many tags match - only the most frequent   |
|                                      | will be selected.                                           |
+--------------------------------------+-------------------------------------------------------------+
| `create_tag_synonyms --from          | Creates tag synonym record from one name to another,        |
| <from_name> --to <to_name>           | creates the tag named as given with the value of `--to`     |
| --user-id <user_id>`                 | if not existing, and the tag creator will be user with id   |
|                                      | equal to the value of `--user-id` parameter.                |
+--------------------------------------+-------------------------------------------------------------+
| `remove_admin <user_id>`             | Remove admin status from a user account - the opposite of   |
|                                      | the `add_admin` command                                     |
+--------------------------------------+-------------------------------------------------------------+
| `askbot_add_user --user-name         | Create a user account. If password is not given, an         |
| --email [--password]`                | unusable password will be set.                              |
|                                      | The command does not create associations with               |
|                                      | any of the external login providers.                        |
+--------------------------------------+-------------------------------------------------------------+
| `askbot_add_users_to_default_groups` | Adds all users to groups "everyone" and personal            |
+--------------------------------------+-------------------------------------------------------------+
| `askbot_clear_moderation_queue`      | Clear all items from the moderation queue                   |
+--------------------------------------+-------------------------------------------------------------+
| `askbot_award_badges`                | Awards badges to users (only some badges are supported)     |
+--------------------------------------+-------------------------------------------------------------+
| `askbot_expire_badges`               | Expire badges (only some badges are supported)              |
+--------------------------------------+-------------------------------------------------------------+
| `askbot_recount_badges`              | Fixes badge award counts, use when disabling/enabling badges|
+--------------------------------------+-------------------------------------------------------------+
| `merge_users <from_id>               | Merges user accounts and all related data from one user     |
| <to_id>`                             | to another, the "from user" account is deleted.             |
+--------------------------------------+-------------------------------------------------------------+
| `get_tag_stats [-u|-t] [-e]`         | Print tag subscription statistics, per tag (option -t)      |
|                                      | or per user (option -u), if option -e is given, empty       |
|                                      | records will be shown too (longer versions of the options   |
|                                      | are: --per-tag-subscription-counts for -t,                  |
|                                      | --per-user-tag-subscription-counts for -u, and --print-empty|
|                                      | for -e).                                                    |
+--------------------------------------+-------------------------------------------------------------+
| `rename_tags --from <from_tags>      | Rename, merge or split tags. User ID is the id of the user  |
| --to <to_tags> --user-id             | who will be assigned as the performer of the retag action.  |
| <user_id>`                           | If more than is in the `--from` or the `--to` parameters    |
|                                      | then that parameter quoted, e.g. `--to "tag1 tag2".         |
|                                      | If user id is not given, the administrator with the smallest|
|                                      | id number will be automatically assigned.                   |
+--------------------------------------+-------------------------------------------------------------+
| `rename_tags_id --from               | This command is the same as `rename_tags`, but takes the tag|
| <from_tag_ids> --to                  | id's as arguments.                                          |
| <to_tag_ids> --user_id               |                                                             |
| <user_id>`                           |                                                             |
+--------------------------------------+-------------------------------------------------------------+
| `delete_unused_tags`                 | Permanently deletes tags that do not appear in any questions|
|                                      | , including the questions that are themselves               |
|                                      | marked as deleted.                                          |
+--------------------------------------+-------------------------------------------------------------+
| `update_avatar_data`                 | Set values of avatar types for all users;                   |
|                                      | this command may take up to 2s per user, because it makes   |
|                                      | up to one http request per user to gravatar.com.            |
|                                      | This data is used to display preferentially real faces      |
|                                      | on the main page.                                           |
+--------------------------------------+-------------------------------------------------------------+
| `askbot_rebuild_avatars`             | Rebuilds avatar urls and creates avatar thumbnails          |
+--------------------------------------+-------------------------------------------------------------+
| `build_thread_summary_cache`         | Rebuilds cache for the question summary snippet.            |
+--------------------------------------+-------------------------------------------------------------+
| `build_livesettings_cache`           | Rebuilds cache for the live settings.                       |
+--------------------------------------+-------------------------------------------------------------+
| `delete_contextless_...`             | `delete_contextless_badge_award_activities`                 |
|                                      | Deletes Activity objects of type badge award where the      |
|                                      | related context object is lost.                             |
+--------------------------------------+-------------------------------------------------------------+
| `delete_contextless_activities`      | Same as above, but works in a broader sense - when the      |
|                                      | related context object does not exist, but the generic      |
|                                      | foreign key to that object is still present.                |
+--------------------------------------+-------------------------------------------------------------+

.. _data-import-commands:

Data import commands
====================

These commands import or add data to the Askbot forum.

+---------------------------------+-------------------------------------------------------------+
| command                         | purpose                                                     |
+=================================+=============================================================+
| `load_stackexchange <file.zip>` | Load SackExchange dump into Askbot. It is best to run this  |
|                                 | command on empty database. Also - before running, make sure |
|                                 | that `askbot.importers.stackexchange` is in the list of     |
|                                 | installed apps within your settings.py file (it might also  |
|                                 | be necessary to run `syncdb` command to initiate the        |
|                                 | SE importer tables).                                        |
+---------------------------------+-------------------------------------------------------------+
| `askbot_add_xml_content         | Add xml Askbot data dumped with the Django command          |
|  <file.xml>`                    | `dumpdata`                                                  |
+---------------------------------+-------------------------------------------------------------+
| `askbot_add_osqa_content        | Add xml OSQA data dumped with the Django command            |
|  <file.xml>`                    | `export_osqa`                                               |
+---------------------------------+-------------------------------------------------------------+
| `askbot_import_jive <file.xml>  | Import xml Jive data                                        |
+---------------------------------+-------------------------------------------------------------+

.. _email-related-commands:

Email-related commands
======================

These commands deal with the periodic tasks related to sending and receiving email by askbot.
A UNIX program called `cron` can run these commands at the specified times
(please look up futher information about `cron` elsewhere).

Any configurable options, related to these commands are accessible via "Email" section of the
:ref:`live settings <live-settings>`.

+-------------------------------------+-------------------------------------------------------------+
| command                             | purpose                                                     |
+=====================================+=============================================================+
| `send_email_alerts`                 | Dispatches email alerts to the users according to           |
|                                     | their subscription settings. This command does not          |
|                                     | send instant" alerts because those are sent automatically   |
|                                     | and do not require a separate command.                      |
|                                     | The most frequent alert setting that can be served by this  |
|                                     | command is "daily", therefore running `send_email_alerts`   |
|                                     | more than twice a day is not necessary.                     |
+-------------------------------------+-------------------------------------------------------------+
| `send_unanswered_question_reminders`| Sends periodic reminders about unanswered questions.        |
|                                     | This command may be disabled from the "email" section       |
|                                     | of :ref:`live settings <live-settings>`, as well as         |
|                                     | an initial wait period and the recurrence delay may be set. |
+-------------------------------------+-------------------------------------------------------------+
| `send_accept_answer_reminders`      | Sends periodic reminders about accepting best answers.      |
|                                     | This command may be disabled from the "email" section       |
|                                     | of the live settings, as well as the appropriate delay      |
|                                     | parameters may be set.                                      |
+-------------------------------------+-------------------------------------------------------------+
| `askbot_send_moderation_alerts`     | Sends alerts to moderators when there are items on the      |
|                                     | queue.                                                      |
+-------------------------------------+-------------------------------------------------------------+

Data repair commands
====================

Under certain circumstances (especially when using MySQL database with MyISAM 
storage engine or when venturing to adapt the software to your needs) some 
records in the database tables may become internally inconsistent. 
The commands from this section will help fix those issues.

.. note::

 Data inconsistency in the Askbot project is considered as a critical error and as a matter of 
 the project policy is addressed on the day of reporting. If you discover such issue - please
 report it at the forum or by email at `admin@askbot.org`

+--------------------------------+-------------------------------------------------------------+
| command                        | purpose                                                     |
+================================+=============================================================+
| `add_missing_subscriptions`    | adds default values of email subscription settings to users |
|                                | that lack them                                              |
+--------------------------------+-------------------------------------------------------------+
| `fix_answer_counts`            | recalculates answer counts for all questions                |
+--------------------------------+-------------------------------------------------------------+
| `fix_inbox_counts`             | recalculates response counts in the user inboxes            |
+--------------------------------+-------------------------------------------------------------+
| `fix_revisionless_posts`       | adds a revision record to posts that lack them              |
+--------------------------------+-------------------------------------------------------------+
| `fix_question_tags`            | takes tag names from the record on the question table       |
|                                | and stores them in the tag table. This defect may show when |
|                                | the server process is interrupted after the question was    |
|                                | saved, but tags were not updated, and the symptom is that   |
|                                | the question cannot be found via the tag search.            |
+--------------------------------+-------------------------------------------------------------+

The above commands are safe to run at any time, also they do not require 
additional parameters. In the future all these will be replaced with just one simple command.

Developer commands
==================

Besides the commands designed to help run the forum, there are several aiming to help
the developers of the Askbot project:

+--------------------------------+-------------------------------------------------------------+
| command                        | purpose                                                     |
+================================+=============================================================+
| `make_docs`                    | Rebuild HTML documentation for the project                  |
+--------------------------------+-------------------------------------------------------------+
| `jinja2_makemessages`          | Extract translatable strings into the `.po` files. Works    |
|                                | exactly the same way as the django `makemessages` command   |
|                                | but extracts strings from Jinja2 templates that are used    |
|                                | by the Askbot project. **Note:** the `jinja2_makemessages`  |
|                                | must be run from the `askbot` app directory, unlike all the |
|                                | remaining commands that are expected to be run from the     |
|                                | site root directory.                                        |
+--------------------------------+-------------------------------------------------------------+
| `askbot_add_test_content`      | Creates content with dummy data for testing                 |
+--------------------------------+-------------------------------------------------------------+
