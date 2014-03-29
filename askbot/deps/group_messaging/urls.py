"""url configuration for the group_messaging application"""
from django.conf.urls import patterns
from django.conf.urls import url
from group_messaging import views

urlpatterns = patterns('',
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
        '^threads/(?P<thread_id>\d+)/delete-or-restore/$',
        views.DeleteOrRestoreThread().as_view(),
        name='delete_or_restore_thread'
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
)
