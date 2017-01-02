FROM python:2

ENV PYTHONUNBUFFERED 1

ADD . /src/
WORKDIR /src/
RUN pip install -r askbot_requirements.txt
RUN python setup.py install

RUN mkdir /site/
WORKDIR /site/
RUN askbot-setup --dir-name=. --db-engine=${ASKBOT_DATABASE_ENGINE:-2} \
    --db-name=${ASKBOT_DATABASE_NAME:-db.sqlite} \
    --db-user="${ASKBOT_DATABASE_USER}" \
    --db-password="${ASKBOT_DATABASE_PASSWORD}" \
    --domain="${ASKBOT_DOMAIN:-example.com}"

RUN sed "s/ROOT_URLCONF.*/ROOT_URLCONF = 'urls'/"  settings.py -i

RUN python manage.py migrate --noinput
RUN python manage.py collectstatic --noinput


CMD ["python", "manage.py", "runserver", "0.0.0.0:8080"]

EXPOSE 8080
