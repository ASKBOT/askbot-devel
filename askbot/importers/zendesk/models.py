import re
from django.db import models
from django.contrib.auth.models import User as DjangoUser
from django.utils.html import strip_tags
from askbot.utils.html import unescape

TAGS = {}#internal cache for mappings forum id _> forum name

# todo: don't allow nulls in char fields that should just allow empty strings

class Entry(models.Model):
    """
    Top level topic posts in a forum
    """
    body = models.TextField()
    created_at = models.DateTimeField()
    tags = models.CharField(max_length = 255, null = True)
    flag_type_id = models.IntegerField() # topic type
    forum_id = models.IntegerField() # forum entry is in
    hits = models.IntegerField(null = True) # number of views
    entry_id = models.IntegerField()
    is_highlighted = models.BooleanField(default = False) # ignored
    is_locked = models.BooleanField(default = False) # close
    is_pinned = models.BooleanField(default = False) # ignored
    is_public = models.BooleanField(default = True)
    organization_id = models.IntegerField(null = True)
    position = models.IntegerField(null = True) # ignored
    posts_count = models.IntegerField(null = True)
    submitter_id = models.IntegerField()
    title = models.CharField(max_length = 300)
    updated_at = models.DateTimeField()
    votes_count = models.IntegerField(null = True, default = 0)
    ab_id = models.IntegerField(null = True)

    def get_author(self):
        """returns author of the post, from the Django user table"""
        zendesk_user = User.objects.get(zendesk_user_id = self.submitter_id)
        return DjangoUser.objects.get(id = zendesk_user.askbot_user_id)

    def get_body_text(self):
        """unescapes html entities in the body text,
        saves in the internal cache and returns the value"""
        if not hasattr(self, '_body_text'):
            self._body_text = unescape(self.body)
        return self._body_text

    def get_tag_names(self):
        """return tags on entry as well as forum title as a tag"""
        # if self.forum_id not in TAGS:
        #     forum = Forum.objects.get(forum_id = self.forum_id)
        #     tag_name = re.sub(r'\s+', '_', forum.name.lower())
        #     TAGS[self.forum_id] = tag_name
        # tags = TAGS[self.forum_id]
        # if self.tags:
        #     tags += " %s" % self.tags
        if not self.tags:
            return "forum"
        else:
            return "forum %s" % self.tags.lower()

class Post(models.Model):
    """
    comments on an Entry in a Forum
    """
    body = models.TextField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    entry_id = models.IntegerField()
    post_id = models.IntegerField()
    forum_id = models.IntegerField()
    user_id = models.IntegerField()
    is_informative = models.BooleanField()
    ab_id = models.IntegerField(null = True)

    def get_author(self):
        """returns author of the post, from the Django user table"""
        zendesk_user = User.objects.get(zendesk_user_id = self.user_id)
        return DjangoUser.objects.get(id = zendesk_user.askbot_user_id)

    def get_body_text(self):
        """unescapes html entities in the body text,
        saves in the internal cache and returns the value"""
        if not hasattr(self, '_body_text'):
            self._body_text = unescape(self.body)
        return self._body_text

class Organization(models.Model):
    created_at = models.DateTimeField()
    default = models.CharField(max_length = 255, null=True)
    details = models.TextField(null=True)
    external_id = models.IntegerField(null = True)
    group_id = models.IntegerField(null = True)
    organization_id = models.IntegerField(unique=True)
    is_shared = models.BooleanField()
    is_shared_comments = models.BooleanField()
    name = models.CharField(max_length = 255)
    notes = models.TextField(null=True)
    suspended = models.BooleanField()
    updated_at = models.DateTimeField()

class User(models.Model):
    zendesk_user_id = models.IntegerField()
    askbot_user_id = models.IntegerField(null = True)
    created_at = models.DateTimeField()
    is_active = models.BooleanField()
    last_login = models.DateTimeField(null = True)
    name = models.CharField(max_length = 255)
    openid_url = models.URLField(null = True)
    phone = models.CharField(max_length = 32, null = True)
    restriction_id = models.IntegerField()
    organization_id = models.IntegerField(null=True)
    roles = models.IntegerField()
    time_zone = models.CharField(max_length = 255)
    updated_at = models.DateTimeField()
    uses_12_hour_clock = models.BooleanField()
    email = models.EmailField(null = True)
    is_verified = models.BooleanField()
    photo_url = models.URLField()
    # can't use foreign keys because Zendesk doesn't necessarily remove
    # the user's organization_id if it's deleted which then causes an
    # integrity error when trying to import here
    # organization = models.ForeignKey(Organization, to_field='organization_id', null=True)

class Forum(models.Model):
    description = models.CharField(max_length = 255, null = True)
    display_type_id = models.IntegerField()
    entries_count = models.IntegerField()
    forum_id = models.IntegerField()
    is_locked = models.BooleanField()
    name = models.CharField(max_length = 255)
    organization_id = models.IntegerField(null = True)
    position = models.IntegerField(null = True)
    updated_at = models.DateTimeField()
    translation_locale_id = models.IntegerField(null = True)
    use_for_suggestions = models.BooleanField()
    visibility_restriction_id = models.IntegerField()
    is_public = models.BooleanField()

    def viewable_to_public(self):
        """There are two ways to restrict visibility of the forum. If is_public
        is False, then it's not public, duh. But for
        visibility_restriction_id:
            1=viewable to everyone
            2=viewable to logged in users only
            3=viewable to logged in agents only
        organization_id:
            if not null, this forum is restricted to a specific organization
            on top of other restrictions
        """
        if (not self.is_public or self.visibility_restriction_id != 1 or
            self.organization_id):
            return False
        else:
            return True

class Ticket(models.Model):
    """todo: custom fields"""
    assigned_at = models.DateTimeField(null=True)
    assignee_id = models.IntegerField(null=True)
    base_score = models.IntegerField()
    created_at = models.DateTimeField()
    current_collaborators = models.CharField(max_length = 255, null=True)
    current_tags = models.CharField(max_length = 255, null=True)
    description = models.CharField(max_length = 1000, null=True)
    due_date = models.DateTimeField(null=True)
    entry_id = models.IntegerField(null = True)
    external_id = models.IntegerField(null = True)
    group_id = models.IntegerField(null = True)
    initially_assigned_at = models.DateTimeField(null=True)
    latest_recipients = models.CharField(max_length = 255, null = True)
    ticket_id = models.IntegerField()
    organization_id = models.IntegerField(null = True)
    original_recipient_address = models.CharField(max_length = 255, null = True)
    priority_id = models.IntegerField()
    recipient = models.CharField(max_length = 255, null=True)
    requester_id = models.IntegerField()
    resolution_time = models.IntegerField(null = True)
    solved_at = models.DateTimeField(null=True)
    status_id = models.IntegerField()
    status_updated_at = models.DateTimeField()
    subject = models.CharField(max_length = 255, null=True)
    submitter_id = models.IntegerField()
    ticket_type_id = models.IntegerField()
    updated_at = models.DateTimeField()
    updated_by_type_id = models.IntegerField(null = True)
    via_id = models.IntegerField()
    score = models.IntegerField()
    problem_id = models.IntegerField(null = True)
    has_incidents = models.BooleanField(default = False)
    ab_id = models.IntegerField(null = True)

    def get_author(self):
        """returns author of the comment, from the Django user table"""
        zendesk_user = User.objects.get(zendesk_user_id = self.requester_id)
        return DjangoUser.objects.get(id = zendesk_user.askbot_user_id)

    def get_body_text(self):
        """unescapes html entities in the body text,
        saves in the internal cache and returns the value"""
        if not hasattr(self, '_body_text'):
            self._body_text = unescape(self.description)
        return self._body_text

    def get_tag_names(self):
        if not self.current_tags:
            return "ticket"
        else:
            return "ticket %s" % self.current_tags.lower()

class Comment(models.Model):
    """todo: attachments"""
    author_id = models.IntegerField()
    created_at = models.DateTimeField()
    is_public = models.BooleanField(default = True)
    type = models.CharField(max_length = 255)
    value = models.CharField(max_length = 1000)
    via_id = models.IntegerField()
    ticket_id = models.IntegerField()
    ab_id = models.IntegerField(null = True)

    def get_author(self):
        """returns author of the comment, from the Django user table"""
        zendesk_user = User.objects.get(zendesk_user_id = self.author_id)
        return DjangoUser.objects.get(id = zendesk_user.askbot_user_id)

    def get_body_text(self):
        """unescapes html entities in the body text,
        saves in the internal cache and returns the value"""
        if not hasattr(self, '_body_text'):
            self._body_text = unescape(self.value)
        return self._body_text
