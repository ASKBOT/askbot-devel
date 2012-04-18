import datetime
from django.core.management.base import NoArgsCommand
from django.core.urlresolvers import reverse
from django.db import connection
from django.db.models import Q, F
from askbot.models import User, Question, Answer, Tag, PostRevision
from askbot.models import Activity, EmailFeedSetting
from askbot.models import Comment
from askbot.models.question import get_tag_summary_from_questions
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext
from django.conf import settings as django_settings
from askbot.conf import settings as askbot_settings
from django.utils.datastructures import SortedDict
from django.contrib.contenttypes.models import ContentType
from askbot import const
from askbot.utils import mail
from askbot.utils.slug import slugify

DEBUG_THIS_COMMAND = False

def get_all_origin_posts(mentions):
    origin_posts = set()
    for mention in mentions:
        post = mention.content_object
        origin_posts.add(post.get_origin_post())
    return list(origin_posts)

#todo: refactor this as class
def extend_question_list(
                    src, dst, cutoff_time = None, 
                    limit=False, add_mention=False,
                    add_comment = False
                ):
    """src is a query set with questions
    or None
    dst - is an ordered dictionary
    update reporting cutoff time for each question
    to the latest value to be more permissive about updates
    """
    if src is None:#is not QuerySet
        return #will not do anything if subscription of this type is not used
    if limit and len(dst.keys()) >= askbot_settings.MAX_ALERTS_PER_EMAIL:
        return
    if cutoff_time is None:
        if hasattr(src, 'cutoff_time'):
            cutoff_time = src.cutoff_time
        else:
            raise ValueError('cutoff_time is a mandatory parameter')

    for q in src:
        if q in dst:
            meta_data = dst[q]
        else:
            meta_data = {'cutoff_time': cutoff_time}
            dst[q] = meta_data

        if cutoff_time > meta_data['cutoff_time']:
            #the latest cutoff time wins for a given question
            #if the question falls into several subscription groups
            #this makes mailer more eager in sending email
            meta_data['cutoff_time'] = cutoff_time
        if add_mention:
            if 'mentions' in meta_data:
                meta_data['mentions'] += 1
            else:
                meta_data['mentions'] = 1
        if add_comment:
            if 'comments' in meta_data:
                meta_data['comments'] += 1
            else:
                meta_data['comments'] = 1

def format_action_count(string, number, output):
    if number > 0:
        output.append(_(string) % {'num':number})

class Command(NoArgsCommand):
    def handle_noargs(self, **options):
        try:
            try:
                self.send_email_alerts()
            except Exception, e:
                print e
        finally:
            connection.close()

    def get_updated_questions_for_user(self,user):
        """
        retreive relevant question updates for the user
        according to their subscriptions and recorded question
        views
        """

        user_feeds = EmailFeedSetting.objects.filter(
                                                subscriber=user
                                            ).exclude(
                                                frequency__in=('n', 'i')
                                            )

        should_proceed = False
        for feed in user_feeds:
            if feed.should_send_now() == True:
                should_proceed = True
                break

        #shortcircuit - if there is no ripe feed to work on for this user
        if should_proceed == False:
            return {}

        #these are placeholders for separate query sets per question group
        #there are four groups - one for each EmailFeedSetting.feed_type
        #and each group has subtypes A and B
        #that's because of the strange thing commented below
        #see note on Q and F objects marked with todo tag
        q_sel_A = None
        q_sel_B = None

        q_ask_A = None
        q_ask_B = None

        q_ans_A = None
        q_ans_B = None

        q_all_A = None
        q_all_B = None

        #base question query set for this user
        #basic things - not deleted, not closed, not too old
        #not last edited by the same user
        base_qs = Question.objects.exclude(
                                last_activity_by=user
                            ).exclude(
                                last_activity_at__lt=user.date_joined#exclude old stuff
                            ).exclude(
                                deleted=True
                            ).exclude(
                                closed=True
                            ).order_by('-last_activity_at')
        #todo: for some reason filter on did not work as expected ~Q(viewed__who=user) | 
        #      Q(viewed__who=user,viewed__when__lt=F('last_activity_at'))
        #returns way more questions than you might think it should
        #so because of that I've created separate query sets Q_set2 and Q_set3
        #plus two separate queries run faster!

        #build two two queries based

        #questions that are not seen by the user at all
        not_seen_qs = base_qs.filter(~Q(viewed__who=user))
        #questions that were seen, but before last modification
        seen_before_last_mod_qs = base_qs.filter(
                                    Q(
                                        viewed__who=user,
                                        viewed__when__lt=F('last_activity_at')
                                    )
                                )

        #shorten variables for convenience
        Q_set_A = not_seen_qs
        Q_set_B = seen_before_last_mod_qs

        for feed in user_feeds:
            if feed.feed_type == 'm_and_c':
                #alerts on mentions and comments are processed separately
                #because comments to questions do not trigger change of last_updated
                #this may be changed in the future though, see
                #http://askbot.org/en/question/96/
                continue

            #each group of updates represented by the corresponding
            #query set has it's own cutoff time
            #that cutoff time is computed for each user individually
            #and stored as a parameter "cutoff_time"

            #we won't send email for a given question if an email has been
            #sent after that cutoff_time
            if feed.should_send_now():
                if DEBUG_THIS_COMMAND == False:
                    feed.mark_reported_now()
                cutoff_time = feed.get_previous_report_cutoff_time() 

                if feed.feed_type == 'q_sel':
                    q_sel_A = Q_set_A.filter(followed_by=user)
                    q_sel_A.cutoff_time = cutoff_time #store cutoff time per query set
                    q_sel_B = Q_set_B.filter(followed_by=user)
                    q_sel_B.cutoff_time = cutoff_time #store cutoff time per query set

                elif feed.feed_type == 'q_ask':
                    q_ask_A = Q_set_A.filter(author=user)
                    q_ask_A.cutoff_time = cutoff_time
                    q_ask_B = Q_set_B.filter(author=user)
                    q_ask_B.cutoff_time = cutoff_time

                elif feed.feed_type == 'q_ans':
                    q_ans_A = Q_set_A.filter(answers__author=user)
                    q_ans_A = q_ans_A[:askbot_settings.MAX_ALERTS_PER_EMAIL]
                    q_ans_A.cutoff_time = cutoff_time

                    q_ans_B = Q_set_B.filter(answers__author=user)
                    q_ans_B = q_ans_B[:askbot_settings.MAX_ALERTS_PER_EMAIL]
                    q_ans_B.cutoff_time = cutoff_time

                elif feed.feed_type == 'q_all':
                    q_all_A = user.get_tag_filtered_questions(Q_set_A)
                    q_all_B = user.get_tag_filtered_questions(Q_set_B)

                    q_all_A = q_all_A[:askbot_settings.MAX_ALERTS_PER_EMAIL]
                    q_all_B = q_all_B[:askbot_settings.MAX_ALERTS_PER_EMAIL]
                    q_all_A.cutoff_time = cutoff_time
                    q_all_B.cutoff_time = cutoff_time

        #build ordered list questions for the email report
        q_list = SortedDict()

        #todo: refactor q_list into a separate class?
        extend_question_list(q_sel_A, q_list)
        extend_question_list(q_sel_B, q_list)

        #build list of comment and mention responses here
        #it is separate because posts are not marked as changed
        #when people add comments
        #mention responses could be collected in the loop above, but
        #it is inconvenient, because feed_type m_and_c bundles the two
        #also we collect metadata for these here
        try:
            feed = user_feeds.get(feed_type='m_and_c')
            if feed.should_send_now():
                cutoff_time = feed.get_previous_report_cutoff_time()
                comments = Comment.objects.filter(
                                            added_at__lt = cutoff_time,
                                        ).exclude(
                                            user = user
                                        )
                q_commented = list() 
                for c in comments:
                    post = c.content_object
                    if post.author != user:
                        continue

                    #skip is post was seen by the user after
                    #the comment posting time
                    q_commented.append(post.get_origin_post())

                extend_question_list(
                                q_commented,
                                q_list,
                                cutoff_time = cutoff_time,
                                add_comment = True
                            )

                mentions = Activity.objects.get_mentions(
                                                    mentioned_at__lt = cutoff_time,
                                                    mentioned_whom = user
                                                )

                #print 'have %d mentions' % len(mentions)
                #MM = Activity.objects.filter(activity_type = const.TYPE_ACTIVITY_MENTION)
                #print 'have %d total mentions' % len(MM)
                #for m in MM:
                #    print m

                mention_posts = get_all_origin_posts(mentions)
                q_mentions_id = [q.id for q in mention_posts]

                q_mentions_A = Q_set_A.filter(id__in = q_mentions_id)
                q_mentions_A.cutoff_time = cutoff_time
                extend_question_list(q_mentions_A, q_list, add_mention=True)

                q_mentions_B = Q_set_B.filter(id__in = q_mentions_id)
                q_mentions_B.cutoff_time = cutoff_time
                extend_question_list(q_mentions_B, q_list, add_mention=True)
        except EmailFeedSetting.DoesNotExist:
            pass

        if user.email_tag_filter_strategy == const.INCLUDE_INTERESTING:
            extend_question_list(q_all_A, q_list)
            extend_question_list(q_all_B, q_list)

        extend_question_list(q_ask_A, q_list, limit=True)
        extend_question_list(q_ask_B, q_list, limit=True)

        extend_question_list(q_ans_A, q_list, limit=True)
        extend_question_list(q_ans_B, q_list, limit=True)

        if user.email_tag_filter_strategy == const.EXCLUDE_IGNORED:
            extend_question_list(q_all_A, q_list, limit=True)
            extend_question_list(q_all_B, q_list, limit=True)

        ctype = ContentType.objects.get_for_model(Question)
        EMAIL_UPDATE_ACTIVITY = const.TYPE_ACTIVITY_EMAIL_UPDATE_SENT

        #up to this point we still don't know if emails about
        #collected questions were sent recently
        #the next loop examines activity record and decides
        #for each question, whether it needs to be included or not
        #into the report

        for q, meta_data in q_list.items():
            #this loop edits meta_data for each question
            #so that user will receive counts on new edits new answers, etc
            #and marks questions that need to be skipped
            #because an email about them was sent recently enough

            #also it keeps a record of latest email activity per question per user
            try:
                #todo: is it possible to use content_object here, instead of
                #content type and object_id pair?
                update_info = Activity.objects.get(
                                            user=user,
                                            content_type=ctype,
                                            object_id=q.id,
                                            activity_type=EMAIL_UPDATE_ACTIVITY
                                        )
                emailed_at = update_info.active_at
            except Activity.DoesNotExist:
                update_info = Activity(
                                        user=user, 
                                        content_object=q, 
                                        activity_type=EMAIL_UPDATE_ACTIVITY
                                    )
                emailed_at = datetime.datetime(1970, 1, 1)#long time ago
            except Activity.MultipleObjectsReturned:
                raise Exception(
                                'server error - multiple question email activities '
                                'found per user-question pair'
                                )

            cutoff_time = meta_data['cutoff_time']#cutoff time for the question

            #skip question if we need to wait longer because
            #the delay before the next email has not yet elapsed
            #or if last email was sent after the most recent modification
            if emailed_at > cutoff_time or emailed_at > q.last_activity_at:
                meta_data['skip'] = True
                continue

            #collect info on all sorts of news that happened after
            #the most recent emailing to the user about this question
            q_rev = PostRevision.objects.question_revisions().filter(
                                                question=q,
                                                revised_at__gt=emailed_at
                                            )

            q_rev = q_rev.exclude(author=user)

            #now update all sorts of metadata per question
            meta_data['q_rev'] = len(q_rev)
            if len(q_rev) > 0 and q.added_at == q_rev[0].revised_at:
                meta_data['q_rev'] = 0
                meta_data['new_q'] = True
            else:
                meta_data['new_q'] = False
                
            new_ans = Answer.objects.filter(
                                            question=q,
                                            added_at__gt=emailed_at,
                                            deleted=False,
                                        )

            new_ans = new_ans.exclude(author=user)
            meta_data['new_ans'] = len(new_ans)
            ans_rev = PostRevision.objects.answer_revisions().filter(
                                            answer__question = q,
                                            answer__deleted = False,
                                            revised_at__gt = emailed_at
                                        )
            ans_rev = ans_rev.exclude(author=user)
            meta_data['ans_rev'] = len(ans_rev)

            comments = meta_data.get('comments', 0)
            mentions = meta_data.get('mentions', 0)

            #print meta_data
            #finally skip question if there are no news indeed
            if len(q_rev) + len(new_ans) + len(ans_rev) + comments + mentions == 0:
                meta_data['skip'] = True
                #print 'skipping'
            else:
                meta_data['skip'] = False
                #print 'not skipping'
                update_info.active_at = datetime.datetime.now() 
                if DEBUG_THIS_COMMAND == False:
                    update_info.save() #save question email update activity 
        #q_list is actually an ordered dictionary
        #print 'user %s gets %d' % (user.username, len(q_list.keys()))
        #todo: sort question list by update time
        return q_list 

    def send_email_alerts(self):
        #does not change the database, only sends the email
        #todo: move this to template
        for user in User.objects.all():
            user.add_missing_askbot_subscriptions()
            #todo: q_list is a dictionary, not a list
            q_list = self.get_updated_questions_for_user(user)
            if len(q_list.keys()) == 0:
                continue
            num_q = 0
            for question, meta_data in q_list.items():
                if meta_data['skip']:
                    del q_list[question]
                else:
                    num_q += 1
            if num_q > 0:
                url_prefix = askbot_settings.APP_URL

                tag_summary = get_tag_summary_from_questions(q_list.keys())
                question_count = len(q_list.keys())

                subject_line = ungettext(
                    '%(question_count)d updated question about %(topics)s',
                    '%(question_count)d updated questions about %(topics)s',
                    question_count
                ) % {
                    'question_count': question_count,
                    'topics': tag_summary
                }

                #todo: send this to special log
                #print 'have %d updated questions for %s' % (num_q, user.username)
                text = ungettext('%(name)s, this is an update message header for %(num)d question', 
                            '%(name)s, this is an update message header for %(num)d questions',num_q) \
                                % {'num':num_q, 'name':user.username}

                text += '<ul>'
                items_added = 0
                items_unreported = 0
                for q, meta_data in q_list.items():
                    act_list = []
                    if meta_data['skip']:
                        continue
                    if items_added >= askbot_settings.MAX_ALERTS_PER_EMAIL:
                        items_unreported = num_q - items_added #may be inaccurate actually, but it's ok
                        
                    else:
                        items_added += 1
                        if meta_data['new_q']:
                            act_list.append(_('new question'))
                        format_action_count('%(num)d rev', meta_data['q_rev'],act_list)
                        format_action_count('%(num)d ans', meta_data['new_ans'],act_list)
                        format_action_count('%(num)d ans rev',meta_data['ans_rev'],act_list)
                        act_token = ', '.join(act_list)
                        text += '<li><a href="%s?sort=latest">%s</a> <font color="#777777">(%s)</font></li>' \
                                    % (url_prefix + q.get_absolute_url(), q.title, act_token)
                text += '</ul>'
                text += '<p></p>'
                #if len(q_list.keys()) >= askbot_settings.MAX_ALERTS_PER_EMAIL:
                #    text += _('There may be more questions updated since '
                #                'you have logged in last time as this list is '
                #                'abridged for your convinience. Please visit '
                #                'the askbot and see what\'s new!<br>'
                #              )

                text += _(
                            'Please visit the askbot and see what\'s new! '
                            'Could you spread the word about it - '
                            'can somebody you know help answering those questions or '
                            'benefit from posting one?'
                        )

                feeds = EmailFeedSetting.objects.filter(subscriber = user)
                feed_freq = [feed.frequency for feed in feeds]
                text += '<p></p>'
                if 'd' in feed_freq:
                    text += _('Your most frequent subscription setting is \'daily\' '
                               'on selected questions. If you are receiving more than one '
                               'email per day'
                               'please tell about this issue to the askbot administrator.'
                               )
                elif 'w' in feed_freq:
                    text += _('Your most frequent subscription setting is \'weekly\' '
                               'if you are receiving this email more than once a week '
                               'please report this issue to the askbot administrator.'
                               )
                text += ' '
                text += _(
                            'There is a chance that you may be receiving links seen '
                            'before - due to a technicality that will eventually go away. '
                        )

                link = url_prefix + reverse(
                                        'user_subscriptions', 
                                        kwargs = {
                                            'id': user.id,
                                            'slug': slugify(user.username)
                                        }
                                    )

                text += _(
                    'go to %(email_settings_link)s to change '
                    'frequency of email updates or '
                    '%(admin_email)s administrator'
                ) % {
                    'email_settings_link': link,
                    'admin_email': django_settings.ADMINS[0][1]
                }
                if DEBUG_THIS_COMMAND == True:
                    recipient_email = django_settings.ADMINS[0][1]
                else:
                    recipient_email = user.email

                mail.send_mail(
                    subject_line = subject_line,
                    body_text = text,
                    recipient_list = [recipient_email]
                )
