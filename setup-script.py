''' Setup script for new Chime instance in EC2.

Asks for Github login credentials and desired repository
name to create under https://github.com/chimecms organization.

Requires four environment variables:
- GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET for Github authorization.
- AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY for Amazon EC2 setup.

Follows the process described here:
  https://github.com/codeforamerica/ceviche-cms/issues/39#issuecomment-72957188

'''
from getpass import getpass
from urlparse import urljoin
from os.path import join, dirname
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
    path = '/repos/chimecms/{}'.format(reponame)
    resp = requests.get(urljoin(github_api_base, path), auth=auth)
    
    return bool(resp.status_code == 200)

#
# Establish some baseline details.
#
github_client_id, github_client_secret, gdocs_client_id, gdocs_client_secret, \
    username, password, reponame, ec2, route53 = functions.get_input()

resp = requests.get(urljoin(github_api_base, '/user'), auth=(username, password))

if resp.status_code != 200:
    raise RuntimeError('Failed Github login for user "{}"'.format(username))

print '--> Github login OK'

#
# Ask for Google Docs credentials and create an authentication spreadsheet.
#
gdocs_credentials = functions.authenticate_google(gdocs_client_id, gdocs_client_secret)
sheet_id = functions.create_google_spreadsheet(gdocs_credentials, reponame)
sheet_url = 'https://docs.google.com/spreadsheets/d/{}'.format(sheet_id)

print '--> Created spreadsheet {}'.format(sheet_url)

#
# Create a new authorization with Github.
# https://developer.github.com/v3/oauth_authorizations/#create-a-new-authorization
#
github_auth_id, github_temporary_token = functions.get_github_authorization(
    github_client_id, github_client_secret, (username, password))

#
# Verify status of Github authorization.
# https://developer.github.com/v3/oauth_authorizations/#check-an-authorization
#
functions.verify_github_authorization(
    github_client_id, github_client_secret, github_temporary_token, github_auth_id)

#
# EC2
# Set public hostname in EC2 for Browser ID based on this:
# http://www.onepwr.org/2012/04/26/chef-recipe-to-setup-up-a-new-nodes-fqdn-hostname-etc-properly/
#
if check_repo_state(reponame, github_temporary_token):
    raise RuntimeError('Repository {} already exists, not going to run EC2'.format(reponame))

instance = functions.create_ec2_instance(
    ec2, reponame, sheet_url, gdocs_client_id, gdocs_client_secret, github_temporary_token)

while True:
    print '    Waiting for', reponame
    sleep(30)

    if check_repo_state(reponame, github_temporary_token):
        print '-->', 'https://github.com/chimecms/{}'.format(reponame), 'exists'
        break

#
# Add a new repository webhook.
# https://developer.github.com/v3/repos/hooks/#create-a-hook
#
functions.add_github_webhook(reponame, (github_temporary_token, 'x-oauth-basic'))

#
# Add a new repository deploy key.
# https://developer.github.com/v3/repos/keys/#create
#
deploy_key = functions.get_public_deploy_key(
    instance.dns_name, secret=github_temporary_token, salt='deploy-key')

functions.add_permanent_github_deploy_key(deploy_key, reponame, (username, password))

#
# Delete Github authorization.
# https://developer.github.com/v3/oauth_authorizations/#delete-an-authorization
#
functions.delete_temporary_github_authorization(github_auth_id, (username, password))

#
# Write domain name to Route 53.
#
cname = functions.create_cname_record(route53, reponame, instance.dns_name)

#
# Save details of instance.
#
functions.save_details(gdocs_credentials,
                       reponame, cname, instance, reponame, sheet_url, deploy_key)
