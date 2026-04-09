"""Train the dual Bayesian spam filter models.

Usage:
    python manage.py askbot_train_spam_filter --from-db
    python manage.py askbot_train_spam_filter --input spam-ham.json
    python manage.py askbot_train_spam_filter --input spam-ham.json --model spam
"""
import json
import os

from django.conf import settings as django_settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Train the Bayesian spam filter (spam and/or ham models)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--from-db', action='store_true', default=False,
            help='Train from live database (blocked users = spam, approved users = ham)'
        )
        parser.add_argument(
            '--input', dest='input_file', default=None,
            help='Path to JSON file from askbot_get_spam_training_set'
        )
        parser.add_argument(
            '--model', choices=['spam', 'ham', 'both'], default='both',
            help='Which model(s) to train (default: both)'
        )

    def handle(self, *args, **kwargs):
        from_db = kwargs['from_db']
        input_file = kwargs['input_file']
        model_choice = kwargs['model']

        if not from_db and not input_file:
            raise CommandError('Specify --from-db or --input FILE')

        if from_db and input_file:
            raise CommandError('Specify only one of --from-db or --input')

        if input_file:
            spam_texts, ham_texts = self._load_from_file(input_file)
        else:
            spam_texts, ham_texts = self._load_from_db()

        self.stdout.write(f'Spam examples: {len(spam_texts)}')
        self.stdout.write(f'Ham examples: {len(ham_texts)}')

        if model_choice in ('spam', 'both'):
            if len(spam_texts) < 10:
                self.stderr.write('WARNING: Very few spam examples, model may be unreliable')
            self._train_model('spam', spam_texts, ham_texts)

        if model_choice in ('ham', 'both'):
            if len(ham_texts) < 10:
                self.stderr.write('WARNING: Very few ham examples, model may be unreliable')
            self._train_model('ham', ham_texts, spam_texts)

        self.stdout.write(self.style.SUCCESS('Training complete.'))

    def _load_from_file(self, path):
        if not os.path.exists(path):
            raise CommandError(f'File not found: {path}')
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('spam', []), data.get('ham', [])

    def _load_from_db(self):
        from askbot.models import Post, User
        from askbot import const

        self.stdout.write('Loading training data from database...')

        from django.db.models import Count
        spam_users = User.objects.filter(
            askbot_profile__reputation=const.MIN_REPUTATION,
            askbot_profile__status='b'
        ).annotate(post_count=Count('posts')).filter(post_count=1)
        spam_posts = Post.objects.filter(
            author__in=spam_users,
            post_type__in=('question', 'answer', 'comment')
        ).only('text')
        spam_texts = [p.text for p in spam_posts]

        ham_users = User.objects.filter(
            askbot_profile__reputation__gte=10
        ).order_by('-askbot_profile__reputation')
        ham_posts = Post.objects.filter(
            author__in=ham_users,
            post_type__in=('question', 'answer', 'comment')
        ).only('text')[:3000]
        ham_texts = [p.text for p in ham_posts]

        return spam_texts, ham_texts

    def _train_model(self, model_type, positive_texts, negative_texts):
        import numpy as np
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.model_selection import train_test_split
        from sklearn.naive_bayes import MultinomialNB
        from sklearn.metrics import classification_report

        self.stdout.write(f'\nTraining {model_type} model...')

        all_texts = positive_texts + negative_texts
        labels = np.array([1] * len(positive_texts) + [0] * len(negative_texts))

        X_train_text, X_test_text, y_train, y_test = train_test_split(
            all_texts, labels, test_size=0.2, random_state=42, stratify=labels
        )

        vectorizer = TfidfVectorizer(
            max_features=50000,
            ngram_range=(1, 2),
            min_df=2
        )
        X_train = vectorizer.fit_transform(X_train_text)
        X_test = vectorizer.transform(X_test_text)

        classifier = MultinomialNB(alpha=0.1)
        classifier.fit(X_train, y_train)

        y_pred = classifier.predict(X_test)
        report = classification_report(y_test, y_pred, target_names=['negative', 'positive'])
        self.stdout.write(f'\n{model_type.upper()} model evaluation:\n{report}')

        import joblib
        model_dir = os.path.join(django_settings.MEDIA_ROOT, 'spam_filter')
        os.makedirs(model_dir, exist_ok=True)

        vec_path = os.path.join(model_dir, f'{model_type}_vectorizer.joblib')
        clf_path = os.path.join(model_dir, f'{model_type}_classifier.joblib')
        joblib.dump(vectorizer, vec_path)
        joblib.dump(classifier, clf_path)
        self.stdout.write(f'Saved {model_type} model to {model_dir}')
