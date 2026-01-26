Changes in Askbot
=================

0.12.3 (Jan 26, 2026)
---------------------
* Supports Python 3.12
* Admin Tags: tags can be designated as "admin tags" with special styling and management,
  setting ``ASKBOT_USER_CAN_MANAGE_ADMIN_TAGS_FUNCTION`` controls access
* OIDC authentication: added setting ``OIDC_AUTHORIZATION_FUNCTION`` for custom authorization,
  OIDC now uses access token instead of id_token
* Added Django signals ``best_answer_accepted`` and ``best_answer_unaccepted``
* Added setting ``WHO_CAN_ANONYMIZE_ACCOUNTS``
* Added setting ``ASKBOT_FEDERATED_LOGIN_EMAIL_EDITABLE``
* Custom user profile tab: added ``USER_IS_AUTHORIZED_FUNC`` option
* Added ``email_is_confidential`` field to UserProfile model
* HTML emails now use premailer for inline CSS styling
* Added ``HeadRequestMiddleware`` to handle HEAD requests
* Retired ``ez_setup.py``
* Pre-commit configuration and GitHub Actions tests added
* Admin site: allows filtering user profiles by status and email_is_confidential
* Non-admins cannot terminate admin or moderator accounts
* Publish/unpublish button shown for group private posts when user has permission
* Security fix: authorization bypass in avatar views where URL string parameters
  were compared directly to integer user IDs
* Bug fix: undeleting a question was not working properly
* Bug fix: unsubscribe URL no longer breaks if user not found with given email
* Bug fix: privacy setting is maintained when editing a post via ajax
* Bug fix: delete tag when removing admin tag
* XSS fix: adds escape to closed_question_info in templates
* Bumps django-livesettings3 to 1.6.3

0.12.2 (Jul 29, 2023)
---------------------
* improves installation process, supports Python 3.11
* Allows customization of the question close reasons in the settings

0.12.1 (Jul 21, 2023)
---------------------
* bug fixes with library versions

0.12.0 (Jul 19, 2023)
---------------------
* Added support for Django 4.2
* Removed all TinyMCE code
* Added ASKBOT_SPAM_CHECKER_TIMEOUT_SECONDS parameter to settings.py,
  defaults to 1s
* Made moderation queue actions snappier by using optimistic UI update
* fixes creation of duplicate moderation queue records when
  link and image moderation is enabled.
* all uses of is_spam function is guarded by the check for
  askbot.conf.SPAM_FILTER_ENABLED setting

0.11.8 (Jul 24, 2023)
---------------------
* Allows customization of the question close reasons in the settings,
  this feature is not merged into v0.12.x until 0.12.2
* Added ASKBOT_SPAM_CHECKER_TIMEOUT_SECONDS parameter to settings.py,
  defaults to 1s
* Made moderation queue actions snappier by using optimistic UI update
* fixes creation of duplicate moderation queue records when
  link and image moderation is enabled.
* all uses of is_spam function is guarded by the check for
  askbot.conf.SPAM_FILTER_ENABLED setting

0.11.7 (May 15, 2023)
---------------------
* PR #928 - upgrades django-avatar (Bruno Guimarães, @brunobastosg)

0.11.6 (May 8, 2023)
--------------------
* added setting ASKBOT_SPAM_CHECKER_FUNCTION - default is
  `askbot.spam_checker.akismet_spam_checker.is_spam`
* added a second spam checker alternative:
  `askbot.spam_checker.askbot_spam_checker.is_spam`
  which needs settings: `ASKBOT_SPAM_CHECKER_API_KEY`,
  `ASKBOT_SPAM_CHECKER_API_URL`
* added a management command `askbot_get_spam_training_set`
* added fields to Post model: `marked_as_spam`, `marked_as_spam_at`, `marked_as_spam_by`
  these fields are populated when marking user as spammer in the moderation queue
* added signal `askbot.signals.posts_marked_as_spam`

0.11.5 (Apr 12, 2023)
-------------------
* Works with python 3.7-3.10
* Rewrites the base theme.
* New theme is responsive across all reasonable screen sizes
* When groups are enabled - per group permissions
  to post questions/answers/comments are respected
* Adds settings "Allow uploading file attachments in posts"
  and "Allow uploading images in posts"
  to the "Forum data rules" section of the admin settings page
* Adds question close reasons: "question is considered as answered" and
  "closed as inactive"
* Supports OIDC authentication protocol
* Adds blank state for the moderation queue
* Adds management command `askbot_markdownify_content` - converts
  html markup to markdown
* When groups are enabled, per-group permissions added:
  - can upload attachments
  - can upload images
* Bug, PEP8 fixes

0.11.3, 0.11.4 (Apr 7, 2023)
--------------
* Changelog not recorded, see update for 0.11.5

0.11.2 (Jan 21, 2022)
------------------
* Supports Django up to version 3, tested with Python up to 3.7
* Anonymize data and disable accounts
* GDPR compliance (export data, cancel/request to cancel account)
* Updated Facebook login Api to v3.2

0.10.2 (Dec 21, 2016)
---------------------
* Bug fixes for the previous version

0.10.1 (Nov 16, 2016)
---------------------
* Added settings `ASKBOT_ALLOWED_HTML_ELEMENTS` and
  `ASKBOT_ALLOWED_HTML_ATTRIBUTES`
* Allow custom markdown parser via `ASKBOT_MARKDOWN_CLASS` setting
* Applied Akismet check (if enabled) to editing of all content
* Updated Facebook API to v2.2.
* Unsubscribe link feature
* User profile "about" section is per-language (localizable)
* Tag names with diacritic characters are allowed
* Inline editing of questions and answer
* Markdown editor expands automatically
* Added ASKBOT_LANGUAGE_MODE setting, which can be one of
  'single-lang', 'url-lang', 'user-lang'. The 'user-lang'
  option allows users to see posts of several user-selected
  languages in the single listing of questions. The 'url-lang'
  option shows questions in one listing per language.
* Added option to close new account registrations
* Added support of CAS protocol

0.10.0 (Dec 7, 2015)
--------------------
* Supports Django 1.8
* Added management command `askbot_rebuild_avatars`
* Added option to choose gravatar or default avatar for new users
* Message on the feedback page is editable
* Added support for the NoCaptcha recaptcha

NOTE::
  Releases 0.10.x support Django 1.8, 0.9.x - Django 1.7,
  0.7.x support Django 1.5, 0.8.x - 1.6 and to be used
  only to migrate to the higher versions of the Django framework
  from 1.5. See https://pypi.python.org/pypi/askbot/
  to download the latest available version.

0.7.53 (Apr 22, 2015)
---------------------
* Use prompt placeholders on all registration forms
* Disable Google login by default because it is now OAuth2


0.7.52 (Apr 19, 2015)
---------------------
* Added account recovery form to the "complete registration" page
  to help prevent accidental creation of duplicate accounts
* Support migration of Google OpenID accounts to G+
* Added setting to allow comment updates show on the main page
* Improved support of uploadable avatars
* Added authentication via MediaWiki
* Added option to specify `ASKBOT_QUESTION_TITLE_RENDERER` function
* Added option to specify `ASKBOT_HTML_MODERATOR` function
* Allowed reordering badges on the badges page via drag and drop
* Added option to forbid commenting in closed questions
* Added separate optional time limits to edit questions and answers
* Added option to disable comments under questions or answers
* Added management command `askbot_recount_badges`
* Allowed adding custom badges via `ASKBOT_CUSTOM_BADGES` setting
* Allowed enabling and disabling individual badges
* Added "forbidden phrases" for the content moderation
  Posts containing these will be rejected outright, without placement
  on the moderation queue.
* Added minimum reputation to delete own questions with answers
* Added optional checkbox "accept terms of service"
  which being enabled, requires users to read and agree
  with the terms before signing up.
* Added terms of service page
* Allowed reverse ordering of comments

0.7.51 (Dec 15, 2014)
---------------------
* Bug fixes

0.7.50 (Nov 1, 2014)
--------------------
* Added email alert for moderators `askbot_send_moderation_alerts`
* Implemented Google Plus login
* Allowed localized site settings
* Added management command `askbot_clear_moderation_queue`
* Admins and Moderators can merge questions.
* Improved moderation modes: flags, audit, premoderation.
  Watched user status, IP blocking, mass content removal.
* Allow bulk deletion of user content simultaneously with blocking
* Allow custom destination url under the logo
* Option to allow asking without registration (Egil Moeller)
* Implemented Mozilla Persona authentication
* Allowed custom providers of gravatar service (michas2)
* Allowed configurable custom OpenID login button
* Allowed custom list of feedback recipients (Keto)
* Added option to show user's emails to the moderators
* Added Read-Only mode for the site in the "access control" section.
* Added `askbot_add_osqa_content` management command.
* Management command to add data from other Askbot site.
* Allowed simple overrides of livesettings with `ASKBOT_...` prefixed
  variables in the `settings.py` file.

0.7.49 (Sep 19, 2013)
---------------------
* Support for Solr search backend (Adolfo)
* Allowed read-only access user groups (Adolfo)
* Added simple read-only API (Adolfo)
* Added "admin email" to livesettings (Evgeny)
* Improved Zendesk import feature `Kevin Porterfield, Shotgun Software<http://www.shotgunsoftware.com>_`
* Added backend support for the tag synonyms `pcompassion https://github.com/pcompassion`_
* Added management command `apply_hinted_tags` to batch-apply tags from a list (Evgeny)
* Added hovercard on the user's karma display in the header (Evgeny)
* Added option to hide ad blocks from logged in users (Evgeny)
* Applied Askbot templates to the settings control panel (Evgeny)
* Added option to auto-follow questions by the question posters with default "on" (Evgeny)
* Support for Django 1.5
* Auto-tweet option for questions and answers
* Added Chech and Croatian translations
* Disable/enable best answer feature
* Allowed post owners repost answers and comments (this used to be mod-only function).
* Answer editor is "folded" by default. Editor buttons and options show on click.
* Management command `askbot_import_jive` to import data from Jive forums.
* Added possibility to choose editor for comments: plain text, or same as
  editor used for the questions or answers: WMD or TinyMCE.
* Added ajax search to the tags page
* Added a placeholder template for the custom javascript on the question page
* Allowed to disable the big "ask" button.
* Some support for the media compression (Tyler Mandry)
* Allowed to enable and disable question scopes on the main page
* Added full text support for some languages with Postgresql:
  Danish, Dutch, English, Finnish, French, German, Hungarian,
  Italian, Japanese (requires package textsearch_ja), Norwegian,
  Portugese, Romanian, Russian, Spanish, Swedish, Turkish.
* repost answer as a comment under the previous (older) answer
* minor edit option for question and answer, to suppress email alerts
* allowed tags to be created upon marking them as interesting/ignored/subscribed

0.7.48 (Jan 28, 2013)
---------------------
* made "how to ask the question" instructions editable
* added RSS auto-discovery link
* added support for multilingual site (experimental)
* tag subscription manager on the tags page (Adolfo)

0.7.47 (Dec 13, 2012)
---------------------
* Bugfix release

0.7.46 (Dec 12, 2012)
---------------------
* Bugfix release

0.7.45 (Dec 12, 2012)
---------------------
* Feedback sender's email is added to the Reply-To header
  in the feedback form (Evgeny)
* Reimplemented search as drop-down (Evgeny)
* Basic design to work on smartphones (Evgeny)
* Allowed use of alternative form on the user signup page (Evgeny)

0.7.44 (Nov 11, 2012)
---------------------
* Support for django 1.4 (Adolfo)
* Added option to enable/disable rss feeds (Evgeny)
* Added minimum reputation to insert links and hotlinked images (Evgeny)
* Added minimum reputation to suggest links as plain text (Evgeny)
* Added support of Haystack for search (Adolfo)
* Added minimum reputation setting to accept any answer as correct (Evgeny)
* Added "VIP" option to groups - if checked, all posts belong to the group and users of that group in the future will be able to moderate those posts. Moderation features for VIP group are in progress (Evgeny)
* Added setting `NOTIFICATION_DELAY_TIME` to use with enabled celery daemon (Adolfo)
* Added setting `ASKBOT_INTERNAL_IPS` - to allow anonymous access to
  closed sites from dedicated IP addresses (Evgeny)
* Moved default skin from `askbot/skins/default` to simply `askbot` (Evgeny)
* Repost comment as answer (Adolfo)
* Question list widget (Adolfo)
* Ask a question widget (Adolfo)
* Embeddable widget generator (Adolfo)
* Groups are shown in the dropdown menu in the header (Adolfo)
* Added group moderation requests to the moderators inboxes (Evgeny)
* Group joining may be open/closed or moderated (Evgeny)
* Adding "extra options" to the ldap session (Evgeny)
* Tag moderation (Evgeny)
* Editable optional three level category selector for the tags (Evgeny)
* Tag editor adding tags as they are typed (Evgeny)
* Added optional support for unicode slugs (Evgeny)
* Allow switching comment with answer and answer with question comment (Adolfo)
* Allow user names longer than 30 characters (Evgeny)
* Option to disable feedback form for the anonymos users (Evgeny)
* Optional restriction to have confirmed email address to join forum (Evgeny)
* Optional list of allowed email addresses and email domain name for the new users (Evgeny)
* Optional support for unicode slugs (Evgeny)
* Optionally allow limiting one answer per question per person (Evgeny)
* Added management command `build_livesettings_cache` (Adolfo)
* Administrators can post under fictional user accounts without logging out (jtrain, Evgeny)
* Welcome email for the case when replying by email is enabled (Evgeny)
* Detection of email signature based on the response to the welcome email (Evgeny)
* Hide "website" and "about" section of the blocked user profiles
  to help prevent user profile spam (Evgeny)
* Added a function to create a custom user profile tab,
  the feature requires access to the server (Evgeny)
* Added optional top banner to the question page (Evgeny)
* Made "bootstrap mode" default and created instead "large site mode" (Evgeny)
* Added interesting/ignored/subscribed tags to the user profile page (Paul Backhouse, Evgeny)

0.7.43 (May 14, 2012)
---------------------
* User groups (Evgeny)
* Public/Private/Hidden reputation (Evgeny)
* Enabling/disabling the badges system (Evgeny)
* Created a basic post moderation feature (Evgeny)
* Created a way to specify reasons for rejecting posts in a modal dialog (Evgeny)
* A number of bug fixes (Adolfo Fitoria, Jim Tittsler,
  Evgeny Fadeev, Robin Stocker, Radim Řehůřek, Silvio Heuberger)

0.7.41, 0.7.42 (April 21, 2012)
-------------------------------
* Bug fixes

0.7.40 (March 29, 2012)
-----------------------
* New data models!!! (`Tomasz Zieliński <http://pyconsultant.eu>`_)
* Made email recovery link work when askbot is deployed on subdirectory (Evgeny)
* Added tests for the CSRF_COOKIE_DOMAIN setting in the startup_procedures (Evgeny)
* Askbot now respects django's staticfiles app (Radim Řehůřek, Evgeny)
* Fixed the url translation bug (Evgeny)
* Added left sidebar option (Evgeny)
* Added "help" page and links to in the header and the footer (Evgeny)
* Removed url parameters and the hash fragment from uploaded files -
  amazon S3 for some reason adds weird expiration parameters (Evgeny)
* Reduced memory usage in data migrations (Evgeny)
* Added progress bars to slow data migrations (Evgeny)
* Added a management command to build_thread_summary_cache (Evgeny)
* Added a management delete_contextless_badge_award_activities (Evgeny)
* Fixed a file upload issue in FF and IE found by jerry_gzy (Evgeny)
* Added test on maximum length of title working for utf-8 text (Evgeny)
* Added caching and invalidation to the question page (Evgeny)
* Added a management command delete_contextless_activities (Evgeny)
* LDAP login configuration (github user `monkut <https://github.com/monkut>`_)
* Check order of middleware classes (Daniel Mican)
* Added "reply by email" function (`Vasil Vangelovski <http://www.atomidata.com>`_)
* Enabled "ask by email" via Lamson (Evgeny)
* Tags can be optional (Evgeny)
* Fixed dependency of Django up to 1.3.1, because settings must be upgraded
  for Django 1.4 (Evgeny)

0.7.39 (Jan 11, 2012)
---------------------
* restored facebook login after FB changed the procedure (Evgeny)

0.7.38 (Jan 11, 2012)
---------------------
* xss vulnerability fix, issue found by Radim Řehůřek (Evgeny)

0.7.37 (Jan 8, 2012)
--------------------
* added basic slugification treatment to question titles with
  ``ALLOW_UNICODE_SLUGS = True`` (Evgeny)
* added verification of the project directory name to
  make sure it does not contain a `.` (dot) symbol (Evgeny)
* made askbot compatible with django's `CSRFViewMiddleware`
  that may be used for other projects (Evgeny)
* added more rigorous test for the user name to make it slug safe (Evgeny)
* made setting `ASKBOT_FILE_UPLOAD_DIR` work (Radim Řehůřek)
* added minimal length of question title ond body
  text to live settings and allowed body-less questions (Radim Řehůřek, Evgeny)
* allowed disabling use of gravatar site-wide (Rosandra Cuello Suñol)
* when internal login app is disabled - links to login/logout/add-remove-login-methods are gone (Evgeny)
* replaced setting `ASKBOT_FILE_UPLOAD_DIR` with django's `MEDIA_ROOT` (Evgeny)
* replaced setting `ASKBOT_UPLOADED_FILES_URL` with django's `MEDIA_URL` (Evgeny)
* allowed changing file storage backend for file uploads by configuration (Evgeny)
* file uploads to amazon S3 now work with proper configuration (Evgeny)

0.7.36 (Dec 20, 2011)
---------------------
* bugfix and made the logo not used by default

0.7.35 (Dec 15, 2011)
---------------------
* Removal of offensive flags (`Dejan Noveski <http://www.atomidata.com/>`_)
* Fixes in CSS (`Byron Corrales <http://byroncorrales.blogspot.com/>`_)
* Update of Catalan locale (Jordi Bofill)

0.7.34 (Dec 10, 2011)
---------------------
* Returned support of Django 1.2

0.7.33 (Dec 6, 2011)
--------------------
* Made on log in redirect to the forum index page by default
  and to the question page, if user was reading the question
  it is still possible to override the ``next`` url parameter
  or just rely on django's ``LOGIN_REDIRECT_URL`` (Evgeny)
* Implemented retraction of offensive flags (Dejan Noveski)
* Made automatic dependency checking more complete (Evgeny)

0.7.32 (Nov 30, 2011)
---------------------
* Bugfixes in English locale (Evgeny)

0.7.31 (Nov 29, 2011)
---------------------
* Added ``askbot_create_test_fixture`` management command (Dejan Noveski)
* Integrated new test fixture into the page load test cases (Dejan Noveski)
* Added an embeddable widget for the questions list matching tags (Daniel Mican, Evgeny Fadeev, Dejan Noveski)

0.7.30 (Nov 28, 2011)
---------------------
Note: some of these features were added in one of the three previous versions.

* Context-sensitive RSS url (`Dejan Noveski <http://www.atomidata.com/>`_)
* Implemented new version of skin (Byron Corrales)
* Show unused vote count (Tomasz Zielinski)
* Categorized live settings (Evgeny)
* Merge users management command (Daniel Mican)
* Added management command ``send_accept_answer_reminders`` (Evgeny)
* Improved the ``askbot-setup`` script (Adolfo, Evgeny)
* Merge users management command (Daniel Mican)
* Anonymous caching of the question page (Vlad Bokov)
* Fixed sharing button bug, css fixes for new template (Alexander Werner)
* Added ASKBOT_TRANSLATE_URL setting for url localization(Alexander Werner)
* Changed javascript translation model, moved from jqueryi18n to django (Rosandra Cuello Suñol)
* Private forum mode (Vlad Bokov)
* Improved text search query in Postgresql (Alexander Werner)
* Take LANGUAGE_CODE from request (Alexander Werner)
* Added support for LOGIN_REDIRECT_URL to the login app (hjwp, Evgeny)
* Updated Italian localization (Luca Ferroni)
* Added Catalan localization (Jordi Bofill)
* Added management command ``askbot_add_test_content`` (Dejan Noveski)
* Continued work on refactoring the database schema (Tomasz Zielinski)

0.7.27 - 0.7.29 (Nov 8-28, 2011)
--------------------------------
For these versions we did not keep consistent record of features.

0.7.26 (Oct 12, 2011)
---------------------
* Added settings for email subscription defaults (Adolfo)
* Resolved `bug #102<http://bugs.askbot.org/issues/102>`_ - duplicate notifications on posts with mentions (Evegeny)
* Added color-animated transitions when urls with hash tags are visited (Adolfo)
* Repository tags will be `automatically added <http://askbot.org/en/question/345/can-git-tags-be-created-for-each-of-the-releases>`_ to new releases (Evgeny, suggsted by ajmirsky)

0.7.25 (Oct 5 2011)
-------------------
* RSS feed for individual question (Sayan Chowdhury)
* Allow pre-population of tags via ask a questions link (Adolfo)
* Make answering own question one click harder (Adolfo)
* Bootstrap mode (Adolfo, Evgeny)
* Color-animated urls with the hash fragments (Adolfo)

0.7.24
------
* Made it possible to disable the anonymous user greeting alltogether (Raghu Udiyar)
* Added annotations for the meanings of user levels on the "moderation" page. (Jishnu)
* Auto-link patterns - e.g. to bug databases - are configurable from settings. (Arun SAG)

0.7.23
------
* Greeting for anonymuos users can be changed from live settings (Hrishi)
* Greeting for anonymous users is shown only once (Rag Sagar)
* Added support for Akismet spam detection service (Adolfo Fitoria)
* Added noscript message (Arun SAG)
* Support for url shortening with TinyUrl on link sharing (Rtnpro)
* Allowed logging in with password and email in the place of login name (Evgeny)
* Added config settings allowing adjust license information (Evgeny)

0.7.22
------
* Media resource revision is now incremented
  automatically any time when media is updated (Adolfo Fitoria, Evgeny Fadeev)
* First user automatically becomes site administrator (Adolfo Fitoria)
* Avatar displayed on the sidebar can be controlled with livesettings.(Adolfo Fitoria, Evgeny Fadeev)
* Avatar box in the sidebar is ordered with priority for real faces.(Adolfo Fitoria)
* Django's createsuperuser now works with askbot (Adolfo Fitoria)

0.7.21
------
This version was skipped

0.7.20
------
* Added support for login via self-hosted Wordpress site (Adolfo Fitoria)
* Allowed basic markdown in the comments (Adolfo Fitoria)
* Added this changelog (Adolfo Fitoria)
* Added support for threaded emails (Benoit Lavigne)
* A few more Spanish translation strings (Byron Corrales)
* Social sharing support on identi.ca (Rantadeep Debnath)

0.7.19
------
* Changed the Favorite question function for Follow question.
* Fixed issues with page load time.
* Added notify me checkbox to the sidebar.
* Removed MySql dependency from setup.py
* Fixed Facebook login.
* `Fixed "Moderation tab is misaligned" issue reported by methner. <http://askbot.org/en/question/587/moderation-tab-is-misaligned-fixed>`_
* Fixed bug in follow users and changed the follow button design.

0.7.18
------
* `Added multiple capitalization to username mentions(reported by niles) <http://askbot.org/en/question/580/allow-alternate-capitalizations-in-user-links>`_

0.7.17
------
* Adding test for UserNameField.
* Adding test for markup functions.

0.7.16
------
* Admins can add aministrators too.
* Added a postgres driver version check in the start procedures due to a bug in psycopg2 2.4.2.
* New inbox system style (`bug reported by Tomasz P. Szynalski <http://askbot.org/en/question/470/answerscomments-are-listed-twice-in-the-inbox>`_).

0.7.15
------
* Fixed integration with Django 1.1.
* Fixed bugs in setup script.
* Fixed pypi bugs.
