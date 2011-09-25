import logging

log = logging.getLogger('tracking.listeners')

try:
    from django.core.cache import cache
    from django.db.models.signals import post_save, post_delete

    from tracking.models import UntrackedUserAgent, BannedIP
except ImportError:
    pass
else:

    def refresh_untracked_user_agents(sender, instance, created=False, **kwargs):
        """Updates the cache of user agents that we don't track"""

        log.debug('Updating untracked user agents cache')
        cache.set('_tracking_untracked_uas',
            UntrackedUserAgent.objects.all(),
            3600)

    def refresh_banned_ips(sender, instance, created=False, **kwargs):
        """Updates the cache of banned IP addresses"""

        log.debug('Updating banned IP cache')
        cache.set('_tracking_banned_ips',
            [b.ip_address for b in BannedIP.objects.all()],
            3600)

    post_save.connect(refresh_untracked_user_agents, sender=UntrackedUserAgent)
    post_delete.connect(refresh_untracked_user_agents, sender=UntrackedUserAgent)

    post_save.connect(refresh_banned_ips, sender=BannedIP)
    post_delete.connect(refresh_banned_ips, sender=BannedIP)
