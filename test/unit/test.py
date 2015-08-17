# -- coding: utf-8 --
from __future__ import absolute_import

from unittest import main, TestCase

from tempfile import mkdtemp
from StringIO import StringIO
from os.path import join, exists, dirname, isdir, abspath, isfile, sep, realpath
from urlparse import urlparse, urljoin
from urllib import quote
from os import environ, remove, mkdir
from shutil import rmtree, copytree
from uuid import uuid4
from re import search, sub
import random
from datetime import date, timedelta
import sys
from chime.repo_functions import ChimeRepo
from slugify import slugify
import json
import time
import logging
import tempfile
logging.disable(logging.CRITICAL)

repo_root = abspath(join(dirname(__file__), '..'))
sys.path.insert(0, repo_root)

from git.cmd import GitCommandError
from box.util.rotunicode import RotUnicode
from httmock import response, HTTMock
from mock import MagicMock, patch
from bs4 import Comment

from chime import (
    create_app, jekyll_functions, repo_functions, edit_functions,
    google_api_functions, view_functions, publish,
    google_access_token_update, errors)
from chime import constants

from unit.chime_test_client import ChimeTestClient
from unit.app import TestApp, TestAppConfig, TestPublishApp
from unit.process import TestProcess
from unit.repo import TestRepo

import codecs
codecs.register(RotUnicode.search_function)

# these patterns help us search the HTML of a response to determine if the expected page loaded
PATTERN_BRANCH_COMMENT = u'<!-- branch: {} -->'
PATTERN_AUTHOR_COMMENT = u'<!-- author: {} -->'
PATTERN_TASK_COMMENT = u'<!-- task: {} -->'
PATTERN_BENEFICIARY_COMMENT = u'<!-- beneficiary: {} -->'
PATTERN_TEMPLATE_COMMENT = u'<!-- template name: {} -->'
PATTERN_FILE_COMMENT = u'<!-- file type: {file_type}, file name: {file_name}, file title: {file_title} -->'
PATTERN_OVERVIEW_ITEM_CREATED = u'<p>The "{created_name}" {created_type} was created by {author_email}.</p>'
PATTERN_OVERVIEW_ACTIVITY_STARTED = u'<p>The "{activity_name}" activity was started by {author_email}.</p>'
PATTERN_OVERVIEW_COMMENT_BODY = u'<div class="comment__body">{comment_body}</div>'
PATTERN_OVERVIEW_ITEM_DELETED = u'<p>The "{deleted_name}" {deleted_type} {deleted_also}was deleted by {author_email}.</p>'
PATTERN_FLASH_TASK_DELETED = u'You deleted the "{description}" activity for {beneficiary}!'

PATTERN_FLASH_SAVED_CATEGORY = u'<li class="flash flash--notice">Saved changes to the {title} topic! Remember to submit this change for feedback when you\'re ready to go live.</li>'
PATTERN_FLASH_CREATED_CATEGORY = u'Created a new topic named {title}! Remember to submit this change for feedback when you\'re ready to go live.'
PATTERN_FLASH_CREATED_ARTICLE = u'Created a new article named {title}! Remember to submit this change for feedback when you\'re ready to go live.'
PATTERN_FLASH_SAVED_ARTICLE = u'Saved changes to the {title} article! Remember to submit this change for feedback when you\'re ready to go live.'
PATTERN_FLASH_DELETED_ARTICLE = u'The "{title}" article was deleted! Remember to submit this change for feedback when you\'re ready to go live.'
PATTERN_FORM_CATEGORY_TITLE = u'<input name="en-title" type="text" value="{title}" class="directory-modify__name" placeholder="Crime Statistics and Maps">'
PATTERN_FORM_CATEGORY_DESCRIPTION = u'<textarea name="en-description" class="directory-modify__description" placeholder="Crime statistics and reports by district and map">{description}</textarea>'

# review stuff
PATTERN_REQUEST_FEEDBACK_BUTTON = u'<input class="toolbar__item button button--orange" type="submit" name="request_feedback" value="Request Feedback">'
PATTERN_UNREVIEWED_EDITS_LINK = u'<a href="/tree/{branch_name}/" class="toolbar__item button">Unreviewed Edits</a>'
PATTERN_ENDORSE_BUTTON = u'<input class="toolbar__item button button--green" type="submit" name="endorse_edits" value="Looks Good!">'
PATTERN_FEEDBACK_REQUESTED_LINK = u'<a href="/tree/{branch_name}/" class="toolbar__item button">Feedback requested</a>'
PATTERN_PUBLISH_BUTTON = u'<input class="toolbar__item button button--blue" type="submit" name="merge" value="Publish">'
PATTERN_READY_TO_PUBLISH_LINK = u'<a href="/tree/{branch_name}/" class="toolbar__item button">Ready to publish</a>'

class TestJekyll (TestCase):

    def test_good_files(self):
        front = dict(title='Greeting'.encode('rotunicode'))
        body, file = u'World: Hello.'.encode('rotunicode'), StringIO()

        jekyll_functions.dump_jekyll_doc(front, body, file)
        _front, _body = jekyll_functions.load_jekyll_doc(file)

        self.assertEqual(_front['title'], front['title'])
        self.assertEqual(_body, body)

        file.seek(0)
        file.read(4) == '---\n'

    def test_missing_front_matter(self):
        '''
        Should read properly with valid, minimal front matter
        '''
        expected_body = 'Missing front matter'
        actual_front, actual_body = jekyll_functions.load_jekyll_doc(StringIO(expected_body))
        self.assertEqual({}, actual_front)
        self.assertEqual(actual_body, expected_body)


class TestViewFunctions (TestCase):

    def setUp(self):
        self.old_tempdir, tempfile.tempdir = tempfile.tempdir, mkdtemp(prefix='chime-TestViewFunctions-')

        repo_path = dirname(abspath(__file__)) + '/../test-app.git'
        temp_repo_dir = mkdtemp(prefix='chime-root')
        temp_repo_path = temp_repo_dir + '/test-app.git'
        copytree(repo_path, temp_repo_path)
        self.origin = ChimeRepo(temp_repo_path)
        repo_functions.ignore_task_metadata_on_merge(self.origin)
        self.clone = self.origin.clone(mkdtemp(prefix='chime-'))
        repo_functions.ignore_task_metadata_on_merge(self.clone)

        self.session = dict(email=str(uuid4()))

        environ['GIT_AUTHOR_NAME'] = ' '
        environ['GIT_COMMITTER_NAME'] = ' '
        environ['GIT_AUTHOR_EMAIL'] = self.session['email']
        environ['GIT_COMMITTER_EMAIL'] = self.session['email']

    def tearDown(self):
        rmtree(tempfile.tempdir)
        tempfile.tempdir = self.old_tempdir

    # in TestViewFunctions
    def test_sorted_paths(self):
        ''' Ensure files/directories are sorted in alphabetical order, and that
            we get the expected values back from the sorted_paths method
        '''
        sorted_list = view_functions.sorted_paths(self.clone, 'master')

        expected_list = [
            {'modified_date': view_functions.get_relative_date(self.clone, 'index.md'), 'name': 'index.md', 'title': 'index.md', 'view_path': '/tree/master/view/index.md', 'is_editable': True, 'link_name': 'index.md', 'display_type': view_functions.FILE_FILE_TYPE},
            {'modified_date': view_functions.get_relative_date(self.clone, 'other'), 'name': 'other', 'title': 'other', 'view_path': '/tree/master/view/other', 'is_editable': False, 'link_name': u'other/', 'display_type': view_functions.FOLDER_FILE_TYPE},
            {'modified_date': view_functions.get_relative_date(self.clone, 'other.md'), 'name': 'other.md', 'title': 'other.md', 'view_path': '/tree/master/view/other.md', 'is_editable': True, 'link_name': 'other.md', 'display_type': view_functions.FILE_FILE_TYPE},
            {'modified_date': view_functions.get_relative_date(self.clone, 'sub'), 'name': 'sub', 'title': 'sub', 'view_path': '/tree/master/view/sub', 'is_editable': False, 'link_name': u'sub/', 'display_type': view_functions.FOLDER_FILE_TYPE}]

        self.assertEqual(sorted_list, expected_list)

    # in TestViewFunctions
    def test_breadcrumb_paths_with_no_relative_path(self):
        ''' Ensure that a list with pairs of a sub-directory and the absolute path
            to that directory is returned for all sub-directories in a path
        '''
        breadcrumb_paths = view_functions.make_breadcrumb_paths('my-branch')
        self.assertEqual(breadcrumb_paths, [('root', '/tree/my-branch/edit')])

    # in TestViewFunctions
    def test_breadcrumb_paths_with_relative_path(self):
        ''' Ensure that a list with pairs of a sub-directory and the absolute path
            to that directory is returned for all sub-directories in a path
        '''
        breadcrumb_paths = view_functions.make_breadcrumb_paths('my-branch', 'blah/foo/')
        self.assertEqual(breadcrumb_paths, [('root', '/tree/my-branch/edit'),
                                            ('blah', '/tree/my-branch/edit/blah/'),
                                            ('foo', '/tree/my-branch/edit/blah/foo/')])

    # in TestViewFunctions
    def test_auth_url(self):
        '''
        '''
        auth_url = 'data/authentication.csv'
        csv_url = view_functions.get_auth_csv_url(auth_url)
        self.assertEqual(csv_url, auth_url)

        auth_url = 'https://docs.google.com/spreadsheets/d/12jUfaRBd-CU1_6BGeLFG1_qoi7Fw_vRC_SXv36eDzM0/edit'
        csv_url = view_functions.get_auth_csv_url(auth_url)
        self.assertEqual(csv_url, 'https://docs.google.com/spreadsheets/d/12jUfaRBd-CU1_6BGeLFG1_qoi7Fw_vRC_SXv36eDzM0/export?format=csv')

    # in TestViewFunctions
    def test_is_allowed_email(self):
        '''
        '''
        def mock_remote_authentication_file(url, request):
            if 'good-file.csv' in url.geturl():
                return response(200, '''
Some junk below
Email domain,Organization,Email address,Organization,Name
codeforamerica.org,Code for America,mike@teczno.com,Code for America,Mike Migurski
*@codeforamerica.org,Code for America,,,
''')

            if 'org-file.csv' in url.geturl():
                return response(200, '''
Some junk below
Email domain,Organization
codeforamerica.org,Code for America
*@codeforamerica.org,Code for America
''')

            if 'addr-file.csv' in url.geturl():
                return response(200, '''
Some junk below
Email address,Organization,Name
mike@teczno.com,Code for America,Mike Migurski
''')

            return response(404, '')

        def good_file():
            return view_functions.get_auth_data_file('http://example.com/good-file.csv')

        def org_file():
            return view_functions.get_auth_data_file('http://example.com/org-file.csv')

        def addr_file():
            return view_functions.get_auth_data_file('http://example.com/addr-file.csv')

        def no_file():
            return view_functions.get_auth_data_file('http://example.com/no-file.csv')

        with HTTMock(mock_remote_authentication_file):
            self.assertTrue(view_functions.is_allowed_email(good_file(), 'mike@codeforamerica.org'))
            self.assertTrue(view_functions.is_allowed_email(good_file(), 'frances@codeforamerica.org'))
            self.assertTrue(view_functions.is_allowed_email(good_file(), 'mike@teczno.com'))
            self.assertFalse(view_functions.is_allowed_email(good_file(), 'whatever@teczno.com'))

            self.assertTrue(view_functions.is_allowed_email(org_file(), 'mike@codeforamerica.org'))
            self.assertTrue(view_functions.is_allowed_email(org_file(), 'frances@codeforamerica.org'))
            self.assertFalse(view_functions.is_allowed_email(org_file(), 'mike@teczno.com'))
            self.assertFalse(view_functions.is_allowed_email(org_file(), 'whatever@teczno.com'))

            self.assertFalse(view_functions.is_allowed_email(addr_file(), 'mike@codeforamerica.org'))
            self.assertFalse(view_functions.is_allowed_email(addr_file(), 'frances@codeforamerica.org'))
            self.assertTrue(view_functions.is_allowed_email(addr_file(), 'mike@teczno.com'))
            self.assertFalse(view_functions.is_allowed_email(addr_file(), 'whatever@teczno.com'))

            self.assertFalse(view_functions.is_allowed_email(no_file(), 'mike@codeforamerica.org'))
            self.assertFalse(view_functions.is_allowed_email(no_file(), 'frances@codeforamerica.org'))
            self.assertFalse(view_functions.is_allowed_email(no_file(), 'mike@teczno.com'))
            self.assertFalse(view_functions.is_allowed_email(no_file(), 'whatever@teczno.com'))

''' Test functions that are called outside of the google authing/analytics data fetching via the UI
'''
class TestGoogleApiFunctions (TestCase):

    def setUp(self):
        self.old_tempdir, tempfile.tempdir = tempfile.tempdir, mkdtemp(prefix='chime-TestGoogleApiFunctions-')

        create_app_environ = {}
        create_app_environ['BROWSERID_URL'] = 'http://example.com'
        create_app_environ['LIVE_SITE_URL'] = 'http://example.org/'
        create_app_environ['GA_CLIENT_ID'] = 'client_id'
        create_app_environ['GA_CLIENT_SECRET'] = 'meow_secret'

        self.ga_config_dir = mkdtemp(prefix='chime-config-')
        create_app_environ['RUNNING_STATE_DIR'] = self.ga_config_dir

        self.app = create_app(create_app_environ)

        # write a tmp config file
        config_values = {
            "access_token": "meowser_token",
            "refresh_token": "refresh_meows",
            "profile_id": "12345678",
            "project_domain": "example.com"
        }
        with self.app.app_context():
            google_api_functions.write_ga_config(config_values, self.app.config['RUNNING_STATE_DIR'])

    def tearDown(self):
        rmtree(tempfile.tempdir)
        tempfile.tempdir = self.old_tempdir

    def mock_successful_request_new_google_access_token(self, url, request):
        if google_api_functions.GOOGLE_ANALYTICS_TOKENS_URL in url.geturl():
            return response(200, '''{"access_token": "meowser_access_token", "token_type": "meowser_type", "expires_in": 3920}''')
        else:
            raise Exception('01 Asked for unknown URL ' + url.geturl())

    def mock_failed_request_new_google_access_token(self, url, request):
        if google_api_functions.GOOGLE_ANALYTICS_TOKENS_URL in url.geturl():
            return response(500)
        else:
            raise Exception('02 Asked for unknown URL ' + url.geturl())

    def mock_google_analytics_authorized_response(self, url, request):
        if 'https://www.googleapis.com/analytics/' in url.geturl():
            return response(200, '''{"totalsForAllResults": {"ga:pageViews": "24", "ga:avgTimeOnPage": "67.36363636363636"}}''')

    # in TestGoogleApiFunctions
    def test_successful_request_new_google_access_token(self):
        with self.app.test_request_context():
            with HTTMock(self.mock_successful_request_new_google_access_token):
                google_api_functions.request_new_google_access_token('meowser_refresh_token', self.app.config['RUNNING_STATE_DIR'], self.app.config['GA_CLIENT_ID'], self.app.config['GA_CLIENT_SECRET'])

                with self.app.app_context():
                    ga_config = google_api_functions.read_ga_config(self.app.config['RUNNING_STATE_DIR'])
                self.assertEqual(ga_config['access_token'], 'meowser_access_token')

    # in TestGoogleApiFunctions
    def test_failure_to_request_new_google_access_token(self):
        with self.app.test_request_context():
            with HTTMock(self.mock_failed_request_new_google_access_token):
                with self.assertRaises(Exception):
                    google_api_functions.request_new_google_access_token('meowser_refresh_token', self.app.config['RUNNING_STATE_DIR'], self.app.config['GA_CLIENT_ID'], self.app.config['GA_CLIENT_SECRET'])

    # in TestGoogleApiFunctions
    def test_read_missing_config_file(self):
        ''' Make sure that reading from a missing google analytics config file doesn't raise errors.
        '''
        with self.app.app_context():
            ga_config_path = join(self.app.config['RUNNING_STATE_DIR'], google_api_functions.GA_CONFIG_FILENAME)
            # verify that the file exists
            self.assertTrue(isfile(ga_config_path))
            # remove the file
            remove(ga_config_path)
            # verify that the file's gone
            self.assertFalse(isfile(ga_config_path))
            # ask for the config contents
            ga_config = google_api_functions.read_ga_config(self.app.config['RUNNING_STATE_DIR'])
            # there are four values
            self.assertEqual(len(ga_config), 4)
            # they are named as expected
            self.assertTrue(u'access_token' in ga_config)
            self.assertTrue(u'refresh_token' in ga_config)
            self.assertTrue(u'project_domain' in ga_config)
            self.assertTrue(u'profile_id' in ga_config)
            # their values are empty strings
            self.assertEqual(ga_config['access_token'], u'')
            self.assertEqual(ga_config['refresh_token'], u'')
            self.assertEqual(ga_config['project_domain'], u'')
            self.assertEqual(ga_config['profile_id'], u'')

    # in TestGoogleApiFunctions
    def test_write_missing_config_file(self):
        ''' Make sure that writing to a missing google analytics config file doesn't raise errors.
        '''
        with self.app.app_context():
            ga_config_path = join(self.app.config['RUNNING_STATE_DIR'], google_api_functions.GA_CONFIG_FILENAME)
            # verify that the file exists
            self.assertTrue(isfile(ga_config_path))
            # remove the file
            remove(ga_config_path)
            # verify that the file's gone
            self.assertFalse(isfile(ga_config_path))
            # try to write some dummy config values
            write_config = {
                "access_token": "meowser_token",
                "refresh_token": "refresh_meows",
                "profile_id": "12345678",
                "project_domain": "example.com"
            }
            # write the config contents
            google_api_functions.write_ga_config(write_config, self.app.config['RUNNING_STATE_DIR'])
            # verify that the file exists
            self.assertTrue(isfile(ga_config_path))
            # ask for the config contents
            ga_config = google_api_functions.read_ga_config(self.app.config['RUNNING_STATE_DIR'])
            # there are four values
            self.assertEqual(len(ga_config), 4)
            # they are named as expected
            self.assertTrue(u'access_token' in ga_config)
            self.assertTrue(u'refresh_token' in ga_config)
            self.assertTrue(u'project_domain' in ga_config)
            self.assertTrue(u'profile_id' in ga_config)
            # their values are as expected (including the expected value set above)
            self.assertEqual(ga_config['access_token'], u'meowser_token')
            self.assertEqual(ga_config['refresh_token'], u'refresh_meows')
            self.assertEqual(ga_config['profile_id'], u'12345678')
            self.assertEqual(ga_config['project_domain'], u'example.com')

    # in TestGoogleApiFunctions
    def test_get_malformed_config_file(self):
        ''' Make sure that a malformed google analytics config file doesn't raise errors.
        '''
        with self.app.app_context():
            ga_config_path = join(self.app.config['RUNNING_STATE_DIR'], google_api_functions.GA_CONFIG_FILENAME)
            # verify that the file exists
            self.assertTrue(isfile(ga_config_path))
            # remove the file
            remove(ga_config_path)
            # verify that the file's gone
            self.assertFalse(isfile(ga_config_path))
            # write some garbage to the file
            with google_api_functions.WriteLocked(ga_config_path) as iofile:
                iofile.seek(0)
                iofile.truncate(0)
                iofile.write('{"access_token": "meowser_access_token", "refresh_token": "meowser_refre')
            # verify that the file exists
            self.assertTrue(isfile(ga_config_path))
            # ask for the config contents
            ga_config = google_api_functions.read_ga_config(self.app.config['RUNNING_STATE_DIR'])
            # there are four values
            self.assertEqual(len(ga_config), 4)
            # they are named as expected
            self.assertTrue(u'access_token' in ga_config)
            self.assertTrue(u'refresh_token' in ga_config)
            self.assertTrue(u'project_domain' in ga_config)
            self.assertTrue(u'profile_id' in ga_config)
            # their values are empty strings
            self.assertEqual(ga_config['access_token'], u'')
            self.assertEqual(ga_config['refresh_token'], u'')
            self.assertEqual(ga_config['profile_id'], u'')
            self.assertEqual(ga_config['project_domain'], u'')
            # verify that the file exists again
            self.assertTrue(isfile(ga_config_path))

    # in TestGoogleApiFunctions
    def test_write_unexpected_values_to_config(self):
        ''' Make sure that we can't write unexpected values to the google analytics config file.
        '''
        with self.app.app_context():
            # try to write some unexpected values to the config
            unexpected_values = {
                "esme_cordelia_hoggett": "magda_szubanski",
                "farmer_arthur_hoggett": "james_cromwell",
                "hot_headed_chef": "paul_livingston",
                "woman_in_billowing_gown": "saskia_campbell"
            }
            # include an expected value too
            unexpected_values['access_token'] = u'woofer_token'
            google_api_functions.write_ga_config(unexpected_values, self.app.config['RUNNING_STATE_DIR'])
            # ask for the config contents
            ga_config = google_api_functions.read_ga_config(self.app.config['RUNNING_STATE_DIR'])
            # there are four values
            self.assertEqual(len(ga_config), 4)
            # they are named as expected
            self.assertTrue(u'access_token' in ga_config)
            self.assertTrue(u'refresh_token' in ga_config)
            self.assertTrue(u'profile_id' in ga_config)
            self.assertTrue(u'project_domain' in ga_config)
            # their values are as expected (including the expected value set above)
            self.assertEqual(ga_config['access_token'], u'woofer_token')
            self.assertEqual(ga_config['refresh_token'], u'refresh_meows')
            self.assertEqual(ga_config['profile_id'], u'12345678')
            self.assertEqual(ga_config['project_domain'], u'example.com')

    # in TestGoogleApiFunctions
    def test_get_analytics_page_path_pattern(self):
        ''' Verify that we're getting good page path patterns for querying google analytics
        '''
        ga_domain = 'www.codeforamerica.org'

        path_in = u'index.html'
        pattern_out = google_api_functions.get_ga_page_path_pattern(path_in, ga_domain)
        self.assertEqual(pattern_out, u'{ga_domain}/(index.html|index|)'.format(**locals()))

        path_in = u'help.md'
        pattern_out = google_api_functions.get_ga_page_path_pattern(path_in, ga_domain)
        self.assertEqual(pattern_out, u'{ga_domain}/(help.md|help)'.format(**locals()))

        path_in = u'people/michal-migurski/index.html'
        pattern_out = google_api_functions.get_ga_page_path_pattern(path_in, ga_domain)
        self.assertEqual(pattern_out, u'{ga_domain}/people/michal-migurski/(index.html|index|)'.format(**locals()))

    # in TestGoogleApiFunctions
    def test_handle_good_analytics_response(self):
        ''' Verify that an authorized analytics response is handled correctly
        '''
        with HTTMock(self.mock_google_analytics_authorized_response):
            with self.app.app_context():
                analytics_dict = google_api_functions.fetch_google_analytics_for_page(self.app.config, u'index.html', 'meowser_token')
            self.assertEqual(analytics_dict['page_views'], u'24')
            self.assertEqual(analytics_dict['average_time_page'], u'67')

    # in TestGoogleApiFunctions
    def test_google_access_token_functions(self):
        ''' makes sure that the file loads properly
        '''
        self.assertIsNotNone(google_access_token_update.parser)

class TestHttpdStuff (TestCase):
    def test_load(self):
        from chime import httpd
        ''' makes sure that the file loads properly
        '''
        self.assertIsNotNone(httpd.config)


if __name__ == '__main__':
    main()
