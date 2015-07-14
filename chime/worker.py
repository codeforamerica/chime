from __future__ import absolute_import, print_function
from logging import getLogger
Logger = getLogger('chime.worker')

import os
import argparse
import time
import sys
import traceback

from git import Repo

from .repo_functions import NEEDS_PUSH_FILE, push_upstream_if_needed
from .google_api_functions import (
    is_overdue_ga_config, read_ga_config, request_new_google_access_token
)

parser = argparse.ArgumentParser(description='Do the things that need doing.')

if __name__ == '__main__':

    args = parser.parse_args()

    running_state_dir, ga_client_id, ga_client_secret, repo_path = \
        os.environ['RUNNING_STATE_DIR'], os.environ['GA_CLIENT_ID'], \
        os.environ['GA_CLIENT_SECRET'], os.environ['REPO_PATH']

    while True:
        #
        # Periodically get a new access_token and store it.
        # This keeps the user from having to keep authing with Google.
        #
        try:
            if is_overdue_ga_config(running_state_dir):
                Logger.info('Updating GA config in {}.'.format(running_state_dir))
                token_args = (
                    read_ga_config(running_state_dir).get('refresh_token'),
                    running_state_dir, ga_client_id, ga_client_secret
                )
                request_new_google_access_token(*token_args)
        except:
            traceback.print_exc(file=sys.stderr)
        
        #
        # Periodically push to upstream backup remote from origin, triggered
        # in @synch_required and @synched_checkout_required decorators.
        #
        try:
            push_upstream_if_needed(Repo(repo_path), running_state_dir)
        except:
            traceback.print_exc(file=sys.stderr)

        Logger.debug('Sleeping.')
        time.sleep(5)
