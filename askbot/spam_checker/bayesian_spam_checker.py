"""Dual Bayesian spam filter with independent spam and ham models.

The spam model detects spam content; the ham model detects legitimate content.
Together they provide a dual-check: content that matches spam but also matches
ham gets the benefit of the doubt (the ham model "rescues" the post).

Models are loaded lazily from disk (joblib) and cached at module level.
Thread-safe via threading.Lock.

Fails open: if models are not found, is_spam returns False and is_ham returns False.
"""
import logging
import os
import threading

from django.conf import settings as django_settings

LOG = logging.getLogger(__name__)

_lock = threading.Lock()
_spam_vectorizer = None
_spam_classifier = None
_ham_vectorizer = None
_ham_classifier = None
_models_loaded = False


def _get_model_dir():
    """Return the directory where model files are stored."""
    media_root = getattr(django_settings, 'MEDIA_ROOT', '')
    return os.path.join(media_root, 'spam_filter')


def _load_models():
    """Load all models from disk. Called once, lazily."""
    global _spam_vectorizer, _spam_classifier
    global _ham_vectorizer, _ham_classifier
    global _models_loaded

    model_dir = _get_model_dir()
    try:
        import joblib
        spam_vec_path = os.path.join(model_dir, 'spam_vectorizer.joblib')
        spam_clf_path = os.path.join(model_dir, 'spam_classifier.joblib')
        ham_vec_path = os.path.join(model_dir, 'ham_vectorizer.joblib')
        ham_clf_path = os.path.join(model_dir, 'ham_classifier.joblib')

        if os.path.exists(spam_vec_path) and os.path.exists(spam_clf_path):
            _spam_vectorizer = joblib.load(spam_vec_path)
            _spam_classifier = joblib.load(spam_clf_path)
            LOG.info('Spam model loaded from %s', model_dir)
        else:
            LOG.warning('Spam model files not found in %s', model_dir)

        if os.path.exists(ham_vec_path) and os.path.exists(ham_clf_path):
            _ham_vectorizer = joblib.load(ham_vec_path)
            _ham_classifier = joblib.load(ham_clf_path)
            LOG.info('Ham model loaded from %s', model_dir)
        else:
            LOG.warning('Ham model files not found in %s', model_dir)

    except Exception:
        LOG.exception('Error loading spam filter models from %s', model_dir)

    _models_loaded = True


def _ensure_loaded():
    """Ensure models are loaded (thread-safe lazy init)."""
    global _models_loaded
    if not _models_loaded:
        with _lock:
            if not _models_loaded:
                _load_models()


def reload_models():
    """Force re-read models from disk."""
    global _models_loaded
    with _lock:
        _models_loaded = False
    _ensure_loaded()


def is_spam(text, **kwargs):
    """Check if text is spam. Conforms to the spam checker plugin interface.

    Returns True if the spam model classifies the text as spam.
    Returns False if the model is not loaded (fails open).
    """
    _ensure_loaded()
    if _spam_vectorizer is None or _spam_classifier is None:
        return False
    try:
        features = _spam_vectorizer.transform([text])
        prediction = _spam_classifier.predict(features)[0]
        return bool(prediction == 1)
    except Exception:
        LOG.exception('Error in spam classification')
        return False


def is_ham(text):
    """Check if text matches the ham (legitimate content) model.

    Returns True if the ham model classifies the text as ham.
    Returns False if the model is not loaded (fails open).
    """
    _ensure_loaded()
    if _ham_vectorizer is None or _ham_classifier is None:
        return False
    try:
        features = _ham_vectorizer.transform([text])
        prediction = _ham_classifier.predict(features)[0]
        return bool(prediction == 1)
    except Exception:
        LOG.exception('Error in ham classification')
        return False


def check_content(text):
    """Dual-check: returns (spam_detected, ham_detected) tuple."""
    return (is_spam(text), is_ham(text))


def retrain_spam_incremental(texts):
    """Incrementally train the spam model with new spam examples using partial_fit."""
    _ensure_loaded()
    if _spam_vectorizer is None or _spam_classifier is None:
        LOG.warning('Cannot retrain spam model: model not loaded')
        return
    try:
        import numpy as np
        features = _spam_vectorizer.transform(texts)
        labels = np.ones(len(texts), dtype=int)
        _spam_classifier.partial_fit(features, labels)
        LOG.info('Spam model incrementally updated with %d examples', len(texts))
    except Exception:
        LOG.exception('Error in incremental spam retraining')


def retrain_ham_incremental(texts):
    """Incrementally train the ham model with new ham examples using partial_fit."""
    _ensure_loaded()
    if _ham_vectorizer is None or _ham_classifier is None:
        LOG.warning('Cannot retrain ham model: model not loaded')
        return
    try:
        import numpy as np
        features = _ham_vectorizer.transform(texts)
        labels = np.ones(len(texts), dtype=int)
        _ham_classifier.partial_fit(features, labels)
        LOG.info('Ham model incrementally updated with %d examples', len(texts))
    except Exception:
        LOG.exception('Error in incremental ham retraining')
