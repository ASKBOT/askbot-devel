#!/usr/bin/env bash

if [ -x /wait ]; then /wait; else sleep 64; fi

python ${ASKBOT_SITE}/${ASKBOT_APP}/prestart.py

if [ -z "$NO_CRON" ]; then
    crond || cron
fi

