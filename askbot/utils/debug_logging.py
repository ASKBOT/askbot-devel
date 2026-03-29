"""Debug logging helpers for instant email alerts."""
from askbot.conf import settings as askbot_settings


def _emit(log_fn, run_id, msg, *args):
    full_msg = 'email-alert: instant, ' + msg
    if run_id:
        full_msg += ', run_id=%s'
        log_fn(full_msg, *args, run_id)
    else:
        log_fn(full_msg, *args)


def log_instant_email(logger, run_id, msg, *args):
    """Log instant email alert debug info if DEBUG_EMAIL_ALERTS is enabled."""
    if askbot_settings.DEBUG_EMAIL_ALERTS:
        _emit(logger.info, run_id, msg, *args)


def log_instant_email_error(logger, run_id, msg, *args):
    """Log instant email alert error (always, regardless of DEBUG_EMAIL_ALERTS)."""
    _emit(logger.error, run_id, msg, *args)
