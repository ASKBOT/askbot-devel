from django.apps import AppConfig
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
    badges_ready = False

    def ready(self):
        # too bad there isn't an "all_django_apps_ready" signal
        request_started.connect(
            init_badges_once,
            dispatch_uid='init_askbot_badges_once')

        import followit
        user_model = get_user_model()
        followit.register(user_model)
