# CLAUDE.md

Askbot is a Django-based Q&A forum (like StackOverflow). Django 4.2, Python 3.8+, PostgreSQL recommended.

## Development Setup

```bash
# Install
pip install -e .
askbot-setup

# Pre-commit (required)
pre-commit install
```

- Test project: `testproject/`
- Virtual env may be specified in task files

## Testing

```bash
# Tox (recommended)
tox

Use virtual environment `env-md`

# Direct
cd askbot_site/

../env-md/bin/python manage.py test --parallel 8 askbot.tests askbot.deps.django_authopenid.tests

# Database config (if needed)
DB_TYPE=postgres DB_USER=askbot DB_PASS=askB0T! DB_HOST=localhost DB_PORT=5432 DB_NAME=askbotfortox
```

**Before writing new tests:** Check if the desired test already exists. Search existing test files for similar test cases. If a test exists, inform the developer. If not, plan the new test.

## Running One-Off Python Scripts

Use `manage.py shell` with heredoc for one-off scripts that need Django context:

```bash
cd askbot_site && ../env-md/bin/python manage.py shell << 'EOF'
from askbot.utils.markup import markdown_input_converter

result = markdown_input_converter("**test**")
print(result)
EOF
```

This properly initializes Django settings and all app configurations.

## Issue Tracking

This project uses **bd** (beads). Run `bd onboard` to get started.

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --status in_progress  # Claim work
bd close <id>         # Complete work
bd sync               # Sync with git
bd new "<title>"      # Create a new issue
bd comments <id>      # List comments on an issue
bd comments add <id> "message"  # Add a comment
```

Dependencies: `bd dep <blocker> --blocks <blocked>` | `bd dep tree <id>`

**Making issues part of an epic** If I ask an issue X to be part of certain epic E, the issue in question must be blocking
the said epic issue - i.e. `bd dep <X-id> --blocks <E-id>`

**Creating issues:** Issues must be self-sufficient—include all necessary context, acceptance criteria, and relevant file paths so that implementing them requires no additional hand-typed context (e.g., "implement issue X" should be enough).

Use `/land` skill when ending a work session.

## Architecture

See `.claude/docs/architecture.md` for detailed architecture reference including:
- Django app structure and core models
- Configuration system (Livesettings)
- Template system (Jinja2)
- Authentication (django_authopenid fork)
- Multi-language support, search, email, Celery tasks
