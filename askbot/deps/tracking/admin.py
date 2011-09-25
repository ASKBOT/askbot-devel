from django.contrib import admin
from tracking.models import BannedIP, UntrackedUserAgent

admin.site.register(BannedIP)
admin.site.register(UntrackedUserAgent)