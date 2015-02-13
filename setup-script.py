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

from itsdangerous import Signer
from boto.ec2.blockdevicemapping import BlockDeviceMapping, BlockDeviceType

from bizarro.setup import functions

github_api_base = 'https://api.github.com/'

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
github_client_id, github_client_secret, gdocs_client_id, gdocs_client_secret, \
    username, password, reponame, ec2 = functions.get_input()

resp = requests.get(urljoin(github_api_base, '/user'), auth=(username, password))

if resp.status_code != 200:
    raise RuntimeError('Failed Github login for user "{}"'.format(username))

print '--> Github login OK'

#
# Ask for Google Docs credentials and create an authentication spreadsheet.
#
gdocs_credentials = functions.authenticate_google(gdocs_client_id, gdocs_client_secret)
sheet_id = functions.create_google_spreadsheet(gdocs_credentials, reponame)
sheet_url = 'https://docs.google.com/a/codeforamerica.org/spreadsheets/d/{}'.format(sheet_id)

print '--> Created spreadsheet {}'.format(sheet_url)

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
# Set public hostname in EC2 for Browser ID based on this:
# http://www.onepwr.org/2012/04/26/chef-recipe-to-setup-up-a-new-nodes-fqdn-hostname-etc-properly/
#
if check_repo_state(reponame, github_token):
    raise RuntimeError('{} already exists, not going to run EC2'.format(reponame))

user_data = '''#!/bin/sh -ex
apt-get update -y
apt-get install -y git htop curl

# What is our public DNS name?
ipaddr=$(ifconfig eth0 | grep 'inet addr:'| grep -v '127.0.0.1' | cut -d: -f2 | awk '{{ print $1}}')
fullname=`curl -s http://169.254.169.254/latest/meta-data/public-hostname`
shortname=`echo $fullname | cut -d. -f1`

# Configure host name for Ubuntu.
sed -i '/ '$fullname'/ d' /etc/hosts
echo "$ipaddr $fullname $shortname" >> /etc/hosts
echo $shortname > /etc/hostname
hostname -F /etc/hostname

# Install Ceviche.
DIR=/var/opt/ceviche-cms
git clone -b {branch} https://github.com/codeforamerica/ceviche-cms.git $DIR
env GITHUB_REPO={repo} GITHUB_TOKEN={token} $DIR/chef/run.sh
'''.format(branch='master', token=github_token, repo=reponame)

device_sda1 = BlockDeviceType(size=16, delete_on_termination=True)
device_map = BlockDeviceMapping(); device_map['/dev/sda1'] = device_sda1

ec2_args = dict(instance_type='c3.large', user_data=user_data,
                key_name='cfa-keypair-2015', block_device_map=device_map,
                security_groups=['default'])

instance = ec2.run_instances('ami-f8763a90', **ec2_args).instances[0]
instance.add_tag('Name', 'Ceviche Test {}'.format(reponame))

print 'Prepared EC2 instance', instance.id

while not instance.dns_name:
    instance.update()
    sleep(1)

print 'Available at', instance.dns_name

while True:
    print 'Waiting for', reponame
    sleep(30)

    if check_repo_state(reponame, github_token):
        print reponame, 'exists'
        break

#
# Add a new repository deploy key.
# https://developer.github.com/v3/repos/keys/#create
#
while True:
    path = '/.well-known/deploy-key.txt'
    print 'Waiting for', path
    sleep(5)
    
    resp = requests.get('http://{}{}'.format(instance.dns_name, path))
    
    if resp.status_code == 200:
        break

deploy_key = Signer(github_token, salt='deploy-key').unsign(resp.content)
keys_url = 'https://api.github.com/repos/ceviche/{}/keys'.format(reponame)
head = {'Content-Type': 'application/json'}
body = json.dumps(dict(title='ceviche-key', key=deploy_key))
resp = requests.post(keys_url, body, headers=head, auth=(username, password))
code = resp.status_code

if code == 422:
    # Github deploy key already exists, but likely to be tied to OAuth token.
    # Delete it, and recreate with basic auth so it survives auth deletion.
    resp = requests.get(keys_url, auth=(username, password))
    key_url = [k['url'] for k in resp.json() if k['title'] == 'token-key'][0]
    resp = requests.delete(key_url, auth=(username, password))
    code = resp.status_code
    
    if code not in range(200, 299):
        raise RuntimeError('Github deploy key deletion failed, status {}'.format(code))
    
    print 'Deleted temporary token key'
    resp = requests.post(keys_url, body, headers=head, auth=(username, password))
    code = resp.status_code
    
    if code not in range(200, 299):
        raise RuntimeError('Github deploy key recreation failed, status {}'.format(code))
    
elif code not in range(200, 299):
    raise RuntimeError('Github deploy key creation failed, status {}'.format(code))

print 'Created permanent deploy key', 'ceviche-key'

#
# Delete Github authorization.
# https://developer.github.com/v3/oauth_authorizations/#delete-an-authorization
#
url = urljoin(github_api_base, '/authorizations/{}'.format(github_auth_id))
resp = requests.delete(url, auth=(username, password))
check_status(resp, 'delete authorization {}'.format(github_auth_id))
