from __future__ import print_function

from os import environ
from getpass import getpass
from re import match
from urllib import urlencode
from urlparse import urljoin
import json

from boto.ec2 import EC2Connection
from oauth2client.client import OAuth2WebServerFlow
import gspread

def get_input():
    '''
    '''
    github_client_id = environ['GITHUB_CLIENT_ID']
    github_client_secret = environ['GITHUB_CLIENT_SECRET']
    
    gdocs_client_id = environ['GDOCS_CLIENT_ID']
    gdocs_client_secret = environ['GDOCS_CLIENT_SECRET']

    print('--> Enter Github details:')
    username = raw_input('    Github username: ')
    password = getpass('    Github password: ')
    reponame = raw_input('    New Github repository name: ')

    if not match(r'\w+(-\w+)*$', reponame):
        raise RuntimeError('Repository "{}" does not match "\w+(-\w+)*$"'.format(reponame))

    ec2 = EC2Connection()
    
    return github_client_id, github_client_secret, \
           gdocs_client_id, gdocs_client_secret, \
           username, password, reponame, ec2

def authenticate_google(gdocs_client_id, gdocs_client_secret):
    '''
    '''
    scopes = [
        'https://spreadsheets.google.com/feeds/',

        # http://stackoverflow.com/questions/24293523/im-trying-to-access-google-drive-through-the-cli-but-keep-getting-not-authori
        'https://docs.google.com/feeds',
        ]

    flow = OAuth2WebServerFlow(gdocs_client_id, gdocs_client_secret, scopes)
    flow_info = flow.step1_get_device_and_user_codes()

    user_code, verification_url = flow_info.user_code, flow_info.verification_url
    print('--> Authenticate with Google Docs:')
    print('    Visit {verification_url} with code "{user_code}"'.format(**locals()))
    print('    (then come back here and press enter)')

    raw_input()
    credentials = flow.step2_exchange(device_flow_info=flow_info)
    
    print('--> Google Docs authentication OK')
    return credentials

def create_google_spreadsheet(credentials, reponame):
    '''
    '''
    email = 'frances@codeforamerica.org'
    gdocs_api_base = 'https://www.googleapis.com/drive/v2/files/'
    headers = {'Content-Type': 'application/json'}

    source_id = '12jUfaRBd-CU1_6BGeLFG1_qoi7Fw_vRC_SXv36eDzM0'
    url = urljoin(gdocs_api_base, '{source_id}/copy'.format(**locals()))

    gc = gspread.authorize(credentials)
    resp = gc.session.post(url, '{ }', headers=headers)
    info = json.load(resp)
    new_id = info['id']

    print('    Created spreadsheet "{title}"'.format(**info))

    url = urljoin(gdocs_api_base, new_id)
    new_title = 'Ceviche logins for {reponame}'.format(**locals())
    patch = dict(title=new_title)
    
    gc = gspread.authorize(credentials)
    gc.session.request('PATCH', url, json.dumps(patch), headers=headers)

    print('    Updated title to "{new_title}"'.format(**locals()))

    query = urlencode(dict(sendNotificationEmails='true', emailMessage='Yo.'))
    url = urljoin(gdocs_api_base, '{new_id}/permissions?{query}'.format(**locals()))
    permission = dict(type='user', role='writer', emailAddress=email, value=email)

    gc = gspread.authorize(credentials)
    gc.session.post(url, json.dumps(permission), headers=headers)

    print('    Invited {email} to "{new_title}"'.format(**locals()))

    return new_id
