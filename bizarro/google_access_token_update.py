from .google_api_functions import get_new_access_token
from os import environ
import argparse, traceback, sys

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
            token_file_path =  environ.get('TOKEN_ROOT_DIR').rstrip('/')
            with open(token_file_path + '/refresh_token', 'r') as f:
                refresh_token = f.read()
            get_new_access_token(refresh_token)
        except:
            traceback.print_exc(file=sys.stderr)
        
        finally:
            if not args.hourly:
                break

            print 'Sleeping.'
            sleep(3600)