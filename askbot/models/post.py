from django.db import models
from django.core.exceptions import ValidationError

from askbot.utils import markup
from askbot.utils.html import sanitize_html

#class Post(models.Model):
#    pass

class PostRevisionManager(models.Manager):
    def create(self, *kargs, **kwargs):
        raise NotImplementedError  # Prevent accidental creation of PostRevision instance without `revision_type` set

    def create_question_revision(self, *kargs, **kwargs):
        kwargs['revision_type'] = self.model.QUESTION_REVISION
        return super(PostRevisionManager, self).create(*kargs, **kwargs)

    def create_answer_revision(self, *kargs, **kwargs):
        kwargs['revision_type'] = self.model.ANSWER_REVISION
        return super(PostRevisionManager, self).create(*kargs, **kwargs)

    def question_revisions(self):
        return self.filter(revision_type=self.model.QUESTION_REVISION)

    def answer_revisions(self):
        return self.filter(revision_type=self.model.ANSWER_REVISION)


class PostRevision(models.Model):
    QUESTION_REVISION_TEMPLATE_NO_TAGS = (
        '<h3>%(title)s</h3>\n'
        '<div class="text">%(html)s</div>\n'
    )

    QUESTION_REVISION = 1
    ANSWER_REVISION = 2
    REVISION_TYPE_CHOICES = (
        (QUESTION_REVISION, 'question'),
        (ANSWER_REVISION, 'answer'),
    )
    REVISION_TYPE_CHOICES_DICT = dict(REVISION_TYPE_CHOICES)

    answer = models.ForeignKey('askbot.Answer', related_name='revisions', null=True, blank=True)
    question = models.ForeignKey('askbot.Question', related_name='revisions', null=True, blank=True)

    revision_type = models.SmallIntegerField(choices=REVISION_TYPE_CHOICES)

    revision   = models.PositiveIntegerField()
    author     = models.ForeignKey('auth.User', related_name='%(class)ss')
    revised_at = models.DateTimeField()
    summary    = models.CharField(max_length=300, blank=True)
    text       = models.TextField()

    # Question-specific fields
    title      = models.CharField(max_length=300, blank=True, default='')
    tagnames   = models.CharField(max_length=125, blank=True, default='')
    is_anonymous = models.BooleanField(default=False)

    objects = PostRevisionManager()

    class Meta:
        # INFO: This `unique_together` constraint might be problematic for databases in which
        #       2+ NULLs cannot be stored in an UNIQUE column.
        #       As far as I know MySQL, PostgreSQL and SQLite allow that so we're on the safe side.
        unique_together = (('answer', 'revision'), ('question', 'revision'))
        ordering = ('-revision',)
        app_label = 'askbot'

    def revision_type_str(self):
        return self.REVISION_TYPE_CHOICES_DICT[self.revision_type]

    def __unicode__(self):
        return u'%s - revision %s of %s' % (self.revision_type_str(), self.revision, self.title)

    def parent(self):
        if self.is_question_revision():
            return self.question
        elif self.is_answer_revision():
            return self.answer

    def clean(self):
        "Internal cleaning method, called from self.save() by self.full_clean()"
        if bool(self.question) == bool(self.answer): # one and only one has to be set (!xor)
            raise ValidationError('One (and only one) of question/answer fields has to be set.')
        if (self.question and not self.is_question_revision()) or (self.answer and not self.is_answer_revision()):
            raise ValidationError('Revision_type doesn`t match values in question/answer fields.')

    def save(self, **kwargs):
        # Determine the revision number, if not set
        if not self.revision:
            # TODO: Maybe use Max() aggregation? Or `revisions.count() + 1`
            self.revision = self.parent().revisions.values_list('revision', flat=True)[0] + 1

        # Make sure that everything is ok, in particular that `revision_type` and `revision` are set to valid values
        self.full_clean()

        super(PostRevision, self).save(**kwargs)

    def is_question_revision(self):
        return self.revision_type == self.QUESTION_REVISION

    def is_answer_revision(self):
        return self.revision_type == self.ANSWER_REVISION

    @models.permalink
    def get_absolute_url(self):
        if self.is_question_revision():
            return 'question_revisions', (self.question.id,), {}
        elif self.is_answer_revision():
            return 'answer_revisions', (), {'id':self.answer.id}

    def get_question_title(self):
        #INFO: ack-grepping shows that it's only used for Questions, so there's no code for Answers
        return self.question.title

    def as_html(self, **kwargs):
        markdowner = markup.get_parser()
        sanitized_html = sanitize_html(markdowner.convert(self.text))

        if self.is_question_revision():
            return self.QUESTION_REVISION_TEMPLATE_NO_TAGS % {
                'title': self.title,
                'html': sanitized_html
            }
        elif self.is_answer_revision():
            return sanitized_html
