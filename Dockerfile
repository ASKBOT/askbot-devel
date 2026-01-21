# This Dockerifle builds a simple Askbot installation
#
# It makes use of environment variables:
# 1. DATABASE_URL See https://github.com/kennethreitz/dj-database-url for details
# 2. SECRET_KEY for making hashes within Django.
# 3. ADMIN_PASSWORD used for creating a user named "admin"
# 4. NO_CRON set this to "yes" to disable the embedded cron job.
#
# Make sure to *+always* start the container with the same SECRET_KEY.
#
# Start with something like
#
# docker run -e 'DATABASE_URL=sqlite:////askbot_site/askbot.sqlite' -e "SECRET_KEY=$(openssl rand 14 | base64)" -e ADMIN_PASSWORD=admin -p 8080:8000 askbot/askbot:latest
#
# User uploads are stored in **/askbot_site/upfiles** . I'd recommend to make it a kubernetes volume.
# Static files are stored in **/askbot_site/static** . I'd recommend to make it a kubernetes volume.

# Stage 0
FROM tiangolo/uwsgi-nginx:python3.8-alpine

ARG HTTP_PROXY=
ARG HTTPS_PROXY=

ENV http_proxy $HTTP_PROXY
ENV https_proxy $HTTPS_PROXY
ENV no_proxy ""

RUN apk add --update --no-cache git py3-cffi \
    gcc g++ git make mkinitfs kmod mtools squashfs-tools py3-cffi \
    libffi-dev linux-headers musl-dev libc-dev openssl-dev \
    python3-dev zlib-dev libxml2-dev libxslt-dev jpeg-dev \
    postgresql-dev zlib jpeg libxml2 libxslt postgresql-libs \
    hiredis \
    && python -m pip install --upgrade pip \
    && pip install psycopg2

COPY ${ASKBOT}/askbot/__init__.py /askbot_meta.py
WORKDIR /
RUN pip install virtualenv \
    && pip install setuptools \
    && pip install wheel \
    && python3 -c "from askbot_meta import REQUIREMENTS; _=[print(r) for r in REQUIREMENTS.values()];" >requirements.txt \
    && pip install -r requirements.txt

COPY ${ASKBOT}/askbot /usr/local/src/askbot/askbot
COPY ${ASKBOT}/AUTHORS ${ASKBOT}/COPYING ${ASKBOT}/LICENSE ${ASKBOT}/setup.py ${ASKBOT}/ez_setup.py ${ASKBOT}/askbot_requirements.txt ${ASKBOT}/MANIFEST.in /usr/local/src/askbot/
RUN cd /usr/local/src/askbot \
    && python3 setup.py bdist_wheel \
    && cp /usr/local/src/askbot/dist/askbot*.whl / \
    && cp /usr/local/src/askbot/askbot_requirements.txt /

RUN pip install /askbot*.whl \
    && find /root/.cache -name "*.whl" -exec cp {} / \; \
    && ls /*.whl


# Stage 1
FROM tiangolo/uwsgi-nginx:python3.8-alpine

ARG SITE=askbot-site
ARG APP=askbot_app
ARG ASKBOT=.
ARG HTTP_PROXY=
ARG HTTPS_PROXY=
ARG CACHE_PASSWORD

ENV PYTHONUNBUFFERED 1
ENV ASKBOT_SITE /${SITE}
ENV ASKBOT_APP ${APP}
ENV ASKBOT_CACHE locmem
ENV CACHE_NODES ""
ENV NO_CRON yes
ENV ADMIN_PASSWORD admin
ENV SECRET_KEY 0123456789abcdef
ENV DATABASE_URL "sqlite:///${ASKBOT_SITE}/askbot.sqlite"
ENV DJANGO_SETTINGS_MODULE ${ASKBOT_APP}.settings
ENV http_proxy $HTTP_PROXY
ENV https_proxy $HTTPS_PROXY
ENV no_proxy ""

ENV UWSGI_INI ${ASKBOT_SITE}/${ASKBOT_APP}/uwsgi.ini
# Not recognized by uwsgi-nginx, yet.
# The file doesn't exist either!
#ENV PRE_START_PATH /${SITE}/prestart.sh

# using more than 1 process each requires redis or memcached as backend
ENV NGINX_WORKER_PROCESSES 1
ENV UWSGI_PROCESSES 1
ENV UWSGI_CHEAPER 0
ENV LISTEN_PORT 8000

RUN apk add --update --no-cache git py3-cffi \
    zlib jpeg libxml2 libxslt postgresql-libs \
    hiredis

COPY ${ASKBOT}/askbot_requirements.txt /
COPY --from=0 /*.whl /

RUN    python -m pip install --upgrade pip \
    && pip install redis django-redis-cache simplejson \
    && pip install /*.whl && rm /*.whl \
    && rm -rf /root/.cache

# lets not use the Askbot installer for now. Let's do this instead:

RUN pip install j2render dj-database-url \
    && mkdir -p ${ASKBOT_SITE}/log ${ASKBOT_SITE}/cron ${ASKBOT_SITE}/upfiles ${ASKBOT_SITE}/static ${ASKBOT_SITE}/askbot_app \
    && SRC_DIR=`python -c 'import os; from askbot import setup_templates; print(os.path.dirname(setup_templates.__file__))'` \
    && cp ${SRC_DIR}/celery_app.py ${ASKBOT_SITE}/${ASKBOT_APP} \
    && cp ${SRC_DIR}/__init__.py ${ASKBOT_SITE}/${ASKBOT_APP} \
    && cp ${SRC_DIR}/urls.py ${ASKBOT_SITE}/${ASKBOT_APP} \
    && cp ${SRC_DIR}/django.wsgi ${ASKBOT_SITE}/${ASKBOT_APP} \
    && cp ${SRC_DIR}/prestart.py ${ASKBOT_SITE}/${ASKBOT_APP} \
    && cp ${SRC_DIR}/prestart.sh ${ASKBOT_SITE}/${ASKBOT_APP} \
    && cp ${SRC_DIR}/cron-askbot.sh ${ASKBOT_SITE}/${ASKBOT_APP} \
    && cp ${SRC_DIR}/manage.py ${ASKBOT_SITE} \
    && ln -sf `realpath ${SRC_DIR}/../doc` ${ASKBOT_SITE}/doc \
    && echo "{\"askbot_app\": \"${ASKBOT_APP}\", \"askbot_site\": \"${SITE}\", \"database_engine\": \"\" , \"database_name\": \"\" , \"database_password\": \"\", \"database_user\": \"\" , \"settings_path\": \"${ASKBOT_APP}\", \"logfile_name\": \"stdout\"}" >/data.json \
    && j2render -o ${ASKBOT_SITE}/${ASKBOT_APP}/settings.py --source /data.json ${SRC_DIR}/settings.py.jinja2 \
    && j2render -o ${ASKBOT_SITE}/cron/crontab --source /data.json ${SRC_DIR}/crontab.jinja2 \
    && j2render -o ${ASKBOT_SITE}/${ASKBOT_APP}/uwsgi.ini --source /data.json ${SRC_DIR}/uwsgi.ini.jinja2 \
    && cat ${SRC_DIR}/../container/uwsgi.txt >> ${ASKBOT_SITE}/${ASKBOT_APP}/uwsgi.ini \
    && cat ${SRC_DIR}/../container/augment_settings.py >> ${ASKBOT_SITE}/${ASKBOT_APP}/settings.py

# adapt image to our needs (in order of appearance)
# * install wait to stall instances of this container until the database
#   reachable
# * remove /etc/uwsgi/uwsgi.ini; we bring our own uwsgi.ini and tell the
#   container in the env var UWSGI_INI about it
# * copy our prestart.sh into /app because that's where the entrypoint
#   looks for it and this behaviour cannot (yet) be overwritten through
#   env vars.
# * add Askbot tasks to cron
# * collect staticfiles
# * make nginx serve staticfiles directly without involving uwsgi/python
#   this is a bit tricky as this image writes nginx.conf at startup time
#   and takes env vars into account when doing so. In order to keep this
#   mechanism, changing the nginx.conf actually means modifying the
#   logic in /entrypoint.sh, which creates the nginx.conf
# * we keep unix domain sockets into /tmp, not /run
# * change owning group to gid 0 and make things group-writable
#   (essential to OpenShift support and some Kubernetes deployments)
# * add the uwsgi user to group root(0)
ADD https://github.com/ufoscout/docker-compose-wait/releases/download/2.5.0/wait /wait
RUN chmod +x /wait \
    && rm /etc/uwsgi/uwsgi.ini \
    && sed -i "s%^\(\s*command\s*=.*\)--ini\s*/etc/uwsgi/uwsgi.ini\(.*\)$%\1\2%" /etc/supervisor.d/supervisord.ini \
    && cp ${ASKBOT_SITE}/${ASKBOT_APP}/prestart.sh /app \
    && /usr/bin/crontab ${ASKBOT_SITE}/cron/crontab \
    && cd ${ASKBOT_SITE} \
    && SECRET_KEY=whatever \
       ASKBOT_CACHE=locmem python manage.py collectstatic --noinput \
    && cd ${ASKBOT_SITE}/${ASKBOT_APP} \
    && STATIC_URL=`SECRET_KEY=whatever python -c 'import settings;print(settings.STATIC_URL)'` \
    && STATIC_ROOT=`SECRET_KEY=whatever python -c 'import settings;print(settings.STATIC_ROOT)'` \
    && MEDIA_URL=`SECRET_KEY=whatever python -c 'import settings;print(settings.MEDIA_URL)'` \
    && MEDIA_ROOT=`SECRET_KEY=whatever python -c 'import settings;print(settings.MEDIA_ROOT)'` \
    && sed -i "/content_server.*USE_LISTEN_PORT/a content_server=\$content_server\"    location ${STATIC_URL} { alias ${STATIC_ROOT}/; }\n\"" /entrypoint.sh \
    && sed -i "/content_server.*USE_LISTEN_PORT/a content_server=\$content_server\"    location ${MEDIA_URL} { alias ${MEDIA_ROOT}/; }\n\"" /entrypoint.sh \
    && sed -i 's%/run/supervisord.sock%/tmp/supervisor.sock%g' /etc/supervisord.conf \
    && for i in ${ASKBOT_SITE} /etc/nginx /var/log /var/cache /run; do\
       mkdir -p $i; chown -Rh :0 $i && chmod -R g+w $i; done \
    && sed -i '/^chown-socket/d' ${ASKBOT_SITE}/${ASKBOT_APP}/uwsgi.ini \
    && sed -i 's/^chmod-socket.*/chmod-socket = 666/' ${ASKBOT_SITE}/${ASKBOT_APP}/uwsgi.ini \
    && chmod 660 /etc/supervisord.conf \
    && sed -i 's/0:root/0:root,uwsgi/' /etc/group

RUN apk add --update --no-cache dos2unix \
    && dos2unix ${ASKBOT_SITE}/${ASKBOT_APP}/* ${ASKBOT_SITE}/* /app/* /etc/supervisord.conf /etc/supervisor.d/* /etc/nginx/*

USER uwsgi

VOLUME ["${ASKBOT_SITE}/static", "${ASKBOT_SITE}/upfiles"]
EXPOSE ${LISTEN_PORT}
WORKDIR ${ASKBOT_SITE}
