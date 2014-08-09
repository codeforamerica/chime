from flask import request, redirect, session, url_for
from requests import post, get
from urllib import urlencode
import random
from string import ascii_uppercase, digits
import oauth2
import os
import json
from datetime import date, timedelta

google_access_token_url = 'https://accounts.google.com/o/oauth2/token'

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
                                  scope='openid profile', state=state, response_type='code',
                                  access_type='offline', approval_prompt='force'))

    return redirect('https://accounts.google.com/o/oauth2/auth' + '?' + query_string)

def callback_google(state, code, callback_uri):
    ''' Get the refresh token so we can use it to get a new access token every once in a while
    '''
    if state != session['state']:
        raise Exception()

    data = dict(client_id=os.environ.get('CLIENT_ID'), client_secret=os.environ.get('CLIENT_SECRET'),
                code=code, redirect_uri=callback_uri,
                grant_type='authorization_code')

    resp = post('https://accounts.google.com/o/oauth2/token', data=data)
    access = json.loads(resp.content)
    session['access_token'] = access['access_token']
    session['refresh_token'] = access['refresh_token']

def fetch_google_analytics_for_page(page_path):
    ''' Get stats for a particular page
    '''
    start_date = (date.today() - timedelta(days=7)).isoformat()
    end_date = date.today().isoformat()
    profile_id = os.environ.get('PROFILE_ID')
    query_string = urlencode({'ids' : 'ga:' + profile_id, 'dimensions' : 'ga:previousPagePath,ga:pagePath',
                               'metrics' : 'ga:pageViews,ga:avgTimeOnPage,ga:exitRate',
                               'filters' : 'ga:pagePath' + page_path, 'start-date' : start_date,
                               'end-date' : end_date, 'max-results' : '1'})
    resp = get('https://www.googleapis.com/analytics/v3/data/ga' + '?' + query_string)
    return json.loads(resp.content)
