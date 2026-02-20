# Askbot Dockerfile — hobby / localhost deployment
# Build:  docker compose build
# Run:    docker compose up
FROM python:3.12-slim-bookworm AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        libjpeg-dev \
        zlib1g-dev \
        libxml2-dev \
        libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY . .

RUN pip install --no-cache-dir setuptools . gunicorn whitenoise redis

# Generate the askbot project with --noinput.
# Caching and extra settings are read from snippet files in docker/.
RUN askbot-setup --noinput \
        --root-directory /app \
        --proj-name askbot_site \
        --db-settings "$(cat /src/docker/db_settings.py)" \
        --admin-name "Admin" \
        --admin-email "admin@example.com" \
        --caching-settings "$(cat /src/docker/caching_settings.py)" \
        --append-settings "$(cat /src/docker/extra_settings.py)" \
    && printf '%s\n' \
        'import os' \
        'from django.core.wsgi import get_wsgi_application' \
        "os.environ.setdefault(\"DJANGO_SETTINGS_MODULE\", \"askbot_site.settings\")" \
        'application = get_wsgi_application()' \
        > /app/askbot_site/wsgi.py

# Collect static files during build (whitenoise will compress & cache-bust).
WORKDIR /app
RUN SECRET_KEY=build-placeholder python manage.py collectstatic --noinput

# --- Runtime stage ---
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libjpeg62-turbo \
        zlib1g \
        libxml2 \
        libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages and the generated project
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
COPY --from=build /app /app

COPY ./docker/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

WORKDIR /app
EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
