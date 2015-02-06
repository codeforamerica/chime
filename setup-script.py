''' Setup script for new Ceviche instance in EC2.

Asks for Github login credentials and desired repository
name to create under https://github.com/ceviche organization.

Requires four environment variables:
- GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET for Github authorization.
- AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY for Amazon EC2 setup.

Follows the process described here:
  https://github.com/codeforamerica/ceviche-cms/issues/39#issuecomment-72957188

'''
from getpass import getpass
from urlparse import urljoin
from os import environ
from time import sleep
import re, json, requests

from boto.ec2 import EC2Connection
from boto.ec2.blockdevicemapping import BlockDeviceMapping, BlockDeviceType

def check_status(resp, task):
    ''' Raise a RuntimeError if response is not HTTP 2XX.
    '''
    if resp.status_code not in range(200, 299):
        raise RuntimeError('Got {} trying to {}'.format(resp.status_code, task))

def check_repo_state(reponame, token):
    ''' Return True if repository name exists.
    '''
    auth = token, 'x-oauth-basic'
    path = '/repos/ceviche/{}'.format(reponame)
    resp = requests.get(urljoin(github_api_base, path), auth=auth)
    
    return bool(resp.status_code == 200)


#
# Establish some baseline details.
#
github_api_base = 'https://api.github.com/'
github_client_id = environ['GITHUB_CLIENT_ID']
github_client_secret = environ['GITHUB_CLIENT_SECRET']

username = raw_input('Enter Github username: ')
password = getpass('Enter Github password: ')
reponame = raw_input('Enter new Github repository name: ')

if not re.match(r'\w+(-\w+)*$', reponame):
    raise RuntimeError('Repository "{}" does not match "\w+(-\w+)*$"'.format(reponame))

ec2 = EC2Connection()

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
# EC2
#
if check_repo_state(reponame, github_token):
    raise RuntimeError('{} already exists, not going to run EC2'.format(reponame))

user_data = '''#!/bin/sh -ex
apt-get update -y
apt-get install -y git htop

DIR=/var/opt/ceviche-cms
git clone -b {branch} https://github.com/codeforamerica/ceviche-cms.git $DIR
env GITHUB_REPO={repo} GITHUB_TOKEN={token} $DIR/chef/run.sh
'''.format(branch='setup-new-instance-issue-39', token=github_token, repo=reponame)

device_sda1 = BlockDeviceType(size=16, delete_on_termination=True)
device_map = BlockDeviceMapping(); device_map['/dev/sda1'] = device_sda1

ec2_args = dict(instance_type='c3.large', user_data=user_data,
                key_name='cfa-keypair-2015', block_device_map=device_map,
                security_groups=['default'])

instance = ec2.run_instances('ami-f8763a90', **ec2_args).instances[0]
instance.add_tag('Name', 'Ceviche Test')

print 'Prepared EC2 instance', instance

while True:
    print 'Waiting for', reponame
    sleep(30)

    if check_repo_state(reponame, github_token):
        print reponame, 'exists'
        break

sleep(30) # give it time to prepare a deploy key

#
# Delete Github authorization.
# https://developer.github.com/v3/oauth_authorizations/#delete-an-authorization
#
url = urljoin(github_api_base, '/authorizations/{}'.format(github_auth_id))
resp = requests.delete(url, auth=(username, password))
check_status(resp, 'delete authorization {}'.format(github_auth_id))
