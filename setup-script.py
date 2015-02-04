from getpass import getpass
from urlparse import urljoin
from os import environ
import json, requests

def check_status(resp, task):
    '''
    '''
    if resp.status_code not in range(200, 299):
        raise RuntimeError('Got {} trying to {}'.format(resp.status_code, task))

#
# Establish some baseline details.
#
github_api_base = 'https://api.github.com/'
github_client_id = environ['GITHUB_CLIENT_ID']
github_client_secret = environ['GITHUB_CLIENT_SECRET']

username = raw_input('Enter Github username: ')
password = getpass('Enter Github password: ')

#
# Create a new authorization with Github.
# https://developer.github.com/v3/oauth_authorizations/#create-a-new-authorization
#
info = dict(
    scopes='repo',
    note='Ceviche setup script',
    client_id=github_client_id,
    client_secret=github_client_secret
    )

url = urljoin(github_api_base, '/authorizations')
resp = requests.post(url, json.dumps(info), auth=(username, password))
check_status(resp, 'create a new authorization')

github_auth_id = resp.json().get('id')
github_token = resp.json().get('token')

#
# Verify status of Github authorization.
# https://developer.github.com/v3/oauth_authorizations/#check-an-authorization
#
path = '/applications/{client_id}/tokens/{token}'
kwargs = dict(client_id=github_client_id, token=github_token)
url = urljoin(github_api_base, path.format(**kwargs))
resp = requests.get(url, auth=(github_client_id, github_client_secret))
check_status(resp, 'check authorization {}'.format(github_auth_id))

#
# Delete Github authorization.
# https://developer.github.com/v3/oauth_authorizations/#delete-an-authorization
#
url = urljoin(github_api_base, '/authorizations/{}'.format(github_auth_id))
resp = requests.delete(url, auth=(username, password))
check_status(resp, 'delete authorization {}'.format(github_auth_id))
