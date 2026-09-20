# Agent Instructions

Askbot is a Django-based Q&A forum (like StackOverflow). Django 4.2, Python 3.8+, PostgreSQL recommended.

This file is the single source of truth for agent guidance. `CLAUDE.md` is a
symlink to it, so Claude Code, Codex, and other tools all read the same content.

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

If you want to override settings - either django or askbot livesettings - use decorators designed for this,
not context managers, if the setting value should not change during the test.

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

## Working with JavaScript, Svelte and SASS assets.

All client side media assets are located in `askbot/media`. Sass files are in `askbot/media/sass`.
Javascript

To rebuild css files from sass and the help panel, refer to askbot/media/CLAUDE.md

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var

## Changelog

Changelog is in askbot/doc/source/changelog.rst

- all new edits should be appended to thes section "Development (not yet released)"
- entries must be brief - ideally 1 liners, should not be too technical


## Architecture

See `.claude/docs/architecture.md` for detailed architecture reference including:
- Django app structure and core models
- Configuration system (Livesettings)
- Template system (Jinja2)
- Authentication (django_authopenid fork)
- Multi-language support, search, email, Celery tasks


## Coding style

Comments in the code must:

- be concise
- limit use of the technical jargon
- must be written in clear simple English
- should not cross reference files or lines of code - that info rots quickly

Python code must adhere to PEP8 standards.


## Issue Tracking

This project uses **bd (beads)** for issue tracking.
Run `bd prime` for workflow context, or install hooks (`bd hooks install`) for auto-injection.

**Quick reference:**
- `bd ready` - Find unblocked work
- `bd create "Title" --type task --priority 2` - Create issue
- `bd close <id>` - Complete work
- `bd dolt push` - Push beads to remote

For full workflow details: `bd prime`
