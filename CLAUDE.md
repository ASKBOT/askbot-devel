# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Askbot is a Django-based Q&A forum platform similar to StackOverflow, written in Python. It supports Django 4.2 and Python 3.8+, with PostgreSQL as the recommended database for full-text search capabilities.

Current version: 0.12.x (master branch)

## Development Setup

### Initial Installation
```bash
pip install --upgrade pip
pip install setuptools-rust
python -m pip install .
askbot-setup  # Creates a Django project, default directory: askbot_site
cd <root_dir>  # Navigate to project root
python manage.py migrate
python manage.py migrate  # Run twice for askbot and django_authopenid apps
```

### Development Environment
- Test project available at: `testproject/` for development and testing
- Working site example at: `askbot_site/`
- Virtual environment typically in: `env/`

### Pre-commit Hooks
```bash
pre-commit install  # Required before committing
```

Pre-commit runs ruff for linting with `--fix` flag. Configuration in `.pre-commit-config.yaml` and `pyproject.toml`.

## Testing

### Running Tests
```bash
# Using tox (recommended)
tox  # Runs tests for available Python versions

# Environment variables for database configuration
DB_TYPE=postgres
DB_USER=askbot
DB_PASS=askB0T!
DB_HOST=localhost
DB_PORT=5432
DB_NAME=askbotfortox

# Direct Django test runner
cd testproject/
python manage.py test --parallel 8 askbot.tests askbot.deps.django_authopenid.tests

# Coverage report
coverage run --rcfile ../.coveragerc manage.py test --parallel 8 askbot.tests askbot.deps.django_authopenid.tests
coverage html --rcfile ../.coveragerc
```

### Test Configuration
- Tests located in: `askbot/tests/`
- Coverage config: `.coveragerc`
- Tox config: `tox.ini`
- Uses factory_boy for test fixtures

## Management Commands

Askbot includes numerous custom management commands in `askbot/management/commands/`:
- `add_admin.py` - Add admin users
- `askbot_add_test_content.py` - Generate test data
- `askbot_award_badges.py` - Award badges to users
- Many others for data migration, cleanup, and maintenance

Run with: `python manage.py <command_name>`

## Architecture

### Django App Structure
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

### Core Models (askbot/models/)
- **Post** (`post.py`) - Base class for questions/answers/comments
- **Thread/Question** (`question.py`) - Question threads and views
- **User** (`user.py`, `user_profile.py`) - Extended user model with reputation
- **Tag** (`tag.py`) - Tag system with synonyms and categories
- **Badges** (`badges.py`) - Badge award system
- **Repute** (`repute.py`) - Reputation tracking

### Configuration System (Livesettings)
Askbot uses django-livesettings3 for runtime-editable settings stored in the database. Configuration modules in `askbot/conf/` define settings groups:
- `site_settings.py`, `email.py`, `moderation.py`, etc.
- Settings accessed via: `from askbot.conf import settings as askbot_settings`
- Wrapper in: `askbot/conf/settings_wrapper.py`

### Template System
- Uses Jinja2 (not Django templates)
- Custom Jinja2 environment in `askbot/skins/jinja2_environment.py`
- Template backends in `askbot/skins/template_backends.py`
- Skin system allows theme customization

### URL Routing
- Translatable URLs using `pgettext()` when `ASKBOT_TRANSLATE_URL` is enabled
- Configurable base URLs: `ASKBOT_MAIN_PAGE_BASE_URL`, `ASKBOT_QUESTION_PAGE_BASE_URL`
- Complex regex patterns for questions with filters (scope, sort, tags, author, page)

### Authentication
Bundled fork of `django_authopenid` in `askbot/deps/`:
- Supports multiple auth providers (OAuth, OpenID, LDAP, CAS, Okta)
- Custom user model extensions patch Django's `auth_user` table
- **Important**: Migrations automatically add missing columns but won't overwrite existing ones

## Recent Changes

### Markdown Parser Migration (Current Branch: markdown-upgrade)
Recent commit migrated from markdown2 to markdown_it:
- Changed in: `askbot/utils/markup.py`
- Uses: `markdown-it-py`, `mdit-py-plugins`, `linkify-it-py`
- Function: `get_md_converter()` returns configured MarkdownIt instance
- PostRevision.html property uses markdown input converter

Key behavior:
- Users trusted by reputation or admins can post links
- Anonymous users cannot post links
- Link detection for spam prevention in `User.assert_can_post_text()`

## Important Development Considerations

### Multi-language Support
Three language modes configured via `ASKBOT_LANGUAGE_MODE`:
- `'single-lang'` - Single language site
- `'url-lang'` - Language prefix in URLs
- `'user-lang'` - User-selected language

Check mode: `askbot.is_multilingual()`

### Database Considerations
- PostgreSQL recommended for full-text search and relevance sorting
- Supports MySQL 5.6+ and SQLite
- Database engine check: `askbot.get_database_engine_name()`

### Search System
Multiple search backends in `askbot/search/`:
- `postgresql/` - PostgreSQL full-text search
- `haystack/` - Haystack integration

### Email System
- Complex email alert system in `askbot/mail/`
- Supports instant and delayed alerts with tag filtering
- Email parsing for reply-by-email functionality

### Celery Tasks
Async task processing configured in `askbot/tasks.py`:
- Badge awarding
- Email sending
- Other background operations

### Static Files and Media
- Node.js dependencies in `askbot/media/node_modules/`
- ESLint configuration for JavaScript
- Static files collected via Django's collectstatic

### Code Quality Tools
- **Ruff**: Primary linter (configuration in `pyproject.toml`)
- **Pylint**: Available but currently disabled in pre-commit
- Many rules are TODO for gradual adoption
- Migrations excluded from linting

## Key Files to Review

- `askbot/__init__.py` - Version, requirements, utility functions
- `askbot/startup_procedures.py` - Deployment validation on startup
- `askbot/conf/__init__.py` - Settings system initialization
- `askbot/forms.py` - Large file with all form definitions
- `askbot/signals.py` - Django signal handlers
- `testproject/testproject/settings.py` - Example settings configuration

## Admin Tags Feature
Recent work on admin tags system:
- Admin tags stored in a root category
- Setting: `ASKBOT_USER_CAN_MANAGE_ADMIN_TAGS_FUNCTION`
- Defaults to admins or moderators
- Category tree editing updates admin tags setting

## Installation Paths

Function `askbot.get_install_directory()` returns askbot package location.
Function `askbot.get_askbot_module_path(relative_path)` constructs paths within askbot.
