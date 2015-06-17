from django.core.management.base import NoArgsCommand
from django.db import transaction
import os.path
import askbot
from askbot.search.postgresql import setup_full_text_search

class Command(NoArgsCommand):
    @transaction.commit_on_success
    def handle_noargs(self, **options):
        script_path = os.path.join(
                            askbot.get_install_directory(),
                            'search',
                            'postgresql',
                            'thread_and_post_models_10032013.plsql'
                        )
        setup_full_text_search(script_path)

        script_path = os.path.join(
                            askbot.get_install_directory(),
                            'search',
                            'postgresql',
                            'user_profile_search_02262013.plsql'
                        )
        setup_full_text_search(script_path)
