''' Do nothing.

The activities previously defined here have moved to chime.worker.
'''
from __future__ import absolute_import
from logging import getLogger
Logger = getLogger('chime.google_access_token_update')

import argparse
from time import sleep

parser = argparse.ArgumentParser(description='Do nothing.')
parser.add_argument('--hourly', action='store_true', help='Do nothing hourly.')

if __name__ == '__main__':

    args = parser.parse_args()

    while True:
        if not args.hourly:
            break

        Logger.debug('Sleeping.')
        sleep(3600)
