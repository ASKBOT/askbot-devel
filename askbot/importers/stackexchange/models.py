from django.db import models
class Badge(models.Model):
    id = models.IntegerField(primary_key=True)
    class_type = models.IntegerField(null=True)
    name = models.CharField(max_length=50, null=True)
    description = models.TextField(null=True)
    single = models.BooleanField(null=True)
    secret = models.BooleanField(null=True)
    tag_based = models.BooleanField(null=True)
    command = models.TextField(null=True)
    award_frequency = models.IntegerField(null=True)

class CloseReason(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=200, null=True)
    description = models.CharField(max_length=256, null=True)
    display_order = models.IntegerField(null=True)

class Comment2Vote(models.Model):
    id = models.IntegerField(primary_key=True)
    post_comment = models.ForeignKey('PostComment', related_name='Comment2Vote_by_post_comment_set', null=True, on_delete=models.CASCADE)
    vote_type = models.ForeignKey('VoteType', related_name='Comment2Vote_by_vote_type_set', null=True, on_delete=models.CASCADE)
    creation_date = models.DateTimeField(null=True)
    user = models.ForeignKey('User', related_name='Comment2Vote_by_user_set', null=True, on_delete=models.CASCADE)
    ip_address = models.CharField(max_length=40, null=True)
    user_display_name = models.CharField(max_length=40, null=True)
    deletion_date = models.DateTimeField(null=True)

class FlatPage(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=50, null=True)
    url = models.CharField(max_length=128, null=True)
    value = models.TextField(null=True)
    content_type = models.CharField(max_length=50, null=True)
    active = models.BooleanField(null=True)
    use_master = models.BooleanField(null=True)

class Message(models.Model):
    id = models.IntegerField(primary_key=True)
    user = models.ForeignKey('User', related_name='Message_by_user_set', null=True, on_delete=models.CASCADE)
    message_type = models.ForeignKey('MessageType', related_name='Message_by_message_type_set', null=True, on_delete=models.CASCADE)
    is_read = models.BooleanField(null=True)
    creation_date = models.DateTimeField(null=True)
    text = models.TextField(null=True)
    post = models.ForeignKey('Post', related_name='Message_by_post_set', null=True, on_delete=models.CASCADE)

class MessageType(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=50, null=True)
    description = models.CharField(max_length=300, null=True)

class ModeratorMessage(models.Model):
    id = models.IntegerField(primary_key=True)
    message_type = models.ForeignKey('MessageType', related_name='ModeratorMessage_by_message_type_set', null=True, on_delete=models.CASCADE)
    creation_date = models.DateTimeField(null=True)
    creation_ip_address = models.CharField(max_length=40, null=True)
    text = models.TextField(null=True)
    user = models.ForeignKey('User', related_name='ModeratorMessage_by_user_set', null=True, on_delete=models.CASCADE)
    post = models.ForeignKey('Post', related_name='ModeratorMessage_by_post_set', null=True, on_delete=models.CASCADE)
    deletion_date = models.DateTimeField(null=True)
    deletion_user = models.ForeignKey('User', related_name='ModeratorMessage_by_deletion_user_set', null=True, on_delete=models.CASCADE)
    deletion_ip_address = models.CharField(max_length=40, null=True)
    user_display_name = models.CharField(max_length=40, null=True)

class PostComment(models.Model):
    id = models.IntegerField(primary_key=True)
    post = models.ForeignKey('Post', related_name='PostComment_by_post_set', null=True, on_delete=models.CASCADE)
    text = models.TextField(null=True)
    creation_date = models.DateTimeField(null=True)
    ip_address = models.CharField(max_length=15, null=True)
    user = models.ForeignKey('User', related_name='PostComment_by_user_set', null=True, on_delete=models.CASCADE)
    user_display_name = models.CharField(max_length=30, null=True)
    deletion_date = models.DateTimeField(null=True)
    deletion_user = models.ForeignKey('User', related_name='PostComment_by_deletion_user_set', null=True, on_delete=models.CASCADE)
    score = models.IntegerField(null=True)

class PostHistoryType(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=50, null=True)
    description = models.CharField(max_length=300, null=True)

class PostHistory(models.Model):
    id = models.IntegerField(primary_key=True)
    post_history_type = models.ForeignKey('PostHistoryType', related_name='PostHistory_by_post_history_type_set', null=True, on_delete=models.CASCADE)
    post = models.ForeignKey('Post', related_name='PostHistory_by_post_set', null=True, on_delete=models.CASCADE)
    revision_guid = models.CharField(max_length=64, null=True)
    creation_date = models.DateTimeField(null=True)
    ip_address = models.CharField(max_length=40, null=True)
    user = models.ForeignKey('User', related_name='PostHistory_by_user_set', null=True, on_delete=models.CASCADE)
    comment = models.CharField(max_length=400, null=True)
    text = models.TextField(null=True)
    user_display_name = models.CharField(max_length=40, null=True)
    user_email = models.CharField(max_length=100, null=True)
    user_website_url = models.CharField(max_length=200, null=True)

class Post2Vote(models.Model):
    id = models.IntegerField(primary_key=True)
    post = models.ForeignKey('Post', related_name='Post2Vote_by_post_set', null=True, on_delete=models.CASCADE)
    user = models.ForeignKey('User', related_name='Post2Vote_by_user_set', null=True, on_delete=models.CASCADE)
    vote_type = models.ForeignKey('VoteType', related_name='Post2Vote_by_vote_type_set', null=True, on_delete=models.CASCADE)
    creation_date = models.DateTimeField(null=True)
    deletion_date = models.DateTimeField(null=True)
    target_user = models.ForeignKey('User', related_name='Post2Vote_by_target_user_set', null=True, on_delete=models.CASCADE)
    target_rep_change = models.IntegerField(null=True)
    voter_rep_change = models.IntegerField(null=True)
    comment = models.CharField(max_length=150, null=True)
    ip_address = models.CharField(max_length=40, null=True)
    linked_post = models.ForeignKey('Post', related_name='Post2Vote_by_linked_post_set', null=True, on_delete=models.CASCADE)

class Post(models.Model):
    id = models.IntegerField(primary_key=True)
    post_type = models.ForeignKey('PostType', related_name='Post_by_post_type_set', null=True, on_delete=models.CASCADE)
    creation_date = models.DateTimeField(null=True)
    score = models.IntegerField(null=True)
    view_count = models.IntegerField(null=True)
    body = models.TextField(null=True)
    owner_user = models.ForeignKey('User', related_name='Post_by_owner_user_set', null=True, on_delete=models.CASCADE)
    last_editor_user = models.ForeignKey('User', related_name='Post_by_last_editor_user_set', null=True, on_delete=models.CASCADE)
    last_edit_date = models.DateTimeField(null=True)
    last_activity_date = models.DateTimeField(null=True)
    last_activity_user = models.ForeignKey('User', related_name='Post_by_last_activity_user_set', null=True, on_delete=models.CASCADE)
    parent = models.ForeignKey('self', related_name='Post_by_parent_set', null=True, on_delete=models.CASCADE)
    accepted_answer = models.ForeignKey('self', related_name='Post_by_accepted_answer_set', null=True, on_delete=models.CASCADE)
    title = models.CharField(max_length=250, null=True)
    tags = models.CharField(max_length=150, null=True)
    community_owned_date = models.DateTimeField(null=True)
    history_summary = models.CharField(max_length=150, null=True)
    answer_score = models.IntegerField(null=True)
    answer_count = models.IntegerField(null=True)
    comment_count = models.IntegerField(null=True)
    favorite_count = models.IntegerField(null=True)
    deletion_date = models.DateTimeField(null=True)
    closed_date = models.DateTimeField(null=True)
    locked_date = models.DateTimeField(null=True)
    locked_duration = models.IntegerField(null=True)
    owner_display_name = models.CharField(max_length=40, null=True)
    last_editor_display_name = models.CharField(max_length=40, null=True)
    bounty_amount = models.IntegerField(null=True)
    bounty_closes = models.DateTimeField(null=True)
    bounty_closed = models.DateTimeField(null=True)
    last_owner_email_date = models.DateTimeField(null=True)

class PostType(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=50, null=True)
    description = models.CharField(max_length=300, null=True)

class SchemaVersion(models.Model):
    version = models.IntegerField(null=True)

class Setting(models.Model):
    id = models.IntegerField(primary_key=True)
    key = models.CharField(max_length=256, null=True)
    value = models.TextField(null=True)

class SystemMessage(models.Model):
    id = models.IntegerField(primary_key=True)
    user = models.ForeignKey('User', related_name='SystemMessage_by_user_set', null=True, on_delete=models.CASCADE)
    creation_date = models.DateTimeField(null=True)
    text = models.TextField(null=True)
    deletion_date = models.DateTimeField(null=True)
    deletion_user = models.ForeignKey('User', related_name='SystemMessage_by_deletion_user_set', null=True, on_delete=models.CASCADE)

class Tag(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=50, null=True)
    count = models.IntegerField(null=True)
    user = models.ForeignKey('User', related_name='Tag_by_user_set', null=True, on_delete=models.CASCADE)
    creation_date = models.DateTimeField(null=True)
    is_moderator_only = models.BooleanField(null=True)
    is_required = models.BooleanField(null=True)
    aliases = models.CharField(max_length=200, null=True)

class ThemeResource(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=50, null=True)
    value = models.TextField(null=True)
    content_type = models.CharField(max_length=50, null=True)
    version = models.CharField(max_length=6, null=True)

class ThemeTextResource(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=50, null=True)
    value = models.TextField(null=True)
    content_type = models.CharField(max_length=50, null=True)

class ThrottleBucket(models.Model):
    id = models.IntegerField(primary_key=True)
    type = models.CharField(max_length=256, null=True)
    ip_address = models.CharField(max_length=64, null=True)
    tokens = models.IntegerField(null=True)
    last_update = models.DateTimeField(null=True)

class UserHistoryType(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=50, null=True)
    description = models.CharField(max_length=300, null=True)

class UserHistory(models.Model):
    id = models.IntegerField(primary_key=True)
    user_history_type = models.ForeignKey('UserHistoryType', related_name='UserHistory_by_user_history_type_set', null=True, on_delete=models.CASCADE)
    creation_date = models.DateTimeField(null=True)
    ip_address = models.CharField(max_length=40, null=True)
    user = models.ForeignKey('User', related_name='UserHistory_by_user_set', null=True, on_delete=models.CASCADE)
    comment = models.CharField(max_length=400, null=True)
    user_display_name = models.CharField(max_length=40, null=True)
    moderator_user = models.ForeignKey('User', related_name='UserHistory_by_moderator_user_set', null=True, on_delete=models.CASCADE)
    reputation = models.IntegerField(null=True)

class User2Badge(models.Model):
    id = models.IntegerField(primary_key=True)
    user = models.ForeignKey('User', related_name='User2Badge_by_user_set', null=True, on_delete=models.CASCADE)
    badge = models.ForeignKey('Badge', related_name='User2Badge_by_badge_set', null=True, on_delete=models.CASCADE)
    date = models.DateTimeField(null=True)
    comment = models.CharField(max_length=50, null=True)

class User2Vote(models.Model):
    id = models.IntegerField(primary_key=True)
    user = models.ForeignKey('User', related_name='User2Vote_by_user_set', null=True, on_delete=models.CASCADE)
    vote_type = models.ForeignKey('VoteType', related_name='User2Vote_by_vote_type_set', null=True, on_delete=models.CASCADE)
    target_user = models.ForeignKey('User', related_name='User2Vote_by_target_user_set', null=True, on_delete=models.CASCADE)
    creation_date = models.DateTimeField(null=True)
    deletion_date = models.DateTimeField(null=True)
    ip_address = models.CharField(max_length=40, null=True)

class User(models.Model):
    id = models.IntegerField(primary_key=True)
    user_type = models.ForeignKey('UserType', related_name='User_by_user_type_set', null=True, on_delete=models.CASCADE)
    open_id = models.CharField(max_length=200, null=True)
    reputation = models.IntegerField(null=True)
    views = models.IntegerField(null=True)
    creation_date = models.DateTimeField(null=True)
    last_access_date = models.DateTimeField(null=True)
    has_replies = models.BooleanField(null=True)
    has_message = models.BooleanField(null=True)
    opt_in_email = models.BooleanField(null=True)
    opt_in_recruit = models.BooleanField(null=True)
    last_login_date = models.DateTimeField(null=True)
    last_email_date = models.DateTimeField(null=True)
    last_login_ip = models.CharField(max_length=15, null=True)
    open_id_alt = models.CharField(max_length=200, null=True)
    email = models.CharField(max_length=100, null=True)
    display_name = models.CharField(max_length=40, null=True)
    display_name_cleaned = models.CharField(max_length=40, null=True)
    website_url = models.CharField(max_length=200, null=True)
    real_name = models.CharField(max_length=100, null=True)
    location = models.CharField(max_length=100, null=True)
    birthday = models.DateTimeField(null=True)
    badge_summary = models.CharField(max_length=50, null=True)
    about_me = models.TextField(null=True)
    preferences_raw = models.TextField(null=True)
    timed_penalty_date = models.DateTimeField(null=True)
    guid = models.CharField(max_length=64, null=True)
    phone = models.CharField(max_length=20, null=True)
    password_id = models.IntegerField(null=True)

class UserType(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=50, null=True)
    description = models.CharField(max_length=300, null=True)

class VoteType(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=50, null=True)
    description = models.CharField(max_length=300, null=True)

class Password(models.Model):
    id = models.IntegerField(primary_key = True)
    password = models.CharField(max_length = 128)
    salt = models.CharField(max_length = 32)
