from flask import request, redirect, session, url_for
from requests import post, get
from urllib import urlencode
import random
from string import ascii_uppercase, digits
import oauth2
import os
import json
from datetime import date, timedelta
from re import sub

def authorize_google():
    ''' Authorize google via oauth2
    '''
    #
    # This is how google says the state should be generated
    #
    state = ''.join(random.choice(ascii_uppercase + digits)
                  for x in xrange(32))
    session['state'] = state

    query_string = urlencode(dict(client_id=os.environ.get('CLIENT_ID'), redirect_uri=os.environ.get('REDIRECT_URI'),
                                  scope='openid profile https://www.googleapis.com/auth/analytics', state=state, response_type='code',
                                  access_type='offline', approval_prompt='force'))
    return redirect('https://accounts.google.com/o/oauth2/auth' + '?' + query_string)

def callback_google(state, code, callback_uri):
    ''' Get the access token plus the refresh token so we can use it to get a new access token
        every once in a while
    '''
    if state != session['state']:
        raise Exception()

    data = dict(client_id=os.environ.get('CLIENT_ID'), client_secret=os.environ.get('CLIENT_SECRET'),
                code=code, redirect_uri=callback_uri,
                grant_type='authorization_code')

    resp = post('https://accounts.google.com/o/oauth2/token', data=data)

    if resp.status_code != 200:
        raise Exception()
    access = json.loads(resp.content)

    token_file_path =  os.environ.get('TOKEN_ROOT_DIR', '.').rstrip('/')
    with open(token_file_path + '/access_token', "w") as f:
        f.write(access['access_token'])

    with open(token_file_path + '/refresh_token', "w") as f:
        f.write(access['refresh_token'])

def get_new_access_token(refresh_token):
    ''' Get a new access token with the refresh token so a user doesn't need to
        authorize the app again
    '''
    data = dict(client_id=os.environ.get('CLIENT_ID'), client_secret=os.environ.get('CLIENT_SECRET'),
                refresh_token=refresh_token, grant_type='refresh_token')

    resp = post('https://accounts.google.com/o/oauth2/token', data=data)

    if resp.status_code != 200:
        raise Exception()
    access = json.loads(resp.content)

    token_file_path =  os.environ.get('TOKEN_ROOT_DIR').rstrip('/') + '/access_token'
    with open(token_file_path, "w") as f:
        f.write(access['access_token'])

def fetch_google_analytics_for_page(page_path, access_token):
    ''' Get stats for a particular page
    '''
    start_date = (date.today() - timedelta(days=7)).isoformat()
    end_date = date.today().isoformat()
    profile_id = os.environ.get('PROFILE_ID')
    repo_root_dir = os.environ.get('REPO_ROOT_DIR', '')
    repo_root_dir =  repo_root_dir.rstrip('/') + '/'
    filter_page_path = sub(r'\.html$|\.md$', '', page_path)
    query_string = urlencode({'ids' : 'ga:' + profile_id, 'dimensions' : 'ga:previousPagePath,ga:pagePath',
                               'metrics' : 'ga:pageViews,ga:avgTimeOnPage,ga:exitRate',
                               'filters' : 'ga:pagePath==' + repo_root_dir + filter_page_path, 'start-date' : start_date,
                               'end-date' : end_date, 'max-results' : '1', 'access_token' : access_token})
    resp = get('https://www.googleapis.com/analytics/v3/data/ga' + '?' + query_string)
    response_list = json.loads(resp.content)
    if 'error' in response_list:
        return {}
    else:
        average_time = str(int(float(response_list['totalsForAllResults']['ga:avgTimeOnPage'])))
        analytics_dict = {'page_views' : response_list['totalsForAllResults']['ga:pageViews'],
                          'average_time_page' : average_time,
                          'start_date' : start_date, 'end_date' : end_date}
        return analytics_dict
