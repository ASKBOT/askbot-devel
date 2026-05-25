"""file utilities for askbot"""
import random
import time
import urllib.parse
from django.core.files.storage import default_storage

def make_file_name(ext, prefix=''):
    name = str(time.time())
    name = name.replace('.', str(random.randint(0,100000)))
    return prefix + name + ext


def store_file(file_name, file_object):
    """Saves a file via the default storage backend and returns its URL."""
    default_storage.save(file_name, file_object)
    file_url = default_storage.url(file_name)
    parsed_url = urllib.parse.urlparse(file_url)
    file_url = urllib.parse.urlunparse(
        urllib.parse.ParseResult(
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            '', '', ''
        )
    )
    return file_url
