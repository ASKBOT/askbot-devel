# Askbot Architecture

Detailed architecture reference for the Askbot codebase.

## Django App Structure

```
askbot/
├── models/          # Core data models
├── views/           # View controllers (readers.py, writers.py, commands.py, users.py)
├── forms.py         # Form definitions (large, 63KB+)
├── urls.py          # URL routing with translatable patterns
├── conf/            # Livesettings configuration system
├── deps/            # Bundled dependencies
│   ├── django_authopenid/   # Forked authentication system
│   └── group_messaging/      # Group messaging functionality
├── skins/           # Template system
├── utils/           # Utility modules
├── middleware/      # Custom middleware
├── deployment/      # Deployment scripts and validators
└── startup_procedures.py  # Validation on startup
```

## Core Models (askbot/models/)

- **Post** (`post.py`) - Base class for questions/answers/comments
- **Thread/Question** (`question.py`) - Question threads and views
- **User** (`user.py`, `user_profile.py`) - Extended user model with reputation
- **Tag** (`tag.py`) - Tag system with synonyms and categories
- **Badges** (`badges.py`) - Badge award system
- **Repute** (`repute.py`) - Reputation tracking

## Configuration System (Livesettings)

Askbot uses django-livesettings3 for runtime-editable settings stored in the database. Configuration modules in `askbot/conf/` define settings groups:
- `site_settings.py`, `email.py`, `moderation.py`, etc.
- Settings accessed via: `from askbot.conf import settings as askbot_settings`
- Wrapper in: `askbot/conf/settings_wrapper.py`

## Template System

- Uses Jinja2 (not Django templates)
- Custom Jinja2 environment in `askbot/skins/jinja2_environment.py`
- Template backends in `askbot/skins/template_backends.py`
- Skin system allows theme customization

## URL Routing

- Translatable URLs using `pgettext()` when `ASKBOT_TRANSLATE_URL` is enabled
- Configurable base URLs: `ASKBOT_MAIN_PAGE_BASE_URL`, `ASKBOT_QUESTION_PAGE_BASE_URL`
- Complex regex patterns for questions with filters (scope, sort, tags, author, page)

## Authentication

Bundled fork of `django_authopenid` in `askbot/deps/`:
- Supports multiple auth providers (OAuth, OpenID, LDAP, CAS, Okta)
- Custom user model extensions patch Django's `auth_user` table
- **Important**: Migrations automatically add missing columns but won't overwrite existing ones

## Multi-language Support

Three language modes configured via `ASKBOT_LANGUAGE_MODE`:
- `'single-lang'` - Single language site
- `'url-lang'` - Language prefix in URLs
- `'user-lang'` - User-selected language

Check mode: `askbot.is_multilingual()`

## Database Considerations

- PostgreSQL recommended for full-text search and relevance sorting
- Supports MySQL 5.6+ and SQLite
- Database engine check: `askbot.get_database_engine_name()`

## Search System

Multiple search backends in `askbot/search/`:
- `postgresql/` - PostgreSQL full-text search
- `haystack/` - Haystack integration

## Email System

- Complex email alert system in `askbot/mail/`
- Supports instant and delayed alerts with tag filtering
- Email parsing for reply-by-email functionality

## Celery Tasks

Async task processing configured in `askbot/tasks.py`:
- Badge awarding
- Email sending
- Other background operations

## Static Files and Media

- Node.js dependencies in `askbot/media/node_modules/`
- ESLint configuration for JavaScript
- Static files collected via Django's collectstatic

## Code Quality Tools

- **Ruff**: Primary linter (configuration in `pyproject.toml`)
- **Pylint**: Available but currently disabled in pre-commit
- Many rules are TODO for gradual adoption
- Migrations excluded from linting
