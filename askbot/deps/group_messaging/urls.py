"""url configuration for the group_messaging application"""
from django.urls import re_path as url

from askbot.deps.group_messaging import views

urlpatterns = [
    url(
        '^threads/$',
        views.ThreadsList().as_view(),
        name='get_threads'
    ),
    url(
        '^threads/(?P<thread_id>\d+)/$',
        views.ThreadDetails().as_view(),
        name='thread_details'
    ),
    url(
        '^threads/(?P<thread_id>\d+)/delete/$',
        views.DeleteOrRestoreThread('delete').as_view(),
        name='delete_thread'
    ),
    url(
        '^threads/(?P<thread_id>\d+)/restore/$',
        views.DeleteOrRestoreThread('restore').as_view(),
        name='restore_thread'
    ),
    url(
        '^threads/create/$',
        views.NewThread().as_view(),
        name='create_thread'
    ),
    url(
        '^senders/$',
        views.SendersList().as_view(),
        name='get_senders'
    ),
    url(
        '^post-reply/$',
        views.PostReply().as_view(),
        name='post_reply'
    )
]
