from logging import getLogger
Logger = getLogger('bizarro.google_access_token_update')

from .google_api_functions import request_new_google_access_token, read_ga_config
import argparse
import traceback
import sys
from time import sleep

parser = argparse.ArgumentParser(description='Update google access token')

parser.add_argument('--hourly', action='store_true',
                    help='Ask for new access token from Google API hourly.')

if __name__ == '__main__':

    args = parser.parse_args()

    ''' Periodically get a new access_token and store it. This keeps the user from
      having to keep authing with google
    '''
    while True:
        try:
            ga_config = read_ga_config()
            request_new_google_access_token(ga_config.get('refresh_token'))
        except:
            traceback.print_exc(file=sys.stderr)

        finally:
            if not args.hourly:
                break

            Logger.debug('Sleeping.')
            sleep(3600)
