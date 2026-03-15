.. _analytics:

=========
Analytics
=========

.. note::
   Analytics is a new feature — your feedback is much appreciated!
   Please share your thoughts and suggestions via the usual channels.

Askbot includes a built-in analytics system that tracks user activity
on the forum. It records events such as questions asked, answers posted,
votes cast, content viewed, and time spent on site. The data is
aggregated into hourly and daily summaries per user and per group.

Analytics pages are accessible only to administrators and moderators,
at the URL path ``/analytics/``.

Overview
========

The analytics system has three layers:

1. **Event collection** -- a middleware creates sessions for
   authenticated users and Django signals record events as they happen.

2. **Summarization** -- a management command compiles raw events into
   hourly and daily summaries, per user and per group.

3. **Reporting** -- two web views present the data: the *Users* view
   shows aggregated statistics by segment/group/user, and the
   *Activity* view shows an event log with filtering.

Tracked events
--------------

The following event types are recorded:

+----------------------------+---------------------------------------------+
| Event type                 | Trigger                                     |
+============================+=============================================+
| User registered            | User completes registration                 |
+----------------------------+---------------------------------------------+
| Logged in                  | User logs in                                |
+----------------------------+---------------------------------------------+
| Logged out                 | User logs out                               |
+----------------------------+---------------------------------------------+
| Question viewed            | Authenticated user opens a question page    |
+----------------------------+---------------------------------------------+
| Answer viewed              | Authenticated user views an answer          |
+----------------------------+---------------------------------------------+
| Upvoted                    | User upvotes a post                         |
+----------------------------+---------------------------------------------+
| Downvoted                  | User downvotes a post                       |
+----------------------------+---------------------------------------------+
| Vote canceled              | User cancels a vote                         |
+----------------------------+---------------------------------------------+
| Question asked             | User posts a new question                   |
+----------------------------+---------------------------------------------+
| Answer posted              | User posts a new answer                     |
+----------------------------+---------------------------------------------+
| Question commented         | User comments on a question                 |
+----------------------------+---------------------------------------------+
| Answer commented           | User comments on an answer                  |
+----------------------------+---------------------------------------------+
| Question retagged          | Tags on a question are changed              |
+----------------------------+---------------------------------------------+

Sessions and time on site
-------------------------

The ``AnalyticsSessionMiddleware`` creates or updates a session record
for every authenticated request. A session expires after a configurable
inactivity timeout (default 30 minutes). Time on site is calculated
from session start to last activity within each hourly window.


Configuration
=============

Groups must have the ``used_for_analytics`` flag set to ``True`` to
participate in analytics — that is, to appear in filtering,
summarization, and segmentation. By default this flag is ``False``,
so groups are invisible to the analytics system unless explicitly
enabled. You can set the flag manually via Django admin, or it is
set automatically by the ``askbot_create_per_email_domain_groups``
management command.

Analytics settings are defined in ``settings.py`` using the
``ASKBOT_`` prefix. They are static settings (not changeable via the
admin UI at runtime).

``ASKBOT_ANALYTICS_SESSION_TIMEOUT_MINUTES``
    Number of minutes of inactivity after which a session is considered
    expired. Default: ``30``.

``ASKBOT_ANALYTICS_EMAIL_DOMAIN_ORGANIZATIONS_ENABLED``
    When ``True``, enables grouping users by email domain. The
    management command ``askbot_create_per_email_domain_groups`` will
    create one group per unique email domain found in the user table
    and assign users to the matching group. These groups are marked
    with ``used_for_analytics=True``. Default: ``False``.

``ASKBOT_ANALYTICS_NAMED_SEGMENTS``
    A list of dictionaries defining named user segments. Each dictionary
    must have the keys: ``name``, ``slug``, ``description``, and
    ``group_ids`` (a list of Askbot Group ids). Named segments appear
    as top-level rows in the Users analytics view. Default: ``[]``.

    Example::

        ASKBOT_ANALYTICS_NAMED_SEGMENTS = [
            {
                'name': 'Engineering',
                'slug': 'engineering',
                'description': 'Engineering team members',
                'group_ids': [10, 11, 12],
            },
        ]

``ASKBOT_ANALYTICS_DEFAULT_SEGMENT``
    A dictionary with keys ``name``, ``slug``, and ``description``.
    This segment captures all users who do not belong to any of the
    named segments, for example - your customers.
    It appears after the named segments in the Users
    view. Default: ``{}`` (empty -- must be configured if segments are
    used).

    Example::

        ASKBOT_ANALYTICS_DEFAULT_SEGMENT = {
            'name': 'Customers',
            'slug': 'customers',
            'description': 'Our Customers',
        }



Middleware setup
================

The analytics session middleware must be included in
``MIDDLEWARE`` in your ``settings.py``::

    MIDDLEWARE = [
        ...
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'askbot.middleware.analytics_session.AnalyticsSessionMiddleware',
        ...
    ]

This middleware is included by default when a new site is created with
``askbot-setup``.


Management commands
===================

``askbot_compile_analytics``
    Compiles raw events into summary tables. This command should be run
    periodically (e.g. hourly via cron). It performs these steps:

    1. Summarizes unsummarized events into hourly per-user summaries.
    2. Extracts time-on-site from sessions into hourly summaries.
    3. Rolls up hourly user summaries into daily user summaries and
       hourly group summaries.
    4. Rolls up hourly group summaries into daily group summaries.
    5. Finalizes daily group summaries with user counts.

    Only completed hours and completed days are summarized, so the
    command is safe to run at any time.

    Options:

    ``--silent``
        Suppress progress output.

    Example cron entry (run every hour)::

        0 * * * * cd /path/to/project && python manage.py askbot_compile_analytics --silent

``askbot_create_per_email_domain_groups``
    Creates one group per unique email domain found among users and
    assigns each user to the corresponding group. Groups are marked
    with ``used_for_analytics=True``. Requires
    ``ASKBOT_ANALYTICS_EMAIL_DOMAIN_ORGANIZATIONS_ENABLED = True``.

    Options:

    ``--silent``
        Suppress progress output.

``askbot_add_test_analytics_content``
    Populates the database with synthetic analytics sessions and events
    based on existing user activity. Useful for development and testing.


Web interface
=============

The analytics pages are at ``/analytics/`` and require administrator
or moderator privileges.

Users view
----------

URL pattern: ``/analytics/users/<users_segment>/<dates>/``

Shows aggregated statistics (questions, answers, votes, views, time on
site, user counts) broken down by segment. Drill-down navigation:

1. **Per-segment stats** -- shows all named segments, the default
   segment, and totals.
2. **Per-group in segment** -- within the default segment, shows stats
   per group (organization).
3. **Per-user in group** -- shows individual user stats within a
   group or named segment.

Activity view
-------------

URL pattern:
``/analytics/activity/<activity_segment>/<content_segment>/<users_segment>/<dates>/``

Shows a paginated event log with filters:

- **Activity segment** -- filter by event type (e.g. ``question-posted``,
  ``content-voted``, ``all-activity``).
- **Content segment** -- filter by thread or post
  (e.g. ``thread:123``, ``post:456``, ``all-content``).
- **Users segment** -- filter by user, group, named segment, or
  ``all-users``.

Date ranges
-----------

Both views accept the following date range values:

- ``last-7-days``
- ``last-30-days``
- ``this-month``
- ``last-month``
- ``last-3-months``
- ``last-6-months``
- ``this-year``
- ``last-year``
- ``all-time``


Data model
==========

The analytics data is stored in the following database tables
(Django models in ``askbot.models.analytics``):

``Session``
    Tracks per-user browsing sessions with IP, user agent, and
    timestamps. Sessions expire based on the configured timeout.

``Event``
    Individual analytics events, each linked to a session, with an
    event type, timestamp, and a generic foreign key to the related
    object (user, post, or thread).

``HourlyUserSummary``
    Aggregated counts per user per hour.

``HourlyGroupSummary``
    Aggregated counts per group per hour, including user counts.

``DailyUserSummary``
    Aggregated counts per user per day.

``DailyGroupSummary``
    Aggregated counts per group per day, including user counts.

Summary fields tracked: ``num_questions``, ``num_answers``,
``num_upvotes``, ``num_downvotes``, ``question_views``,
``time_on_site``. Group summaries additionally track ``num_users``
and ``num_users_added``.


Google Analytics (external)
===========================

Askbot also supports embedding a Google Analytics tracking snippet.
This is configured separately via the admin UI under
**External Services** > **Keys for external services** >
**Google Analytics key**. Set the key to your Google Analytics
tracking ID and the snippet will be included in all pages.
