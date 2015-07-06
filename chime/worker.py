from __future__ import absolute_import
from logging import getLogger
Logger = getLogger('chime.worker')

import argparse
import time

parser = argparse.ArgumentParser(description='Do the things that need doing.')

if __name__ == '__main__':

    args = parser.parse_args()

    while True:
        Logger.debug('Sleeping.')
        time.sleep(3600)
