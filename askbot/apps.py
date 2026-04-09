from django.apps import AppConfig
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.core.signals import request_started

BADGES_READY = False


def init_badges_once(sender, **kwargs):
    from askbot.models import badges
    global BADGES_READY
    if not BADGES_READY:
        try:
            badges.init_badges()
        except:
            pass
        else:
            BADGES_READY = True


class AskbotConfig(AppConfig):
    name = 'askbot'
    verbose_name = 'Askbot Q&A platform'
    default_auto_field = 'django.db.models.AutoField'
    badges_ready = False

    def ready(self):
        # too bad there isn't an "all_django_apps_ready" signal
        import askbot.conf
        askbot.conf.init()

        if getattr(django_settings, 'ASKBOT_AUTO_INIT_BADGES', False):
            request_started.connect(
                init_badges_once,
                dispatch_uid='init_askbot_badges_once')

        import followit
        user_model = get_user_model()
        followit.register(user_model)

        if getattr(django_settings, 'POST_ALERT_EMAIL', None):
            from askbot.post_alerts import connect as connect_post_alerts
            connect_post_alerts()
