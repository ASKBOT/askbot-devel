Changes in Askbot
=================

0.7.34 (Current Version)
------------------------
* Returned support of Django 1.2

0.7.33
------
* Made on log in redirect to the forum index page by default
  and to the question page, if user was reading the question
  it is still possible to override the ``next`` url parameter
  or just rely on django's ``LOGIN_REDIRECT_URL`` (Evgeny)
* Implemented retraction of offensive flags (Dejan Noveski)
* Made automatic dependency checking more complete (Evgeny)

0.7.32
------
* Bugfixes in English locale (Evgeny)

0.7.31 
------
* Added ``askbot_create_test_fixture`` management command (Dejan Noveski)
* Integrated new test fixture into the page load test cases (Dejan Noveski)
* Added an embeddable widget for the questions list matching tags (Daniel Mican, Evgeny Fadeev, Dejan Noveski)

0.7.30
------
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

0.7.27 - 0.7.29
---------------
For these versions we did not keep consistent record of features.

0.7.26
------
* Added settings for email subscription defaults (Adolfo)
* Resolved `bug #102<http://bugs.askbot.org/issues/102>`_ - duplicate notifications on posts with mentions (Evegeny)
* Added color-animated transitions when urls with hash tags are visited (Adolfo)
* Repository tags will be `automatically added <http://askbot.org/en/question/345/can-git-tags-be-created-for-each-of-the-releases>`_ to new releases (Evgeny, suggsted by ajmirsky)

0.7.25
------
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
