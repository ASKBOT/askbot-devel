from group_messaging.models import get_unread_inbox_counter

def group_messaging_context(request):
    if request.user.is_authenticated():
        count_record = get_unread_inbox_counter(request.user)
        return {'group_messaging_unread_inbox_count': count_record.count}
    return {}
