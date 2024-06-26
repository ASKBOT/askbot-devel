from django.db import models
from django.utils.translation import gettext_lazy
from askbot.models import Tag, Group
from askbot.const import DEFAULT_QUESTION_WIDGET_STYLE, SEARCH_ORDER_BY

class AskWidget(models.Model):
    '''stores widgets styles and options'''
    title = models.CharField(max_length=100)
    group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, null=True, blank=True, on_delete=models.CASCADE)

    include_text_field = models.BooleanField(default=False, blank=True)

    inner_style = models.TextField(blank=True)
    outer_style = models.TextField(blank=True)

    class Meta:
        app_label = 'askbot'

    def __str__(self):
        return "Widget: %s" % self.title


class QuestionWidget(models.Model):
    title = models.CharField(max_length=100)
    question_number = models.PositiveIntegerField(default=7)
    tagnames = models.CharField(gettext_lazy('tags'), max_length=50)
    group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.CASCADE)
    search_query = models.CharField(
        max_length=50, null=True, blank=True, default=''
    )
    order_by = models.CharField(max_length=18,
            choices=SEARCH_ORDER_BY, default='-added_at')
    style = models.TextField(gettext_lazy('css for the widget'),
            default=DEFAULT_QUESTION_WIDGET_STYLE, blank=True)

    class Meta:
        app_label = 'askbot'
