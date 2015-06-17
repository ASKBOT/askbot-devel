"""file utilities for askbot"""
import os
import random
import time
import urlparse
from django.core.files.storage import get_storage_class
from django.conf import settings as django_settings

def make_file_name(ext, prefix=''):
    name = str(
            time.time()
        ).replace(
            '.', str(random.randint(0,100000))
        )
    return prefix + name + ext

def store_file(file_object, file_name_prefix = ''):
    """Creates an instance of django's file storage
    object based on the file-like object,
    returns the storage object, file name, file url
    """
    file_ext = os.path.splitext(file_object.name)[1].lower()
    file_name = make_file_name(file_ext, file_name_prefix)
    file_storage = get_storage_class()()
    # use default storage to store file
    file_storage.save(file_name, file_object)

    file_url = file_storage.url(file_name)
    parsed_url = urlparse.urlparse(file_url)
    file_url = urlparse.urlunparse(
        urlparse.ParseResult(
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            '', '', ''
        )
    )

    return file_storage, file_name, file_url
