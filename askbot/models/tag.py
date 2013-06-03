import re
from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.conf import settings
from askbot.models.base import BaseQuerySetManager
from askbot import const
from askbot.conf import settings as askbot_settings
from askbot.utils import category_tree

def delete_tags(tags):
    """deletes tags in the list"""
    tag_ids = [tag.id for tag in tags]
    Tag.objects.filter(id__in = tag_ids).delete()

def get_tags_by_names(tag_names):
    """returns query set of tags
    and a set of tag names that were not found
    """
    tags = Tag.objects.filter(name__in = tag_names)
    #if there are brand new tags, create them
    #and finalize the added tag list
    if tags.count() < len(tag_names):
        found_tag_names = set([tag.name for tag in tags])
        new_tag_names = set(tag_names) - found_tag_names
    else:
        new_tag_names = set()

    return tags, new_tag_names

def filter_tags_by_status(tags, status = None):
    """returns a list or a query set of tags which are accepted"""
    if isinstance(tags, models.query.QuerySet):
        return tags.filter(status = status)
    else:
        return [tag for tag in tags if tag.status == status]

def filter_accepted_tags(tags):
    return filter_tags_by_status(tags, status = Tag.STATUS_ACCEPTED)

def filter_suggested_tags(tags):
    return filter_tags_by_status(tags, status = Tag.STATUS_SUGGESTED)

def format_personal_group_name(user):
    #todo: after migration of groups away from tags,
    #this function will be moved somewhere else
    from askbot.models.user import PERSONAL_GROUP_NAME_PREFIX as prefix
    return '%s%d' % (prefix, user.id)

def is_preapproved_tag_name(tag_name):
    """true if tag name is in the category tree
    or any other container of preapproved tags"""
    #get list of preapproved tags, to make exceptions for
    if askbot_settings.TAG_SOURCE == 'category-tree':
        return tag_name in category_tree.get_leaf_names()
    return False

def separate_unused_tags(tags):
    """returns two lists::
    * first where tags whose use counts are >0
    * second - with use counts == 0
    """
    used = list()
    unused = list()
    for tag in tags:
        if tag.used_count == 0:
            unused.append(tag)
        else:
            assert(tag.used_count > 0)
            used.append(tag)
    return used, unused

def tags_match_some_wildcard(tag_names, wildcard_tags):
    """Same as
    :meth:`~askbot.models.tag.TagQuerySet.tags_match_some_wildcard`
    except it works on tag name strings
    """
    for tag_name in tag_names:
        for wildcard_tag in sorted(wildcard_tags):
            if tag_name.startswith(wildcard_tag[:-1]):
                return True
    return False

def get_mandatory_tags():
    """returns list of mandatory tags,
    or an empty list, if there aren't any"""
    from askbot.conf import settings as askbot_settings
    #TAG_SOURCE setting is hidden
    #and only is accessible via livesettings overrides
    if askbot_settings.TAG_SOURCE == 'category-tree':
        return []#hack: effectively we disable the mandatory tags feature
    else:
        #todo - in the future clean this up
        #we might need to have settings:
        #* prepopulated tags - json structure - either a flat list or a tree
        #  if structure is tree - then use some multilevel selector for choosing tags
        #  if it is a list - then make users click on tags to select them
        #* use prepopulated tags (boolean)
        #* tags are required
        #* regular users can create tags (boolean)
        #the category tree and the mandatory tag lists can be merged
        #into the same setting - and mandatory tags should use json
        #keep in mind that in the future multiword tags will be allowed
        raw_mandatory_tags = askbot_settings.MANDATORY_TAGS.strip()
        if len(raw_mandatory_tags) == 0:
            return []
        else:
            split_re = re.compile(const.TAG_SPLIT_REGEX)
            return split_re.split(raw_mandatory_tags)


class TagQuerySet(models.query.QuerySet):
    def get_valid_tags(self, page_size):
        tags = self.all().filter(deleted=False).exclude(used_count=0).order_by("-id")[:page_size]
        return tags

    def update_use_counts(self, tags):
        """Updates the given Tags with their current use counts."""
        for tag in tags:
            tag.used_count = tag.threads.count()
            tag.save()

    def mark_undeleted(self):
        """removes deleted(+at/by) marks"""
        self.update(#undelete them
            deleted = False,
            deleted_by = None,
            deleted_at = None
        )

    def tags_match_some_wildcard(self, wildcard_tags = None):
        """True if any one of the tags in the query set
        matches a wildcard

        :arg:`wildcard_tags` is an iterable of wildcard tag strings

        todo: refactor to use :func:`tags_match_some_wildcard`
        """
        for tag in self.all():
            for wildcard_tag in sorted(wildcard_tags):
                if tag.name.startswith(wildcard_tag[:-1]):
                    return True
        return False

    def get_by_wildcards(self, wildcards = None):
        """returns query set of tags that match the wildcard tags
        wildcard tag is guaranteed to end with an asterisk and has
        at least one character preceding the the asterisk. and there
        is only one asterisk in the entire name
        """
        if wildcards is None or len(wildcards) == 0:
            return self.none()
        first_tag = wildcards.pop()
        tag_filter = models.Q(name__startswith = first_tag[:-1])
        for next_tag in wildcards:
            tag_filter |= models.Q(name__startswith = next_tag[:-1])
        return self.filter(tag_filter)

    def get_related_to_search(self, threads, ignored_tag_names):
        """Returns at least tag names, along with use counts"""
        tags = self.filter(threads__in=threads).annotate(local_used_count=models.Count('id')).order_by('-local_used_count', 'name')
        if ignored_tag_names:
            tags = tags.exclude(name__in=ignored_tag_names)
        tags = tags.exclude(deleted = True)
        return list(tags[:50])


class TagManager(BaseQuerySetManager):
    """chainable custom filter query set manager
    for :class:``~askbot.models.Tag`` objects
    """
    def get_query_set(self):
        return TagQuerySet(self.model)

    def get_content_tags(self):
        """temporary function that filters out the group tags"""
        return self.all()

    def create(self, name=None, created_by=None, **kwargs):
        """Creates a new tag"""
        if created_by.can_create_tags() or is_preapproved_tag_name(name):
            status = Tag.STATUS_ACCEPTED
        else:
            status = Tag.STATUS_SUGGESTED

        kwargs['created_by'] = created_by
        kwargs['name'] = name
        kwargs['status'] = status

        return super(TagManager, self).create(**kwargs)

    def create_suggested_tag(self, tag_names = None, user = None):
        """This function is not used, and will probably need
        to be retired. In the previous version we were sending
        email to admins when the new tags were created,
        now we have a separate page where new tags are listed.
        """
        #todo: stuff below will probably go after
        #tag moderation actions are implemented
        from askbot import mail
        from askbot.mail import messages
        body_text = messages.notify_admins_about_new_tags(
                                tags = tag_names,
                                user = user,
                                thread = self
                            )
        site_name = askbot_settings.APP_SHORT_NAME
        subject_line = _('New tags added to %s') % site_name
        mail.mail_moderators(
            subject_line,
            body_text,
            headers = {'Reply-To': user.email}
        )

        msg = _(
            'Tags %s are new and will be submitted for the '
            'moderators approval'
        ) % ', '.join(tag_names)
        user.message_set.create(message = msg)

    def create_in_bulk(self, tag_names = None, user = None):
        """creates tags by names. If user can create tags,
        then they are set status ``STATUS_ACCEPTED``,
        otherwise the status will be set to ``STATUS_SUGGESTED``.

        One exception: if suggested tag is in the category tree
        and source of tags is category tree - then status of newly
        created tag is ``STATUS_ACCEPTED``
        """

        #load suggested tags
        pre_suggested_tags = self.filter(
            name__in = tag_names, status = Tag.STATUS_SUGGESTED
        )

        #deal with suggested tags
        if user.can_create_tags():
            #turn previously suggested tags into accepted
            pre_suggested_tags.update(status = Tag.STATUS_ACCEPTED)
        else:
            #increment use count and add user to "suggested_by"
            for tag in pre_suggested_tags:
                tag.times_used += 1
                tag.suggested_by.add(user)
                tag.save()

        created_tags = list()
        pre_suggested_tag_names = list()
        for tag in pre_suggested_tags:
            pre_suggested_tag_names.append(tag.name)
            created_tags.append(tag)

        for tag_name in set(tag_names) - set(pre_suggested_tag_names):
            #status for the new tags is automatically set within the create()
            new_tag = Tag.objects.create(name = tag_name, created_by = user)
            created_tags.append(new_tag)

            if new_tag.status == Tag.STATUS_SUGGESTED:
                new_tag.suggested_by.add(user)

        return created_tags

def clean_group_name(name):
    """todo: move to the models/user.py
    group names allow spaces,
    tag names do not, so we use this method
    to replace spaces with dashes"""
    return re.sub('\s+', '-', name.strip())

class Tag(models.Model):
    #a couple of status constants
    STATUS_SUGGESTED = 0
    STATUS_ACCEPTED = 1

    name = models.CharField(max_length=255, unique=True)
    created_by = models.ForeignKey(User, related_name='created_tags')

    suggested_by = models.ManyToManyField(
        User, related_name='suggested_tags',
        help_text = 'Works only for suggested tags for tag moderation'
    )

    status = models.SmallIntegerField(default = STATUS_ACCEPTED)

    # Denormalised data
    used_count = models.PositiveIntegerField(default=0)

    deleted     = models.BooleanField(default=False)
    deleted_at  = models.DateTimeField(null=True, blank=True)
    deleted_by  = models.ForeignKey(User, null=True, blank=True, related_name='deleted_tags')

    tag_wiki = models.OneToOneField(
                                'Post',
                                null=True,
                                related_name = 'described_tag'
                            )

    objects = TagManager()

    class Meta:
        app_label = 'askbot'
        db_table = u'tag'
        ordering = ('-used_count', 'name')

    def __unicode__(self):
        return self.name

class MarkedTag(models.Model):
    TAG_MARK_REASONS = (
        ('good', ugettext_lazy('interesting')),
        ('bad', ugettext_lazy('ignored')),
        ('subscribed', ugettext_lazy('subscribed')),
    )
    tag = models.ForeignKey('Tag', related_name='user_selections')
    user = models.ForeignKey(User, related_name='tag_selections')
    reason = models.CharField(max_length=16, choices=TAG_MARK_REASONS)

    class Meta:
        app_label = 'askbot'


class TagSynonym(models.Model):

    source_tag_name = models.CharField(max_length=255, unique=True)
    target_tag_name = models.CharField(max_length=255, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    owned_by = models.ForeignKey(User, related_name='tag_synonyms')
    auto_rename_count = models.IntegerField(default=0)
    last_auto_rename_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'askbot'

    def __unicode__(self):
        return u'%s -> %s' % (self.source_tag_name, self.target_tag_name)
        
