import threading
from django.core import management
from django.apps import apps


class ImporterThread(threading.Thread):
    def __init__(self, dump_file = None):
        self.dump_file = dump_file
        super().__init__()

    def run(self):
        management.call_command('load_stackexchange', self.dump_file)


def is_ready():
    """determines whether the stackexchange app is ready to roll
    by trying to load a model from the database
    """
    try:
        apps.get_model('stackexchange', 'User2Vote')
        return True
    except Exception:
        return False
