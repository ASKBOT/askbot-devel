#!/bin/sh
set -e

cd /app

echo "Running migrations…"
python manage.py migrate --noinput

# Create admin superuser if ADMIN_PASSWORD is set and user doesn't exist yet
if [ -n "$ADMIN_PASSWORD" ]; then
    python manage.py shell <<'EOF'
import os
from django.contrib.auth import get_user_model
User = get_user_model()
password = os.environ["ADMIN_PASSWORD"]
if not User.objects.filter(username="admin").exists():
    User.objects.create_superuser("admin", "admin@example.com", password)
    print("Created admin superuser.")
else:
    print("Admin user already exists, skipping.")
EOF
fi

echo "Starting gunicorn…"
exec gunicorn askbot_site.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --access-logfile - \
    --error-logfile -
