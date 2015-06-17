# -*- coding: utf-8 -*-

from django.contrib import admin
from askbot.deps.django_authopenid.models import UserAssociation


class UserAssociationAdmin(admin.ModelAdmin):
    """User association admin class"""
admin.site.register(UserAssociation, UserAssociationAdmin)
