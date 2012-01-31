# -*- coding: utf-8 -*-
"""
:synopsis: connector to standard Django admin interface

To make more models accessible in the Django admin interface, add more classes subclassing ``django.contrib.admin.Model``

Names of the classes must be like `SomeModelAdmin`, where `SomeModel` must 
exactly match name of the model used in the project
"""
from django.contrib import admin
from askbot import models

class AnonymousQuestionAdmin(admin.ModelAdmin):
    """AnonymousQuestion admin class"""

class TagAdmin(admin.ModelAdmin):
    """Tag admin class"""

class VoteAdmin(admin.ModelAdmin):
    """  admin class"""

class FavoriteQuestionAdmin(admin.ModelAdmin):
    """  admin class"""

class PostRevisionAdmin(admin.ModelAdmin):
    """  admin class"""

class AwardAdmin(admin.ModelAdmin):
    """  admin class"""

class ReputeAdmin(admin.ModelAdmin):
    """  admin class"""

class ActivityAdmin(admin.ModelAdmin):
    """  admin class"""
    
admin.site.register(models.Post)
admin.site.register(models.Tag, TagAdmin)
admin.site.register(models.Vote, VoteAdmin)
admin.site.register(models.FavoriteQuestion, FavoriteQuestionAdmin)
admin.site.register(models.PostRevision, PostRevisionAdmin)
admin.site.register(models.Award, AwardAdmin)
admin.site.register(models.Repute, ReputeAdmin)
admin.site.register(models.Activity, ActivityAdmin)
