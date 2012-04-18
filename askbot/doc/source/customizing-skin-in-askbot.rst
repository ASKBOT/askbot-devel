=====================
Skin system in Askbot
=====================

This document aims to help web designers customize skin for their askbot instances.

Askbot has own skinning system, where current skin can be switched on the fly
in :ref:`live settings <live-settings>`, section "Skin and User Interface Settings".
Currently, there is only one skin available, called "default".

All (with minor exceptions) templates are written with Jinja2 templating engine,
very similar to Django, but with advantages
of better performance and flexibility of coding.

What are skins made of
======================

Skin is a directory either within ``askbot/skins``
or in a directory, pointed to by ``ASKBOT_EXTRA_SKINS_DIR``
parameter of your ``settings.py`` file.

Skin name is the same as the name of its directory,
here is an example of a skin directory structure::

    myskin/
      templates/        #all the template files
      media/            #all the media files
         style/         #css files
         images/        #images
         js/            #javascript files

Some template names and their locations are hardcoded in the
python code of askbot. In addition, there are templates that are
included

A skin consists of HTML templates, css and javascript
and all of these resources are looked up first within currently active skin, 
then in "default".

Names "default" and "common" are reserved and should not be used to 
name custom skins.

Current state of skin system
============================

Default skin is still somewhat in flux.
In addition to refactorings of HTML,
skins may receive additional template context variables.

A caveat is that some names of the element selectors might still change so the customization may require some maintenance upon upgrades.


Possible approaches to customize skins
======================================

There are several methods at your disposal,
would you like to customize askbot's appearance.

.. deprecated:: 0.7.21
    Whenever you change any media files on disk, it will be necessary
    to increment "skin media revision number" in the 
    skin settings and restart the app,
    so that the change goes past the browser caches.
    This requirement will be removed in the future.

Customization via ``settings`` user interface
---------------------------------------------
Some customizations can be done via the :ref:`live settings <live-settings>`,
section "Skin and User Interface settings":

* change site logo
* change favicon
* change password login button, if you use the builtin authentication system
* select current skin
* add custom contents to the HTML <HEAD>
* disable or customize the page footer
* add custom css
* add custom javascript

.. note::
   these settings are stored in the database, therefore
   remember to back it up. Also, if you change these settings
   it is not necessary to increment the skin revision number.

Customization via editing ``style/extra.css``
---------------------------------------------
In this method you will not need to edit any askbot's files.
The ``extra.css`` file is not distributed with askbot, but can be
added by the site administrators wishing to add their own
css rules to those shipped with askbot.

You can create a new skin in one of the directories reserved for the skins,
then place all of your custom ``css`` rules
into a file ``style/extra.css`` within the skin directory or just add
``extra.css`` to the default skin.

If necessary, add your custom images to ``images/`` within the same skin directory.

Deeper customization by editing default skin
--------------------------------------------
Since the default skin still will change (a major redesign is expected),
the best method for deeper customization
is via use git revision control on a clone of the askbot
master repository. It does require some knowledge of git system.

If you plan to do this, firstly, install askbot from the repository.
In addition, it will help if your copy of askbot code is installed
in the django project directory (use ``python setup.py develop`` method
to install askbot in the first place).

Then edit anything in directory ``askbot/skins/default``
and commit to your own repository.

If the askbot app is installed in the `site-packages` or `dist-packages`
of your sitewide python system, or your virtual environment,
then it is not very convinient to tweak the skin,
as the file path may be long and files may be writable only
by from the root account.

**IMPORTANT:** Do not edit file style.css manually, instead edit the
source style.less, written in the `lesscss <http://lesscss.org>`_ format.
See also: :ref:`customizing-style-css-file-in-askbot`.

Create a custom skin in a new directory
---------------------------------------
This is technically possible, but not advisable
because a redesign of default skin is pending.
After the redesign your custom skins may be difficult 
to update.

If you still wish to follow this option,
name all directories and files the same way as
in the "default" skin, as some template file names are
hard-coded in the askbot's python code.

Add setting ``ASKBOT_EXTRA_SKINS_DIR`` to your ``settings.py`` file
and set its value to the directory with your additional skins.

For example::

    ASKBOT_EXTRA_SKINS_DIR = '/home/myname/my_askbot_themes'

And your directory structure might be::

    /home/myname/my_askbot_themes/
                          /my_theme
                                /templates
                                /media

If you are planning to seriously recode the skin -
it will be worthwhile learning the ``git`` system
and just follow the recipe described in the previous section -
direct editing of the "default" skin.
Git makes this task quite simple and manageable.

Skin templates
==============

The first template to look at is `askbot/skins/default/templates/base.html`, it is quite simple and you can substantially change the appearance by modifying that template in the combination with adding some custom css.

More detailed description of templates will follow.

Page classes
============

Some pages in askbot have classes assigned to the HTML ``<body>`` element,
to facilitate styling.
Eventually all more pages will have dedicated class names.
These are not set in stone yet.

+----------------------------+------------------------+
| page url                   | class name             |
+============================+========================+
| /questions/                | main-page              |
+----------------------------+------------------------+
| /questions/ask/            | ask-page               |
+----------------------------+------------------------+
| /tags                      | tags-page              |
+----------------------------+------------------------+
| /question/<id>/<slug>      | question-page          |
+----------------------------+------------------------+
| /questions/<id>/revisions  | revisions-page         |
+----------------------------+------------------------+
| /questions/<id>/edit       | question-edit-page     |
+----------------------------+------------------------+
| /answers/<id>/revisions    | revisions-page         |
+----------------------------+------------------------+
| /users/                    | users-page             |
+----------------------------+------------------------+
| /users/<id>/slug           | user-profile-page      |
+----------------------------+------------------------+
| /users/<id>/edit (bug!)    | user-profile-edit-page |
+----------------------------+------------------------+
| /account/signin/           | openid-signin          |
+----------------------------+------------------------+
| /avatar/change/            | avatar-page            |
+----------------------------+------------------------+
| /about/                    | meta                   |
| /badges/                   |                        |
| /badges/<id>/              |                        |
| /account/logout/           |                        |
| /faq/                      |                        |
| /feedback/                 |                        |
+----------------------------+------------------------+

Template Distrubution.
======================

Layouts
-------

The general template layout is controlled by a few files described below:

+------------------------------------+------------------------------------------------------+
| Template File                      | Description                                          |
+====================================+======================================================+
| base.html                          | This is the base template, a container to call all   |
|                                    | the template files required.                         |
+------------------------------------+------------------------------------------------------+
| one_column_body.html               | This is a base layout for one column style pages.    |
+------------------------------------+------------------------------------------------------+
| two_column_body.html               | This is a base layout for two column style pages.    |
+------------------------------------+------------------------------------------------------+
| widgets/answer_edit_tips.html      | Contains text displayed as "Answer Edit Tips" in the |
|                                    | answer edit page.                                    |
+------------------------------------+------------------------------------------------------+
| widgets/ask_form.html              | Contains the form to ask a question.                 |
+------------------------------------+------------------------------------------------------+
| widgets/bottom_scripts.html        | Contains javascript calls and some javascript        |
|                                    | functions needed for askbot this is included at the  |
|                                    | bottom of every page.                                |
+------------------------------------+------------------------------------------------------+
| widgets/editor_data.html           | Contains data necessary for the post editor this is  |
|                                    | included in block endjs.                             |
+------------------------------------+------------------------------------------------------+
| widgets/footer.html                | Contains the html displayed on the footer.           |
+------------------------------------+------------------------------------------------------+
| widgets/header.html                | Contains the header section of the web. Normaly      |
|                                    | includes the site logo and navitation tools.         |
+------------------------------------+------------------------------------------------------+
| widgets/mandatory_tags_js.html     | Javascript functions for mandatory tags.             |
+------------------------------------+------------------------------------------------------+
| widgets/paginator.html             | Renders the paginator in the main page.              |
+------------------------------------+------------------------------------------------------+
| widgets/question_edit_tips.html    | Contains text displayed as "Question Edit Tips" in   |
|                                    | the question edit page.                              |
+------------------------------------+------------------------------------------------------+
| widgets/secondary_header.html      | Containter for the search bar section.               |
+------------------------------------+------------------------------------------------------+
| widgets/system_messages.html       | Containter for notification messages in the top of   |
|                                    | the page.                                            |
+------------------------------------+------------------------------------------------------+
| widgets/user_navigation.html       | User links to login/logout.                          |
+------------------------------------+------------------------------------------------------+

Widgets
-------

Widgets are pieces of html code separated to be easily modified, they are located in the 
widgets folder and are called from several places in the templates.

+----------------------------+------------------------------+--------------------------------+
| Widget name                | Used in                      | Description                    |
+============================+==============================+================================+
| ask_button.html            | widgets/secondary_header.html | Just the "ask a question"      | 
|                            |                              | button                         |
+----------------------------+------------------------------+--------------------------------+
| answer_controls.html       | question.html                | Answer operation links, edit   | 
|                            |                              | report as spam and more.       |
+----------------------------+------------------------------+--------------------------------+
| contributors.html          | main_page/sidebar.html       | Widget to display contributors | 
|                            |                              | avatars.                       |
+----------------------------+------------------------------+--------------------------------+
| logo.html                  | widgets/header.html          | Contains the site logo.        | 
+----------------------------+------------------------------+--------------------------------+
| main_menu.html             | widgets/secondary_header.html| Contains the main menu html    | 
+----------------------------+------------------------------+--------------------------------+
| meta_nav.html              | widgets/header.html          | Widget for the me logo.        | 
+----------------------------+------------------------------+--------------------------------+
| question_controls.html     | question.html                | Question operation links, edit | 
|                            |                              | report as spam and more.       |
+----------------------------+------------------------------+--------------------------------+
| question_vote_buttons.html | question.html                | Vote buttons used in question  | 
+----------------------------+------------------------------+--------------------------------+
| related_tags.html          | main_page/sidebar.html       | Question operation links, edit | 
|                            |                              | report as spam and more.       |
+----------------------------+------------------------------+--------------------------------+
| search_bar.html            | widgets/secondary_header.html| Contains the search bar.       | 
+----------------------------+------------------------------+--------------------------------+
| share_buttons.html         | question.html                | Widget to show the social      | 
|                            |                              | sharing buttons.               |
+----------------------------+------------------------------+--------------------------------+
| tag_selector.html          | main_page/sidebar.html       | Contains the tag selector for  | 
|                            |                              | search.                        |
+----------------------------+------------------------------+--------------------------------+
| user_navigation.html       | widgets/header.html          | User navigation links like     | 
|                            |                              | login, logout.                 |
+----------------------------+------------------------------+--------------------------------+

Template per URL
----------------

According to the URL some template files are called, the detail on 
which file is called is in the following table.

+----------------------------+-----------------------------+--------------------------------+
| Page url                   | Template file               | Macros used                    |
+============================+=============================+================================+
| /questions/                | main_page.html              |                                |
+----------------------------+-----------------------------+--------------------------------+
| /questions/ask/            | ask.html                    |                                |
+----------------------------+-----------------------------+--------------------------------+
| /tags                      | tags.html                   | tag_widget, paginator,         | 
|                            |                             | tag_cloud                      |
+----------------------------+-----------------------------+--------------------------------+
| /question/<id>/<slug>      | question.html               | tag_widget, edit_post          |
|                            |                             | checkbox_in_div, share         |
+----------------------------+-----------------------------+--------------------------------+
| /questions/<id>/revisions  | revisions.html              | post_contributor_info          |
+----------------------------+-----------------------------+--------------------------------+
| /questions/<id>/edit       | question-edit.html          | tag_autocomplete_js,           |
|                            |                             | checkbox_in_div,               |
|                            |                             | edit_post                      |
+----------------------------+-----------------------------+--------------------------------+
| /answers/<id>/revisions    | revisions.html              | post_contributor_info          |
+----------------------------+-----------------------------+--------------------------------+
| /users/                    | users.html                  | users_list, paginator          |
+----------------------------+-----------------------------+--------------------------------+
| /users/<id>/slug           | user_profile/user.html      |                                |
+----------------------------+-----------------------------+--------------------------------+
| /users/<id>/edit (bug!)    | user_profile/user_edit.html | gravatar                       |
+----------------------------+-----------------------------+--------------------------------+
| /account/signin/           | authopenid/signin.html      | provider_buttons               |
|                            |                             | (from authopenid/macros)       |
+----------------------------+-----------------------------+--------------------------------+
| /avatar/change/            | avatar/change.html          | gravatar                       |
+----------------------------+-----------------------------+--------------------------------+
| /about/                    | about.html                  |                                |
+----------------------------+-----------------------------+--------------------------------+
| /badges/                   | badges.html                 |                                |
+----------------------------+-----------------------------+--------------------------------+
| /badges/<id>/              | badge.html                  | user_score_and_badge_summary   |
+----------------------------+-----------------------------+--------------------------------+
| /account/logout/           | authopenid/logout.html      |                                |
+----------------------------+-----------------------------+--------------------------------+
| /faq/                      | faq.html                    |                                |
+----------------------------+-----------------------------+--------------------------------+
| /feedback/                 | feedback.html               |                                |
+----------------------------+-----------------------------+--------------------------------+
