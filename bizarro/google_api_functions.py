from flask import current_app, request, redirect, session, url_for
from requests import post, get
from urllib import urlencode
import random
from string import ascii_uppercase, digits
import oauth2
import os
import posixpath
import json
from datetime import date, timedelta
from re import sub

GA_CONFIG_FILENAME = 'ga_config.json'

def authorize_google():
    ''' Authorize google via oauth2
    '''
    #
    # This is how google says the state should be generated
    #
    state = ''.join(random.choice(ascii_uppercase + digits)
                  for x in xrange(32))
    session['state'] = state


    query_string = urlencode(dict(client_id=current_app.config['GA_CLIENT_ID'], redirect_uri=current_app.config['GA_REDIRECT_URI'],
                                  scope='openid profile https://www.googleapis.com/auth/analytics', state=state, response_type='code',
                                  access_type='offline', approval_prompt='force'))
    return redirect('https://accounts.google.com/o/oauth2/auth' + '?' + query_string)

def callback_google(state, code, callback_uri):
    ''' Get the access token plus the refresh token so we can use them
        to get a new access token every once in a while
    '''
    if state != session['state']:
        raise Exception()

    data = dict(client_id=current_app.config['GA_CLIENT_ID'], client_secret=current_app.config['GA_CLIENT_SECRET'],
                code=code, redirect_uri=callback_uri,
                grant_type='authorization_code')

    resp = post('https://accounts.google.com/o/oauth2/token', data=data)

    if resp.status_code != 200:
        raise Exception()
    access = json.loads(resp.content)

    ga_config_path = os.path.join(current_app.config['RUNNING_STATE_DIR'], GA_CONFIG_FILENAME)
    with open(ga_config_path) as infile:
        ga_config = json.load(infile)

    # change the values of the access and refresh tokens
    ga_config['access_token'] = access['access_token']
    ga_config['refresh_token'] = access['refresh_token']

    # write the new config json
    with open(ga_config_path, 'w') as outfile:
        json.dump(ga_config, outfile, indent=2, ensure_ascii=False)

def get_new_access_token(refresh_token):
    ''' Get a new access token with the refresh token so a user doesn't need to
        authorize the app again
    '''
    if not refresh_token:
        return False

    data = dict(client_id=current_app.config['GA_CLIENT_ID'], client_secret=current_app.config['GA_CLIENT_SECRET'],
                refresh_token=refresh_token, grant_type='refresh_token')

    resp = post('https://accounts.google.com/o/oauth2/token', data=data)

    if resp.status_code != 200:
        raise Exception()

    access = json.loads(resp.content)

    # load the config json
    ga_config_path = os.path.join(current_app.config['RUNNING_STATE_DIR'], GA_CONFIG_FILENAME)
    with open(ga_config_path) as infile:
        ga_config = json.load(infile)
    # change the value of the access token
    ga_config['access_token'] = access['access_token']
    # write the new config json
    with open(ga_config_path, 'w') as outfile:
        json.dump(ga_config, outfile, indent=2, ensure_ascii=False)
    return True

def get_ga_page_path_pattern(page_path, project_domain):
    ''' Get a regex pattern that'll get us the google analytics data we want.
        Builds a pattern that looks like: codeforamerica.org/about/(index.html|index|)
    '''
    page_path_dir, page_path_filename = posixpath.split(page_path)
    filename_base, filename_ext = posixpath.splitext(page_path_filename)
    # if the filename is 'index', allow no filename as an option
    or_else = '|' if (filename_base == 'index') else ''
    filename_pattern = '({page_path_filename}|{filename_base}{or_else})'.format(**locals())
    return posixpath.join(project_domain, page_path_dir, filename_pattern)

def fetch_google_analytics_for_page(config, page_path, access_token):
    ''' Get stats for a particular page
    '''
    ga_config_path = os.path.join(config['RUNNING_STATE_DIR'], GA_CONFIG_FILENAME)
    with open(ga_config_path) as infile:
        ga_config = json.load(infile)
    ga_project_domain = ga_config['project_domain']
    ga_profile_id = ga_config['profile_id']

    start_date = (date.today() - timedelta(days=7)).isoformat()
    end_date = date.today().isoformat()

    page_path_pattern = get_ga_page_path_pattern(page_path, ga_project_domain)

    query_string = urlencode({'ids' : 'ga:' + ga_profile_id, 'dimensions' : 'ga:previousPagePath,ga:pagePath',
                               'metrics' : 'ga:pageViews,ga:avgTimeOnPage,ga:exitRate',
                               'filters' : 'ga:pagePath=~' + page_path_pattern, 'start-date' : start_date,
                               'end-date' : end_date, 'max-results' : '1', 'access_token' : access_token})

    resp = get('https://www.googleapis.com/analytics/v3/data/ga' + '?' + query_string)
    response_list = resp.json()

    if u'error' in response_list:
        return {}
    else:
        average_time = unicode(int(float(response_list['totalsForAllResults']['ga:avgTimeOnPage'])))
        analytics_dict = {'page_views' : response_list['totalsForAllResults']['ga:pageViews'],
                          'average_time_page' : average_time,
                          'start_date' : start_date, 'end_date' : end_date}
        return analytics_dict
