from __future__ import print_function

from os import environ
from getpass import getpass
from re import match
from urllib import urlencode
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

    username = raw_input('Enter Github username: ')
    password = getpass('Enter Github password: ')
    reponame = raw_input('Enter new Github repository name: ')

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
    print('Enter "{user_code}" at {verification_url}'.format(**locals()))
    print('(then come back here and press enter)')

    raw_input()
    credentials = flow.step2_exchange(device_flow_info=flow_info)
    
    return credentials

def create_google_spreadsheet(credentials):
    '''
    '''
    gc = gspread.authorize(credentials)
    url = 'https://www.googleapis.com/drive/v2/files/12jUfaRBd-CU1_6BGeLFG1_qoi7Fw_vRC_SXv36eDzM0/copy'
    print('POST to', url)

    resp = gc.session.post(url, '{}', headers={'Content-Type': 'application/json'})

    info = json.load(resp)
    print('{id} - {title}'.format(**info))

    gc = gspread.authorize(credentials)
    url = 'https://www.googleapis.com/drive/v2/files/{id}'.format(**info)
    print('PATCH to', url)
    gc.session.request('PATCH', url, '{"title": "Good TIMES"}', headers={'Content-Type': 'application/json'})

    perm = dict(
        role='writer',
        type='user',
        emailAddress='frances@codeforamerica.org',
        value='frances@codeforamerica.org'
        )

    query = urlencode(dict(sendNotificationEmails='true', emailMessage='Yo.'))
    gc = gspread.authorize(credentials)
    url = 'https://www.googleapis.com/drive/v2/files/{id}/permissions?{}'.format(query, **info)
    print('POST to', url)
    gc.session.post(url, json.dumps(perm), headers={'Content-Type': 'application/json'})
    
    return info['id']
