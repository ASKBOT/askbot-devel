# this is a cron job for askbot that includes all
# commands that need to be run periodically
# please find introduction to cron here:
# http://www.unixgeeks.org/security/newbie/unix/cron-1.html
#
# if you prefer, you can split this file into several

PROJECT_PARENT_DIR=/path/to/dir_containing_askbot_site
PROJECT_DIR_NAME=askbot_site

export PYTHONPATH=$PROJECT_PARENT_DIR:$PYTHONPATH
PROJECT_ROOT=$PROJECT_DIR_NAME/$PROJECT_NAME

#these are actual commands that are to be run
python $PROJECT_ROOT/manage.py send_email_alerts
