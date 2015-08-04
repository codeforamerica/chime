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

from unit.chime_test_client import ChimeTestClient

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

PATTERN_FLASH_SAVED_CATEGORY = u'<li class="flash flash--notice">Saved changes to the {title} category! Remember to submit this change for feedback when you\'re ready to go live.</li>'
PATTERN_FLASH_CREATED_CATEGORY = u'Created a new category named {title}! Remember to submit this change for feedback when you\'re ready to go live.'
PATTERN_FLASH_CREATED_ARTICLE = u'Created a new article named {title}! Remember to submit this change for feedback when you\'re ready to go live.'
PATTERN_FLASH_SAVED_ARTICLE = u'Saved changes to the {title} article! Remember to submit this change for feedback when you\'re ready to go live.'
PATTERN_FORM_CATEGORY_TITLE = u'<input name="en-title" type="text" value="{title}" class="directory-modify__name">'
PATTERN_FORM_CATEGORY_DESCRIPTION = u'<textarea name="en-description" class="directory-modify__description">{description}</textarea>'

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
            {'modified_date': view_functions.get_relative_date(self.clone, 'index.md'), 'name': 'index.md', 'title': 'index.md', 'view_path': '/tree/master/view/index.md', 'is_editable': True, 'display_type': view_functions.FILE_FILE_TYPE},
            {'modified_date': view_functions.get_relative_date(self.clone, 'other'), 'name': 'other', 'title': 'other', 'view_path': '/tree/master/view/other', 'is_editable': False, 'display_type': view_functions.FOLDER_FILE_TYPE},
            {'modified_date': view_functions.get_relative_date(self.clone, 'other.md'), 'name': 'other.md', 'title': 'other.md', 'view_path': '/tree/master/view/other.md', 'is_editable': True, 'display_type': view_functions.FILE_FILE_TYPE},
            {'modified_date': view_functions.get_relative_date(self.clone, 'sub'), 'name': 'sub', 'title': 'sub', 'view_path': '/tree/master/view/sub', 'is_editable': False, 'display_type': view_functions.FOLDER_FILE_TYPE}]

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

class TestRepo (TestCase):

    def setUp(self):
        self.old_tempdir, tempfile.tempdir = tempfile.tempdir, mkdtemp(prefix='chime-TestRepo-')

        self.work_path = mkdtemp(prefix='chime-repo-clones-')
        repo_path = dirname(abspath(__file__)) + '/../test-app.git'
        temp_repo_dir = mkdtemp(prefix='chime-root')
        temp_repo_path = temp_repo_dir + '/test-app.git'
        copytree(repo_path, temp_repo_path)
        self.origin = ChimeRepo(temp_repo_path)
        repo_functions.ignore_task_metadata_on_merge(self.origin)

        self.clone1 = self.origin.clone(mkdtemp(prefix='chime-'))
        repo_functions.ignore_task_metadata_on_merge(self.clone1)
        self.clone2 = self.origin.clone(mkdtemp(prefix='chime-'))
        repo_functions.ignore_task_metadata_on_merge(self.clone2)

        self.session = dict(email=str(uuid4()))

        environ['GIT_AUTHOR_NAME'] = ' '
        environ['GIT_COMMITTER_NAME'] = ' '
        environ['GIT_AUTHOR_EMAIL'] = self.session['email']
        environ['GIT_COMMITTER_EMAIL'] = self.session['email']

    def tearDown(self):
        rmtree(tempfile.tempdir)
        tempfile.tempdir = self.old_tempdir

    # in TestRepo
    def test_repo_features(self):
        self.assertTrue(self.origin.bare)

        branch_names = [b.name for b in self.origin.branches]
        self.assertEqual(set(branch_names), set(['master', 'title', 'body']))

    # in TestRepo
    def test_get_start_branch(self):
        ''' Make a simple edit in a clone, verify that it appears in the other.
        '''
        task_description, task_beneficiary = str(uuid4()), str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, u'erica@example.com')

        self.assertTrue(branch1.name in self.clone1.branches)
        self.assertTrue(branch1.name in self.origin.branches)

        #
        # Make a change to the branch and push it.
        #
        branch1.checkout()
        message = str(uuid4())

        with open(join(self.clone1.working_dir, 'index.md'), 'a') as file:
            file.write('\n\n...')

        args = self.clone1, 'index.md', message, branch1.commit.hexsha, 'master'
        repo_functions.save_working_file(*args)

        #
        # See if the branch made it to clone 2
        #
        branch2 = repo_functions.get_existing_branch(self.clone2, 'master', branch1.name)

        self.assertTrue(branch2.name in self.clone2.branches)
        self.assertEqual(branch2.commit.hexsha, branch1.commit.hexsha)
        self.assertEqual(branch2.commit.message, message)

    # in TestRepo
    def test_get_start_branch_2(self):
        ''' Make a simple edit in a clone, verify that it appears in the other.
        '''
        task_description, task_beneficiary = str(uuid4()), str(uuid4())

        #
        # Check out both clones.
        #
        self.clone1.branches.master.checkout()
        self.clone2.branches.master.checkout()

        self.assertEqual(self.clone1.refs['master'].commit.hexsha, self.origin.refs['master'].commit.hexsha)
        self.assertEqual(self.clone1.refs['master'].commit.hexsha, self.clone2.refs['master'].commit.hexsha)

        #
        # Make a change to the first clone and push it.
        #
        with open(join(self.clone1.working_dir, 'index.md'), 'a') as file:
            file.write('\n\n...')

        message = str(uuid4())
        args = self.clone1, 'index.md', message, self.clone1.commit().hexsha, 'master'
        repo_functions.save_working_file(*args)

        #
        # Origin now has the updated master, but the second clone does not.
        #
        self.assertEqual(self.clone1.refs['master'].commit.hexsha, self.origin.refs['master'].commit.hexsha)
        self.assertNotEquals(self.clone1.refs['master'].commit.hexsha, self.clone2.refs['master'].commit.hexsha)

        #
        # Now start a new branch from the second clone, and look for the new master commit.
        #
        branch2 = repo_functions.get_start_branch(self.clone2, 'master', task_description, task_beneficiary, self.session['email'])

        self.assertTrue(branch2.name in self.clone2.branches)
        # compare the second-to-last commit on branch2 (by adding ".parents[0]", as
        # the most recent one is the creation of the task metadata file
        self.assertEqual(branch2.commit.parents[0].hexsha, self.origin.refs['master'].commit.hexsha)

    # in TestRepo
    def test_delete_missing_branch(self):
        ''' Delete a branch in a clone that's still in origin, see if it can be deleted anyway.
        '''
        task_description, task_beneficiary = str(uuid4()), str(uuid4())

        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, u'erica@example.com')

        self.assertTrue(branch1.name in self.origin.branches)

        self.clone2.git.fetch('origin')

        self.assertTrue(branch1.name in self.origin.branches)
        self.assertTrue('origin/' + branch1.name in self.clone2.refs)

        repo_functions.abandon_branch(self.clone2, 'master', branch1.name)

        self.assertFalse(branch1.name in self.origin.branches)
        self.assertFalse('origin/' + branch1.name in self.clone2.refs)
        self.assertFalse(branch1.name in self.clone2.branches)

    # in TestRepo
    def test_new_file(self):
        ''' Make a new file and delete an old file in a clone, verify that the changes appear in the other.
        '''
        task_description, task_beneficiary = str(uuid4()), str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, self.session['email'])

        self.assertTrue(branch1.name in self.clone1.branches)
        self.assertTrue(branch1.name in self.origin.branches)

        #
        # Make a new file in the branch and push it.
        #
        branch1.checkout()

        edit_functions.create_new_page(self.clone1, '', 'hello.md',
                                       dict(title='Hello'), 'Hello hello.')

        args = self.clone1, 'hello.md', str(uuid4()), branch1.commit.hexsha, 'master'
        repo_functions.save_working_file(*args)

        #
        # Delete an existing file in the branch and push it.
        #
        message = str(uuid4())

        edit_functions.delete_file(self.clone1, 'index.md')

        args = self.clone1, 'index.md', message, branch1.commit.hexsha, 'master'
        repo_functions.save_working_file(*args)

        #
        # See if the changes made it to clone 2
        #
        branch2 = repo_functions.get_existing_branch(self.clone2, 'master', branch1.name)

        self.assertTrue(branch2.name in self.clone2.branches)
        self.assertEqual(branch2.commit.hexsha, branch1.commit.hexsha)
        self.assertEqual(branch2.commit.message, message)
        self.assertEqual(branch2.commit.author.email, self.session['email'])
        self.assertEqual(branch2.commit.committer.email, self.session['email'])

        branch2.checkout()

        with open(join(self.clone2.working_dir, 'hello.md')) as file:
            front, body = jekyll_functions.load_jekyll_doc(file)

            self.assertEqual(front['title'], 'Hello')
            self.assertEqual(body, 'Hello hello.')

        self.assertFalse(exists(join(self.clone2.working_dir, 'index.md')))

    # in TestRepo
    def test_try_to_create_existing_category(self):
        ''' We can't create a category that exists already.
        '''
        first_result = view_functions.add_article_or_category(self.clone1, 'categories', 'My New Category', view_functions.CATEGORY_LAYOUT)
        self.assertEqual(u'The "My New Category" category was created\n\n[{"action": "create", "file_path": "categories/my-new-category/index.markdown", "display_type": "category", "title": "My New Category"}]', first_result[0])
        self.assertEqual(u'categories/my-new-category/index.markdown', first_result[1])
        self.assertEqual(u'categories/my-new-category/', first_result[2])
        self.assertEqual(True, first_result[3])
        second_result = view_functions.add_article_or_category(self.clone1, 'categories', 'My New Category', view_functions.CATEGORY_LAYOUT)
        self.assertEqual('Category "My New Category" already exists', second_result[0])
        self.assertEqual(u'categories/my-new-category/index.markdown', second_result[1])
        self.assertEqual(u'categories/my-new-category/', second_result[2])
        self.assertEqual(False, second_result[3])

    # in TestRepo
    def test_try_to_create_existing_article(self):
        ''' We can't create an article that exists already
        '''
        first_result = view_functions.add_article_or_category(self.clone1, 'categories/example', 'New Article', view_functions.ARTICLE_LAYOUT)
        self.assertEqual(u'The "New Article" article was created\n\n[{"action": "create", "file_path": "categories/example/new-article/index.markdown", "display_type": "article", "title": "New Article"}]', first_result[0])
        self.assertEqual(u'categories/example/new-article/index.markdown', first_result[1])
        self.assertEqual(u'categories/example/new-article/index.markdown', first_result[2])
        self.assertEqual(True, first_result[3])
        second_result = view_functions.add_article_or_category(self.clone1, 'categories/example', 'New Article', view_functions.ARTICLE_LAYOUT)
        self.assertEqual('Article "New Article" already exists', second_result[0])
        self.assertEqual(u'categories/example/new-article/index.markdown', first_result[1])
        self.assertEqual(u'categories/example/new-article/index.markdown', first_result[2])
        self.assertEqual(False, second_result[3])

    # in TestRepo
    def test_delete_directory(self):
        ''' Make a new file and directory and delete them.
        '''
        task_description, task_beneficiary = str(uuid4()), str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, u'erica@example.com')

        self.assertTrue(branch1.name in self.clone1.branches)
        self.assertTrue(branch1.name in self.origin.branches)

        #
        # Make a new file in a directory on the branch and push it.
        #
        branch1.checkout()

        edit_functions.create_new_page(self.clone1, 'hello/', 'hello.md',
                                       dict(title='Hello'), 'Hello hello.')

        args = self.clone1, 'hello/hello.md', str(uuid4()), branch1.commit.hexsha, 'master'
        repo_functions.save_working_file(*args)

        #
        # Delete the file and folder just created and push the changes.
        #
        message = str(uuid4())

        edit_functions.delete_file(self.clone1, 'hello/hello.md')

        args = self.clone1, 'hello/hello.md', message, branch1.commit.hexsha, 'master'
        repo_functions.save_working_file(*args)

        self.assertFalse(exists(join(self.clone1.working_dir, 'hello/hello.md')))

        edit_functions.delete_file(self.clone1, 'hello/')

        self.assertFalse(exists(join(self.clone1.working_dir, 'hello/')))

    # in TestRepo
    def test_move_file(self):
        ''' Change the path of a file.
        '''
        task_description, task_beneficiary = str(uuid4()), str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, u'erica@example.com')

        self.assertTrue(branch1.name in self.clone1.branches)
        self.assertTrue(branch1.name in self.origin.branches)

        #
        # Rename a file in the branch.
        #
        branch1.checkout()

        args = self.clone1, 'index.md', 'hello/world.md', branch1.commit.hexsha, 'master'
        repo_functions.move_existing_file(*args)

        #
        # See if the new file made it to clone 2
        #
        branch2 = repo_functions.get_existing_branch(self.clone2, 'master', branch1.name)
        branch2.checkout()

        self.assertTrue(exists(join(self.clone2.working_dir, 'hello/world.md')))
        self.assertFalse(exists(join(self.clone2.working_dir, 'index.md')))

    # in TestRepo
    def test_content_merge(self):
        ''' Test that non-conflicting changes on the same file merge cleanly.
        '''
        title_branch_name = 'title'
        body_branch_name = 'body'
        title_branch = repo_functions.get_existing_branch(self.clone1, 'master', title_branch_name)
        body_branch = repo_functions.get_existing_branch(self.clone2, 'master', body_branch_name)

        title_branch.checkout()
        body_branch.checkout()

        with open(self.clone1.working_dir + '/index.md') as file:
            front1, _ = jekyll_functions.load_jekyll_doc(file)

        with open(self.clone2.working_dir + '/index.md') as file:
            _, body2 = jekyll_functions.load_jekyll_doc(file)

        #
        # Show that only the title branch title is now present on master.
        #
        repo_functions.complete_branch(self.clone1, 'master', title_branch_name)

        with open(self.clone1.working_dir + '/index.md') as file:
            front1b, body1b = jekyll_functions.load_jekyll_doc(file)

        title_key_name = 'title'
        self.assertEqual(front1b[title_key_name], front1[title_key_name])
        self.assertNotEqual(body1b, body2)

        #
        # Show that the body branch body is also now present on master.
        #
        repo_functions.complete_branch(self.clone2, 'master', 'body')

        with open(self.clone2.working_dir + '/index.md') as file:
            front2b, body2b = jekyll_functions.load_jekyll_doc(file)

        self.assertEqual(front2b[title_key_name], front1[title_key_name])
        self.assertEqual(body2b, body2)
        self.assertTrue(repo_functions.ACTIVITY_PUBLISHED_MESSAGE in self.clone2.commit().message)

    # in TestRepo
    def test_content_merge_extra_change(self):
        ''' Test that non-conflicting changes on the same file merge cleanly.
        '''
        title_branch_name = 'title'
        body_branch_name = 'body'
        title_branch = repo_functions.get_existing_branch(self.clone1, 'master', title_branch_name)
        body_branch = repo_functions.get_existing_branch(self.clone2, 'master', body_branch_name)

        title_branch.checkout()
        body_branch.checkout()

        with open(self.clone1.working_dir + '/index.md') as file:
            front1, _ = jekyll_functions.load_jekyll_doc(file)

        with open(self.clone2.working_dir + '/index.md') as file:
            front2, body2 = jekyll_functions.load_jekyll_doc(file)

        #
        # Show that only the title branch title is now present on master.
        #
        repo_functions.complete_branch(self.clone1, 'master', title_branch_name)

        with open(self.clone1.working_dir + '/index.md') as file:
            front1b, body1b = jekyll_functions.load_jekyll_doc(file)

        title_key_name = 'title'
        self.assertEqual(front1b[title_key_name], front1[title_key_name])
        self.assertNotEqual(body1b, body2)

        #
        # Show that the body branch body is also now present on master.
        #
        edit_functions.update_page(self.clone2, 'index.md',
                                   front2, 'Another change to the body')

        repo_functions.save_working_file(self.clone2, 'index.md', 'A new change',
                                         self.clone2.commit().hexsha, 'master')

        #
        # Show that upstream changes from master have been merged here.
        #
        with open(self.clone2.working_dir + '/index.md') as file:
            front2b, body2b = jekyll_functions.load_jekyll_doc(file)

        self.assertEqual(front2b[title_key_name], front1[title_key_name])
        self.assertEqual(body2b.strip(), 'Another change to the body')
        self.assertTrue(self.clone2.commit().message.startswith('Merged work from'))

    # in TestRepo
    def test_multifile_merge(self):
        ''' Test that two non-conflicting new files merge cleanly.
        '''
        fake_author_email = u'erica@example.com'
        task_description, task_beneficiary = str(uuid4()), str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
        branch2 = repo_functions.get_start_branch(self.clone2, 'master', task_description, task_beneficiary, fake_author_email)
        branch1_name, branch2_name = branch1.name, branch2.name

        #
        # Make new files in each branch and save them.
        #
        branch1.checkout()
        branch2.checkout()

        edit_functions.create_new_page(self.clone1, '', 'file1.md',
                                       dict(title='Hello'), 'Hello hello.')

        edit_functions.create_new_page(self.clone2, '', 'file2.md',
                                       dict(title='Goodbye'), 'Goodbye goodbye.')

        #
        # Show that the changes from the first branch made it to origin.
        #
        args1 = self.clone1, 'file1.md', '...', branch1.commit.hexsha, 'master'
        commit1 = repo_functions.save_working_file(*args1)

        self.assertEqual(self.origin.branches[branch1_name].commit, commit1)
        self.assertEqual(self.origin.branches[branch1_name].commit.author.email, self.session['email'])
        self.assertEqual(self.origin.branches[branch1_name].commit.committer.email, self.session['email'])
        self.assertEqual(commit1, branch1.commit)

        #
        # Show that the changes from the second branch also made it to origin.
        #
        args2 = self.clone2, 'file2.md', '...', branch2.commit.hexsha, 'master'
        commit2 = repo_functions.save_working_file(*args2)

        self.assertEqual(self.origin.branches[branch2_name].commit, commit2)
        self.assertEqual(self.origin.branches[branch2_name].commit.author.email, self.session['email'])
        self.assertEqual(self.origin.branches[branch2_name].commit.committer.email, self.session['email'])
        self.assertEqual(commit2, branch2.commit)

        #
        # Show that the merge from the second branch made it back to the first.
        #
        branch1b = repo_functions.get_existing_branch(self.clone1, 'master', branch2.name)

        self.assertEqual(branch1b.commit, branch2.commit)
        self.assertEqual(branch1b.commit.author.email, self.session['email'])
        self.assertEqual(branch1b.commit.committer.email, self.session['email'])

    # in TestRepo
    def test_same_branch_conflict(self):
        ''' Test that a conflict in two branches appears at the right spot.
        '''
        fake_author_email = u'erica@example.com'
        task_description, task_beneficiary = str(uuid4()), str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
        branch2 = repo_functions.get_existing_branch(self.clone2, 'master', branch1.name)
        branch1_name = branch1.name
        self.assertIsNotNone(branch2)
        self.assertEqual(branch2.name, branch1_name)

        #
        # Make new files in each branch and save them.
        #
        branch1.checkout()
        branch2.checkout()

        edit_functions.create_new_page(self.clone1, '', 'conflict.md',
                                       dict(title='Hello'), 'Hello hello.')

        edit_functions.create_new_page(self.clone2, '', 'conflict.md',
                                       dict(title='Goodbye'), 'Goodbye goodbye.')

        #
        # Show that the changes from the first branch made it to origin.
        #
        args1 = self.clone1, 'conflict.md', '...', branch1.commit.hexsha, 'master'
        commit1 = repo_functions.save_working_file(*args1)

        self.assertEqual(self.origin.branches[branch1_name].commit, commit1)
        self.assertEqual(commit1, branch1.commit)

        #
        # Show that the changes from the second branch conflict with the first.
        #
        with self.assertRaises(repo_functions.MergeConflict) as conflict:
            args2 = self.clone2, 'conflict.md', '...', branch2.commit.hexsha, 'master'
            repo_functions.save_working_file(*args2)

        self.assertEqual(conflict.exception.remote_commit, commit1)

        diffs = conflict.exception.remote_commit.diff(conflict.exception.local_commit)

        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].a_blob.name, 'conflict.md')
        self.assertEqual(diffs[0].b_blob.name, 'conflict.md')

    # in TestRepo
    def test_upstream_pull_conflict(self):
        ''' Test that a conflict in two branches appears at the right spot.
        '''
        fake_author_email = u'erica@example.com'
        task_description1, task_description2 = str(uuid4()), str(uuid4())
        task_beneficiary1, task_beneficiary2 = str(uuid4()), str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description1, task_beneficiary1, fake_author_email)
        branch2 = repo_functions.get_start_branch(self.clone2, 'master', task_description2, task_beneficiary2, fake_author_email)
        branch1_name = branch1.name

        #
        # Make new files in each branch and save them.
        #
        branch1.checkout()
        branch2.checkout()

        edit_functions.create_new_page(self.clone1, '', 'conflict.md',
                                       dict(title='Hello'), 'Hello hello.')

        edit_functions.create_new_page(self.clone2, '', 'conflict.md',
                                       dict(title='Goodbye'), 'Goodbye goodbye.')

        #
        # Show that the changes from the first branch made it to origin.
        #
        args1 = self.clone1, 'conflict.md', '...', branch1.commit.hexsha, 'master'
        commit1 = repo_functions.save_working_file(*args1)

        self.assertEqual(self.origin.branches[branch1_name].commit, commit1)
        self.assertEqual(commit1, branch1.commit)

        #
        # Merge the first branch to master.
        #
        commit2 = repo_functions.complete_branch(self.clone1, 'master', branch1_name)
        self.assertFalse(branch1_name in self.origin.branches)

        #
        # Show that the changes from the second branch conflict with the first.
        #
        with self.assertRaises(repo_functions.MergeConflict) as conflict:
            args2 = self.clone2, 'conflict.md', '...', branch2.commit.hexsha, 'master'
            repo_functions.save_working_file(*args2)

        self.assertEqual(conflict.exception.remote_commit, commit2)

        diffs = conflict.exception.remote_commit.diff(conflict.exception.local_commit)

        # there are two diffs; the first is addition of the
        # task metadata file, the second is the conflict file
        self.assertEqual(len(diffs), 2)
        self.assertIsNone(diffs[0].a_blob)
        self.assertEqual(diffs[0].b_blob.name, repo_functions.TASK_METADATA_FILENAME)
        self.assertEqual(diffs[1].a_blob.name, 'conflict.md')
        self.assertEqual(diffs[1].b_blob.name, 'conflict.md')

    # in TestRepo
    def test_upstream_push_conflict(self):
        ''' Test that a conflict in two branches appears at the right spot.
        '''
        fake_author_email = u'erica@example.com'
        task_description1, task_description2 = str(uuid4()), str(uuid4())
        task_beneficiary1, task_beneficiary2 = str(uuid4()), str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description1, task_beneficiary1, fake_author_email)
        branch2 = repo_functions.get_start_branch(self.clone2, 'master', task_description2, task_beneficiary2, fake_author_email)
        branch1_name, branch2_name = branch1.name, branch2.name

        #
        # Make new files in each branch and save them.
        #
        branch1.checkout()
        branch2.checkout()

        edit_functions.create_new_page(self.clone1, '', 'conflict.md',
                                       dict(title='Hello'), 'Hello hello.')

        edit_functions.create_new_page(self.clone2, '', 'conflict.md',
                                       dict(title='Goodbye'), 'Goodbye goodbye.')

        #
        # Push changes from the two branches to origin.
        #
        args1 = self.clone1, 'conflict.md', '...', branch1.commit.hexsha, 'master'
        repo_functions.save_working_file(*args1)

        args2 = self.clone2, 'conflict.md', '...', branch2.commit.hexsha, 'master'
        repo_functions.save_working_file(*args2)

        #
        # Merge the two branches to master; show that second merge will fail.
        #
        repo_functions.complete_branch(self.clone1, 'master', branch1_name)
        self.assertFalse(branch1_name in self.origin.branches)

        with self.assertRaises(repo_functions.MergeConflict) as conflict:
            repo_functions.complete_branch(self.clone2, 'master', branch2_name)

        self.assertEqual(conflict.exception.remote_commit, self.origin.commit())
        self.assertEqual(conflict.exception.local_commit, self.clone2.commit())

        # conflict.exception is the MergeConflict exception object
        conflict_files = conflict.exception.files()
        edited_files = [item for item in conflict_files if item['actions'] == repo_functions.CONFLICT_ACTION_EDITED]
        self.assertEqual(len(edited_files), 1)
        self.assertEqual(edited_files[0]['path'], 'conflict.md')

    # in TestRepo
    def test_conflict_resolution_clobber(self):
        ''' Test that a conflict in two branches can be clobbered.
        '''
        fake_author_email = u'erica@example.com'
        task_description, task_beneficiary = str(uuid4()), str(uuid4())
        title_branch = repo_functions.get_existing_branch(self.clone1, 'master', 'title')
        compare_branch = repo_functions.get_start_branch(self.clone2, 'master', task_description, task_beneficiary, fake_author_email)
        title_branch_name, compare_branch_name = title_branch.name, compare_branch.name

        #
        # Add goner.md in title_branch.
        #
        title_branch.checkout()

        edit_functions.create_new_page(self.clone1, '', 'goner.md',
                                       dict(title=task_description), 'Woooo woooo.')

        args = self.clone1, 'goner.md', '...', title_branch.commit.hexsha, 'master'
        commit = repo_functions.save_working_file(*args)

        #
        # Change index.md in compare_branch so it conflicts with the title branch.
        #
        compare_branch.checkout()

        edit_functions.update_page(self.clone2, 'index.md',
                                   dict(title=task_description), 'Hello hello.')

        args = self.clone2, 'index.md', '...', compare_branch.commit.hexsha, 'master'
        commit = repo_functions.save_working_file(*args)

        #
        # Merge the original title branch, fail to merge our conflicting branch.
        #
        repo_functions.complete_branch(self.clone1, 'master', title_branch_name)

        with self.assertRaises(repo_functions.MergeConflict) as conflict:
            repo_functions.complete_branch(self.clone2, 'master', compare_branch_name)

        self.assertEqual(conflict.exception.local_commit, commit)

        diffs = conflict.exception.remote_commit.diff(conflict.exception.local_commit)

        self.assertEqual(len(diffs), 3)
        for diff in diffs:
            if diff.a_blob:
                self.assertTrue(diff.a_blob.name in ('index.md', 'goner.md'))

        #
        # Merge our conflicting branch and clobber the default branch.
        #
        repo_functions.clobber_default_branch(self.clone2, 'master', compare_branch_name)

        with open(join(self.clone2.working_dir, 'index.md')) as file:
            front, body = jekyll_functions.load_jekyll_doc(file)

        self.assertEqual(front['title'], task_description)
        self.assertFalse(compare_branch_name in self.origin.branches)

        # If goner.md is still around, then master wasn't fully clobbered.
        self.clone1.branches['master'].checkout()
        self.clone1.git.pull('origin', 'master')
        self.assertFalse(exists(join(self.clone2.working_dir, 'goner.md')))
        self.assertTrue(self.clone2.commit().message.startswith('Clobbered with work from'))

    # in TestRepo
    def test_conflict_resolution_abandon(self):
        ''' Test that a conflict in two branches can be abandoned.
        '''
        fake_author_email = u'erica@example.com'
        task_description, task_beneficiary = str(uuid4()), str(uuid4())
        title_branch_name = 'title'
        repo_functions.get_existing_branch(self.clone1, 'master', title_branch_name)
        compare_branch = repo_functions.get_start_branch(self.clone2, 'master', task_description, task_beneficiary, fake_author_email)
        compare_branch_name = compare_branch.name

        #
        # Change index.md in compare_branch so it conflicts with title branch.
        # Also add goner.md, which we'll later want to disappear.
        #
        compare_branch.checkout()

        edit_functions.update_page(self.clone2, 'index.md',
                                   dict(title=task_description), 'Hello hello.')

        edit_functions.create_new_page(self.clone2, '', 'goner.md',
                                       dict(title=task_description), 'Woooo woooo.')

        args = self.clone2, 'index.md', '...', compare_branch.commit.hexsha, 'master'
        commit = repo_functions.save_working_file(*args)

        args = self.clone2, 'goner.md', '...', compare_branch.commit.hexsha, 'master'
        commit = repo_functions.save_working_file(*args)

        #
        # Merge the original title branch, fail to merge our conflicting branch.
        #
        repo_functions.complete_branch(self.clone1, 'master', title_branch_name)

        with self.assertRaises(repo_functions.MergeConflict) as conflict:
            repo_functions.complete_branch(self.clone2, 'master', compare_branch_name)

        self.assertEqual(conflict.exception.local_commit, commit)

        diffs = conflict.exception.remote_commit.diff(conflict.exception.local_commit)

        self.assertEqual(len(diffs), 3)
        self.assertTrue(diffs[0].b_blob.name in ('index.md', 'goner.md', repo_functions.TASK_METADATA_FILENAME))
        self.assertTrue(diffs[1].b_blob.name in ('index.md', 'goner.md', repo_functions.TASK_METADATA_FILENAME))
        self.assertTrue(diffs[2].b_blob.name in ('index.md', 'goner.md', repo_functions.TASK_METADATA_FILENAME))

        #
        # Merge our conflicting branch and abandon it to the default branch.
        #
        repo_functions.abandon_branch(self.clone2, 'master', compare_branch_name)

        with open(join(self.clone2.working_dir, 'index.md')) as file:
            front, body = jekyll_functions.load_jekyll_doc(file)

        self.assertNotEqual(front['title'], task_description)
        self.assertFalse(compare_branch_name in self.origin.branches)

        # If goner.md is still around, then the branch wasn't fully abandoned.
        self.assertFalse(exists(join(self.clone2.working_dir, 'goner.md')))
        self.assertTrue(self.clone2.commit().message.startswith('Abandoned work from'))

    # in TestRepo
    def test_peer_review(self):
        ''' Exercise the review process
        '''
        fake_author_email = u'erica@example.com'
        task_description, task_beneficiary = str(uuid4()), str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
        branch1_name = branch1.name

        #
        # Make a commit.
        #
        fake_creator_email = u'creator@example.com'
        environ['GIT_AUTHOR_NAME'] = 'Jim Content Creator'
        environ['GIT_COMMITTER_NAME'] = 'Jim Content Creator'
        environ['GIT_AUTHOR_EMAIL'] = fake_creator_email
        environ['GIT_COMMITTER_EMAIL'] = fake_creator_email

        branch1.checkout()
        review_state, review_authorized = repo_functions.get_review_state_and_authorized(self.clone1, 'master', branch1_name, fake_author_email)
        self.assertEqual(review_state, repo_functions.REVIEW_STATE_FRESH)
        self.assertTrue(review_authorized)

        edit_functions.update_page(self.clone1, 'index.md',
                                   dict(title=task_description), 'Hello you-all.')

        repo_functions.save_working_file(self.clone1, 'index.md', 'I made a change',
                                         self.clone1.commit().hexsha, 'master')

        # verify that the activity has unreviewed edits and that Jim Content Creator is authorized to request feedback
        review_state, review_authorized = repo_functions.get_review_state_and_authorized(self.clone1, 'master', branch1_name, fake_creator_email)
        self.assertEqual(review_state, repo_functions.REVIEW_STATE_EDITED)
        self.assertTrue(review_authorized)

        # request feedback as Jim Content Creator
        repo_functions.update_review_state(self.clone1, repo_functions.REVIEW_STATE_FEEDBACK)
        # verify that the activity has feedback requested and that fake is authorized to endorse
        review_state, review_authorized = repo_functions.get_review_state_and_authorized(self.clone1, 'master', branch1_name, fake_author_email)
        self.assertEqual(review_state, repo_functions.REVIEW_STATE_FEEDBACK)
        self.assertTrue(review_authorized)

        #
        # Approve the work as someone else.
        #
        fake_reviewer_email = u'reviewer@example.com'
        environ['GIT_AUTHOR_NAME'] = 'Joe Reviewer'
        environ['GIT_COMMITTER_NAME'] = 'Joe Reviewer'
        environ['GIT_AUTHOR_EMAIL'] = fake_reviewer_email
        environ['GIT_COMMITTER_EMAIL'] = fake_reviewer_email

        # endorse
        repo_functions.update_review_state(self.clone1, repo_functions.REVIEW_STATE_ENDORSED)
        # verify that the activity has been endorsed and that Joe Reviewer is authorized to publish
        review_state, review_authorized = repo_functions.get_review_state_and_authorized(self.clone1, 'master', branch1_name, fake_reviewer_email)
        self.assertEqual(review_state, repo_functions.REVIEW_STATE_ENDORSED)
        self.assertTrue(review_authorized)

        #
        # Make another commit.
        #
        edit_functions.update_page(self.clone1, 'index.md',
                                   dict(title=task_description), 'Hello you there.')

        repo_functions.save_working_file(self.clone1, 'index.md', 'I made a change',
                                         self.clone1.commit().hexsha, 'master')

        # verify that the activity has unreviewed edits and that Joe Reviewer is authorized to request feedback
        review_state, review_authorized = repo_functions.get_review_state_and_authorized(self.clone1, 'master', branch1_name, fake_reviewer_email)
        self.assertEqual(review_state, repo_functions.REVIEW_STATE_EDITED)
        self.assertTrue(review_authorized)

        # request feedback as Joe Reviewer
        repo_functions.update_review_state(self.clone1, repo_functions.REVIEW_STATE_FEEDBACK)
        # verify that the activity has feedback requested and that Joe Reviewer is not authorized to endorse
        review_state, review_authorized = repo_functions.get_review_state_and_authorized(self.clone1, 'master', branch1_name, fake_reviewer_email)
        self.assertEqual(review_state, repo_functions.REVIEW_STATE_FEEDBACK)
        self.assertFalse(review_authorized)

        #
        # Approve the work as someone else.
        #
        fake_nonprofit_email = u'reviewer@example.org'
        environ['GIT_AUTHOR_NAME'] = 'Jane Reviewer'
        environ['GIT_COMMITTER_NAME'] = 'Jane Reviewer'
        environ['GIT_AUTHOR_EMAIL'] = fake_nonprofit_email
        environ['GIT_COMMITTER_EMAIL'] = fake_nonprofit_email

        # endorse
        repo_functions.update_review_state(self.clone1, repo_functions.REVIEW_STATE_ENDORSED)
        # verify that the activity has been endorsed and that Jane Reviewer is authorized to publish
        review_state, review_authorized = repo_functions.get_review_state_and_authorized(self.clone1, 'master', branch1_name, fake_nonprofit_email)
        self.assertEqual(review_state, repo_functions.REVIEW_STATE_ENDORSED)
        self.assertTrue(review_authorized)

        #
        # Publish the work
        #
        merge_commit = repo_functions.complete_branch(clone=self.clone1, default_branch_name='master', working_branch_name=branch1_name)
        # The commit message is expected
        self.assertTrue(repo_functions.ACTIVITY_PUBLISHED_MESSAGE in merge_commit.message)
        # The branch is gone
        self.assertFalse(branch1_name in self.origin.branches)
        self.assertFalse(branch1_name in self.clone1.branches)

    # in TestRepo
    def test_article_creation_with_unicode(self):
        ''' An article with unicode in its title is created as expected.
        '''
        # start a new branch
        fake_author_email = u'erica@example.com'
        task_description = u'suck blood from a mammal'
        task_beneficiary = u'mosquito larvae'

        source_repo = self.origin
        first_commit = list(source_repo.iter_commits())[-1].hexsha
        dir_name = 'repo-{}-{}'.format(first_commit[:8], slugify(fake_author_email))
        user_dir = realpath(join(self.work_path, quote(dir_name)))

        if isdir(user_dir):
            new_clone = ChimeRepo(user_dir)
            new_clone.git.reset(hard=True)
            new_clone.remotes.origin.fetch()
        else:
            new_clone = source_repo.clone(user_dir, bare=False)

        # tell git to ignore merge conflicts on the task metadata file
        repo_functions.ignore_task_metadata_on_merge(new_clone)

        working_branch = repo_functions.get_start_branch(new_clone, 'master', task_description, task_beneficiary, fake_author_email)
        self.assertTrue(working_branch.name in new_clone.branches)
        self.assertTrue(working_branch.name in self.origin.branches)
        working_branch.checkout()

        # create an article
        art_title = u'快速狐狸'
        art_slug = slugify(art_title)
        add_message, file_path, redirect_path, do_save = view_functions.add_article_or_category(new_clone, u'', art_title, view_functions.ARTICLE_LAYOUT)
        self.assertEqual(u'{}/index.{}'.format(art_slug, view_functions.CONTENT_FILE_EXTENSION), file_path)
        self.assertEqual(u'The "{art_title}" article was created\n\n[{{"action": "create", "file_path": "{file_path}", "display_type": "article", "title": "{art_title}"}}]'.format(art_title=art_title, file_path=file_path), add_message)
        self.assertEqual(u'{}/index.{}'.format(art_slug, view_functions.CONTENT_FILE_EXTENSION), redirect_path)
        self.assertEqual(True, do_save)
        # commit the article
        repo_functions.save_working_file(new_clone, file_path, add_message, new_clone.commit().hexsha, 'master')

    # in TestRepo
    def test_edit_category_title_and_description(self):
        ''' Edits to category details are saved
        '''
        # start a new branch
        fake_author_email = u'erica@example.com'
        task_description = u'squeezing lemons'
        task_beneficiary = u'lemonade lovers'

        source_repo = self.origin
        first_commit = list(source_repo.iter_commits())[-1].hexsha
        dir_name = 'repo-{}-{}'.format(first_commit[:8], slugify(fake_author_email))
        user_dir = realpath(join(self.work_path, quote(dir_name)))

        if isdir(user_dir):
            new_clone = ChimeRepo(user_dir)
            new_clone.git.reset(hard=True)
            new_clone.remotes.origin.fetch()
        else:
            new_clone = source_repo.clone(user_dir, bare=False)

        # tell git to ignore merge conflicts on the task metadata file
        repo_functions.ignore_task_metadata_on_merge(new_clone)

        working_branch = repo_functions.get_start_branch(new_clone, 'master', task_description, task_beneficiary, fake_author_email)
        self.assertTrue(working_branch.name in new_clone.branches)
        self.assertTrue(working_branch.name in self.origin.branches)
        working_branch.checkout()

        # create a category
        cat_title = u'快速狐狸'
        cat_slug = slugify(cat_title)
        add_message, file_path, redirect_path, do_save = view_functions.add_article_or_category(new_clone, u'', cat_title, view_functions.CATEGORY_LAYOUT)
        self.assertEqual(u'{}/index.{}'.format(cat_slug, view_functions.CONTENT_FILE_EXTENSION), file_path)
        self.assertEqual(u'The "{cat_title}" category was created\n\n[{{"action": "create", "file_path": "{file_path}", "display_type": "category", "title": "{cat_title}"}}]'.format(cat_title=cat_title, file_path=file_path), add_message)
        self.assertEqual(u'{}/'.format(cat_slug), redirect_path)
        self.assertEqual(True, do_save)
        # commit the category
        repo_functions.save_working_file(new_clone, file_path, add_message, new_clone.commit().hexsha, 'master')

        index_path = join(new_clone.working_dir, file_path)

        # verify the values
        with open(index_path) as file:
            front_matter, body = jekyll_functions.load_jekyll_doc(file)
        self.assertEqual(front_matter['title'], cat_title)
        self.assertEqual(front_matter['description'], u'')
        self.assertEqual(body, u'')

        # change the values
        fake_changes = {'en-title': u'Drink Craw', 'en-description': u'Pink Straw', 'en-body': u'', 'hexsha': new_clone.commit().hexsha}
        new_values = dict(front_matter)
        new_values.update(fake_changes)
        new_path, did_save = view_functions.save_page(repo=new_clone, default_branch_name='master', working_branch_name=working_branch.name, file_path=file_path, new_values=new_values)

        # check for the new values!
        with open(index_path) as file:
            front_matter, body = jekyll_functions.load_jekyll_doc(file)
        self.assertEqual(front_matter['title'], new_values['en-title'])
        self.assertEqual(front_matter['description'], new_values['en-description'])
        self.assertEqual(body, u'')

    # in TestRepo
    def test_delete_category(self):
        ''' Create and delete a category
        '''
        # start a new branch
        fake_author_email = u'erica@example.com'
        task_description = u'grating lemons'
        task_beneficiary = u'zest lovers'

        source_repo = self.origin
        first_commit = list(source_repo.iter_commits())[-1].hexsha
        dir_name = 'repo-{}-{}'.format(first_commit[:8], slugify(fake_author_email))
        user_dir = realpath(join(self.work_path, quote(dir_name)))

        if isdir(user_dir):
            new_clone = ChimeRepo(user_dir)
            new_clone.git.reset(hard=True)
            new_clone.remotes.origin.fetch()
        else:
            new_clone = source_repo.clone(user_dir, bare=False)

        # tell git to ignore merge conflicts on the task metadata file
        repo_functions.ignore_task_metadata_on_merge(new_clone)

        working_branch = repo_functions.get_start_branch(new_clone, 'master', task_description, task_beneficiary, fake_author_email)
        self.assertTrue(working_branch.name in new_clone.branches)
        self.assertTrue(working_branch.name in self.origin.branches)
        working_branch.checkout()

        # create a category
        cat_title = u'Daffodils and Drop Cloths'
        cat_slug = slugify(cat_title)
        add_message, file_path, redirect_path, do_save = view_functions.add_article_or_category(new_clone, u'', cat_title, view_functions.CATEGORY_LAYOUT)
        self.assertEqual(u'{}/index.{}'.format(cat_slug, view_functions.CONTENT_FILE_EXTENSION), file_path)
        self.assertEqual(u'The "{cat_title}" category was created\n\n[{{"action": "create", "file_path": "{file_path}", "display_type": "category", "title": "{cat_title}"}}]'.format(cat_title=cat_title, file_path=file_path), add_message)
        self.assertEqual(u'{}/'.format(cat_slug), redirect_path)
        self.assertEqual(True, do_save)
        # commit the category
        repo_functions.save_working_file(new_clone, file_path, add_message, new_clone.commit().hexsha, 'master')

        # verify that the directory and index file exist
        cat_index_path = join(new_clone.working_dir, file_path)
        self.assertTrue(exists(cat_index_path))
        self.assertTrue(exists(view_functions.strip_index_file(cat_index_path)))

        # create a category inside that
        cat2_title = u'Drain Bawlers'
        cat2_slug = slugify(cat2_title)
        add_message, cat2_path, redirect_path, do_save = view_functions.add_article_or_category(new_clone, cat_slug, cat2_title, view_functions.CATEGORY_LAYOUT)
        self.assertEqual(u'{}/{}/index.{}'.format(cat_slug, cat2_slug, view_functions.CONTENT_FILE_EXTENSION), cat2_path)
        self.assertEqual(u'The "{cat_title}" category was created\n\n[{{"action": "create", "file_path": "{file_path}", "display_type": "category", "title": "{cat_title}"}}]'.format(cat_title=cat2_title, file_path=cat2_path), add_message)
        self.assertEqual(u'{}/{}/'.format(cat_slug, cat2_slug), redirect_path)
        self.assertEqual(True, do_save)
        # commit the category
        repo_functions.save_working_file(new_clone, cat2_path, add_message, new_clone.commit().hexsha, 'master')

        # verify that the directory and index file exist
        cat2_index_path = join(new_clone.working_dir, cat2_path)
        self.assertTrue(exists(cat2_index_path))
        self.assertTrue(exists(view_functions.strip_index_file(cat2_index_path)))

        # and an article inside that
        art_title = u'သံပုရာဖျော်ရည်'
        art_slug = slugify(art_title)
        dir_path = redirect_path.rstrip('/')
        add_message, art_path, redirect_path, do_save = view_functions.add_article_or_category(new_clone, dir_path, art_title, view_functions.ARTICLE_LAYOUT)
        self.assertEqual(u'{}/{}/{}/index.{}'.format(cat_slug, cat2_slug, art_slug, view_functions.CONTENT_FILE_EXTENSION), art_path)
        self.assertEqual(u'The "{art_title}" article was created\n\n[{{"action": "create", "file_path": "{file_path}", "display_type": "article", "title": "{art_title}"}}]'.format(art_title=art_title, file_path=art_path), add_message)
        self.assertEqual(u'{}/{}/{}/index.{}'.format(cat_slug, cat2_slug, art_slug, view_functions.CONTENT_FILE_EXTENSION), redirect_path)
        self.assertEqual(True, do_save)
        # commit the article
        repo_functions.save_working_file(new_clone, art_path, add_message, new_clone.commit().hexsha, 'master')

        # verify that the directory and index file exist
        art_index_path = join(new_clone.working_dir, art_path)
        self.assertTrue(exists(art_index_path))
        self.assertTrue(exists(view_functions.strip_index_file(art_index_path)))

        # now delete the second category
        browse_path = view_functions.strip_index_file(art_path)
        redirect_path, do_save, commit_message = view_functions.delete_page(repo=new_clone, browse_path=browse_path, target_path=dir_path)
        self.assertEqual(cat_slug.rstrip('/'), redirect_path.rstrip('/'))
        self.assertEqual(True, do_save)
        self.assertEqual(u'The "{cat2_title}" category (containing 1 article) was deleted\n\n[{{"action": "delete", "file_path": "{cat2_path}", "display_type": "category", "title": "{cat2_title}"}}, {{"action": "delete", "file_path": "{art_path}", "display_type": "article", "title": "{art_title}"}}]'.format(cat2_title=cat2_title, cat2_path=cat2_path, art_path=art_path, art_title=art_title), commit_message)

        repo_functions.save_working_file(clone=new_clone, path=dir_path, message=commit_message, base_sha=new_clone.commit().hexsha, default_branch_name='master')

        # verify that the files are gone
        self.assertFalse(exists(cat2_index_path))
        self.assertFalse(exists(view_functions.strip_index_file(cat2_index_path)))
        self.assertFalse(exists(art_index_path))
        self.assertFalse(exists(view_functions.strip_index_file(art_index_path)))

    # in TestRepo
    def test_activity_history_recorded(self):
        ''' The activity history accurately records activity events.
        '''
        # start a new branch
        fake_author_email = u'erica@example.com'
        task_description = u'shake trees until coconuts fall off'
        task_beneficiary = u'castaways'

        source_repo = self.origin
        first_commit = list(source_repo.iter_commits())[-1].hexsha
        dir_name = 'repo-{}-{}'.format(first_commit[:8], slugify(fake_author_email))
        user_dir = realpath(join(self.work_path, quote(dir_name)))

        if isdir(user_dir):
            new_clone = ChimeRepo(user_dir)
            new_clone.git.reset(hard=True)
            new_clone.remotes.origin.fetch()
        else:
            new_clone = source_repo.clone(user_dir, bare=False)

        # tell git to ignore merge conflicts on the task metadata file
        repo_functions.ignore_task_metadata_on_merge(new_clone)

        working_branch = repo_functions.get_start_branch(new_clone, 'master', task_description, task_beneficiary, fake_author_email)
        self.assertTrue(working_branch.name in new_clone.branches)
        self.assertTrue(working_branch.name in self.origin.branches)
        working_branch.checkout()

        # create some category/article structure
        create_details = [
            ('', 'Tree', view_functions.CATEGORY_LAYOUT),
            ('tree', 'Coconut', view_functions.CATEGORY_LAYOUT),
            ('tree/coconut', 'Coconut Milk', view_functions.ARTICLE_LAYOUT),
            ('', 'Rock', view_functions.CATEGORY_LAYOUT),
            ('rock', 'Barnacle', view_functions.CATEGORY_LAYOUT),
            ('', 'Sand', view_functions.CATEGORY_LAYOUT)
        ]
        updated_details = []
        for detail in create_details:
            add_message, file_path, redirect_path, do_save = view_functions.add_article_or_category(new_clone, detail[0], detail[1], detail[2])
            updated_details.append(detail + (file_path,))
            repo_functions.save_working_file(new_clone, file_path, add_message, new_clone.commit().hexsha, 'master')

        # add a comment
        funny_comment = u'I like coconuts ᶘ ᵒᴥᵒᶅ'
        repo_functions.provide_feedback(new_clone, funny_comment)

        # add another comment with newlines
        newline_comment = u'You wound me sir.\n\nI thought we were friends\nBut I guess we are not.'
        repo_functions.provide_feedback(new_clone, newline_comment)

        # delete a category with stuff in it
        commit_message = view_functions.make_delete_display_commit_message(new_clone, 'tree')
        deleted_file_paths, do_save = edit_functions.delete_file(new_clone, 'tree')
        # commit
        repo_functions.save_working_file(new_clone, 'tree', commit_message, new_clone.commit().hexsha, 'master')

        # checkout
        working_branch.checkout()

        # get and check the history
        activity_history = view_functions.make_activity_history(repo=new_clone)
        self.assertEqual(len(activity_history), 10)

        # check the creation of the activity
        check_item = activity_history.pop()
        self.assertEqual(u'The "{}" activity was started'.format(task_description), check_item['commit_subject'])
        self.assertEqual(u'Created task metadata file "{}"\nSet author_email to {}\nSet task_description to {}\nSet task_beneficiary to {}'.format(repo_functions.TASK_METADATA_FILENAME, fake_author_email, task_description, task_beneficiary), check_item['commit_body'])
        self.assertEqual(repo_functions.MESSAGE_TYPE_ACTIVITY_UPDATE, check_item['commit_type'])

        # check the delete
        check_item = activity_history.pop(0)
        self.assertEqual(u'The "{}" category (containing 1 category and 1 article) was deleted'.format(updated_details[0][1]), check_item['commit_subject'])
        self.assertEqual(u'[{{"action": "delete", "file_path": "{cat1_path}", "display_type": "category", "title": "{cat1_title}"}}, {{"action": "delete", "file_path": "{cat2_path}", "display_type": "category", "title": "{cat2_title}"}}, {{"action": "delete", "file_path": "{art1_path}", "display_type": "article", "title": "{art1_title}"}}]'.format(cat1_path=updated_details[0][3], cat1_title=updated_details[0][1], cat2_path=updated_details[1][3], cat2_title=updated_details[1][1], art1_path=updated_details[2][3], art1_title=updated_details[2][1]), check_item['commit_body'])
        self.assertEqual(repo_functions.MESSAGE_TYPE_EDIT, check_item['commit_type'])

        # check the comments
        check_item = activity_history.pop(0)
        self.assertEqual(u'Provided feedback.', check_item['commit_subject'])
        self.assertEqual(newline_comment, check_item['commit_body'])
        self.assertEqual(repo_functions.MESSAGE_TYPE_COMMENT, check_item['commit_type'])

        check_item = activity_history.pop(0)
        self.assertEqual(u'Provided feedback.', check_item['commit_subject'])
        self.assertEqual(funny_comment, check_item['commit_body'])
        self.assertEqual(repo_functions.MESSAGE_TYPE_COMMENT, check_item['commit_type'])

        # check the category & article creations
        for pos, check_item in list(enumerate(activity_history)):
            check_detail = updated_details[len(updated_details) - (pos + 1)]
            self.assertEqual(u'The "{}" {} was created'.format(check_detail[1], check_detail[2]), check_item['commit_subject'])
            self.assertEqual(u'[{{"action": "create", "file_path": "{file_path}", "display_type": "{display_type}", "title": "{title}"}}]'.format(file_path=check_detail[3], display_type=check_detail[2], title=check_detail[1]), check_item['commit_body'])
            self.assertEqual(repo_functions.MESSAGE_TYPE_EDIT, check_item['commit_type'])

    # in TestRepo
    def test_newlines_in_commit_message_body(self):
        ''' Newlines in the commit message body are preserved.
        '''
        # start a new branch
        fake_author_email = u'erica@example.com'
        task_description = u'cling to a rock and scrape bacteria and algae off of it with a radula'
        task_beneficiary = u'mollusks'

        source_repo = self.origin
        first_commit = list(source_repo.iter_commits())[-1].hexsha
        dir_name = 'repo-{}-{}'.format(first_commit[:8], slugify(fake_author_email))
        user_dir = realpath(join(self.work_path, quote(dir_name)))

        if isdir(user_dir):
            new_clone = ChimeRepo(user_dir)
            new_clone.git.reset(hard=True)
            new_clone.remotes.origin.fetch()
        else:
            new_clone = source_repo.clone(user_dir, bare=False)

        # tell git to ignore merge conflicts on the task metadata file
        repo_functions.ignore_task_metadata_on_merge(new_clone)

        working_branch = repo_functions.get_start_branch(new_clone, 'master', task_description, task_beneficiary, fake_author_email)
        self.assertTrue(working_branch.name in new_clone.branches)
        self.assertTrue(working_branch.name in self.origin.branches)
        working_branch.checkout()

        # add some comments with newlines
        striking_comment = u'A striking feature of molluscs is the use of the same organ for multiple functions.\n(و ˃̵ᴗ˂̵)و\n\nFor example, the heart and nephridia ("kidneys") are important parts of the reproductive system, as well as the circulatory and excretory systems\nᶘ ᵒᴥᵒᶅ'
        repo_functions.provide_feedback(new_clone, striking_comment)

        universal_comment = u'The three most universal features defining modern molluscs are:\n\n1. A mantle with a significant cavity used for breathing and excretion,\n\n2. the presence of a radula, and\n\n3. the structure of the nervous system.'
        repo_functions.provide_feedback(new_clone, universal_comment)

        # checkout
        working_branch.checkout()

        _, universal_body = repo_functions.get_commit_message_subject_and_body(working_branch.commit)
        _, striking_body = repo_functions.get_commit_message_subject_and_body(working_branch.commit.parents[0])

        self.assertEqual(universal_comment, universal_body)
        self.assertEqual(striking_comment, striking_body)

    # in TestRepo
    def test_delete_full_folders(self):
        ''' Make sure that full folders can be deleted, and that what's reported as deleted matches what's expected.
        '''
        # build some nested categories
        view_functions.add_article_or_category(self.clone1, '', 'quick', view_functions.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, 'quick', 'brown', view_functions.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, 'quick/brown', 'fox', view_functions.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, 'quick', 'red', view_functions.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, 'quick', 'yellow', view_functions.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, 'quick/yellow', 'banana', view_functions.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, 'quick', 'orange', view_functions.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, 'quick/brown', 'potato', view_functions.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, 'quick/yellow', 'lemon', view_functions.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, 'quick/red', 'tomato', view_functions.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, 'quick/red', 'balloon', view_functions.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, 'quick/orange', 'peanut', view_functions.CATEGORY_LAYOUT)
        # add in some articles
        view_functions.add_article_or_category(self.clone1, 'quick/brown/fox', 'fur', view_functions.ARTICLE_LAYOUT)
        view_functions.add_article_or_category(self.clone1, 'quick/brown/fox', 'ears', view_functions.ARTICLE_LAYOUT)
        view_functions.add_article_or_category(self.clone1, 'quick/yellow/lemon', 'rind', view_functions.ARTICLE_LAYOUT)
        view_functions.add_article_or_category(self.clone1, 'quick/yellow/lemon', 'pulp', view_functions.ARTICLE_LAYOUT)
        view_functions.add_article_or_category(self.clone1, 'quick/orange/peanut', 'shell', view_functions.ARTICLE_LAYOUT)
        view_functions.add_article_or_category(self.clone1, 'quick/red/balloon', 'string', view_functions.ARTICLE_LAYOUT)

        # add and commit
        self.clone1.index.add(['*'])
        self.clone1.index.commit(u'cats and arts committed for testing purposes')

        # verify that everything's there as expected
        file_paths = edit_functions.list_contained_files(self.clone1, join(self.clone1.working_dir, 'quick'))
        file_paths.sort()
        self.assertEqual(len(file_paths), 18)
        self.assertTrue(exists(join(self.clone1.working_dir, 'quick')))

        # delete everything, and get a file list back from the git rm command
        deleted_file_paths, do_save = edit_functions.delete_file(self.clone1, 'quick')
        deleted_file_paths.sort()
        self.assertTrue(do_save)
        self.assertEqual(len(deleted_file_paths), 18)
        self.assertFalse(exists(join(self.clone1.working_dir, 'quick')))

        # verify that everything in file_paths is in deleted_file_paths
        for check_index in range(len(file_paths)):
            self.assertEqual(file_paths[check_index], deleted_file_paths[check_index])

    # in TestRepo
    def test_task_metadata_creation(self):
        ''' The task metadata file is created when a branch is started, and contains the expected information.
        '''
        fake_author_email = u'erica@example.com'
        task_description, task_beneficiary = str(uuid4()), str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
        branch1_name = branch1.name
        branch1.checkout()

        # verify that the most recent commit on the new branch is for the task metadata file
        # by checking for the name of the file in the commit message
        self.assertTrue(repo_functions.TASK_METADATA_FILENAME in branch1.commit.message)

        # validate the existence of the task metadata file
        task_metadata = repo_functions.get_task_metadata_for_branch(self.clone1, branch1_name)
        self.assertEqual(type(task_metadata), dict)
        self.assertTrue(len(task_metadata) > 0)

        # validate the contents of the task metadata file
        self.assertEqual(task_metadata['author_email'], fake_author_email)
        self.assertEqual(task_metadata['task_description'], task_description)
        self.assertEqual(task_metadata['task_beneficiary'], task_beneficiary)

    # in TestRepo
    def test_task_metadata_creation_with_unicode(self):
        ''' The task metadata file is created when a branch is started, and contains the expected information.
        '''
        fake_author_email = u'¯\_(ツ)_/¯@快速狐狸.com'
        task_description = u'(╯°□°）╯︵ ┻━┻'
        task_beneficiary = u'૮(꒦ິ ˙̫̮ ꒦ິ)ა'
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
        branch1_name = branch1.name
        branch1.checkout()

        # verify that the most recent commit on the new branch is for the task metadata file
        # by checking for the name of the file in the commit message
        self.assertTrue(repo_functions.TASK_METADATA_FILENAME in branch1.commit.message)

        # validate the existence of the task metadata file
        task_metadata = repo_functions.get_task_metadata_for_branch(self.clone1, branch1_name)
        self.assertEqual(type(task_metadata), dict)
        self.assertTrue(len(task_metadata) > 0)

        # validate the contents of the task metadata file
        self.assertEqual(task_metadata['author_email'], fake_author_email)
        self.assertEqual(task_metadata['task_description'], task_description)
        self.assertEqual(task_metadata['task_beneficiary'], task_beneficiary)

    # in TestRepo
    def test_task_metadata_update(self):
        ''' The task metadata file can be updated
        '''
        fake_author_email = u'erica@example.com'
        task_description, task_beneficiary = str(uuid4()), str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
        branch1_name = branch1.name
        branch1.checkout()

        # verify that the most recent commit on the new branch is for the task metadata file
        # by checking for the name of the file in the commit message
        self.assertTrue(repo_functions.TASK_METADATA_FILENAME in branch1.commit.message)

        # validate the existence of the task metadata file
        task_metadata = repo_functions.get_task_metadata_for_branch(self.clone1, branch1_name)
        self.assertEqual(type(task_metadata), dict)
        self.assertTrue(len(task_metadata) > 0)

        # validate the contents of the task metadata file
        self.assertEqual(task_metadata['author_email'], fake_author_email)
        self.assertEqual(task_metadata['task_description'], task_description)
        self.assertEqual(task_metadata['task_beneficiary'], task_beneficiary)

        # write a new task name and some other arbitrary data
        metadata_update = {'task_description': u'Changed my mind', 'lead_singer': u'Johnny Rotten'}
        repo_functions.save_task_metadata_for_branch(self.clone1, 'master', metadata_update)

        # validate the contents of the task metadata file
        new_task_metadata = repo_functions.get_task_metadata_for_branch(self.clone1, branch1_name)
        self.assertEqual(type(new_task_metadata), dict)
        self.assertTrue(len(new_task_metadata) > 0)
        self.assertEqual(new_task_metadata['task_description'], metadata_update['task_description'])
        self.assertEqual(new_task_metadata['lead_singer'], metadata_update['lead_singer'])

    # in TestRepo
    def test_task_metadata_deletion(self):
        ''' The task metadata file is deleted when a branch is completed, and isn't merged.
        '''
        fake_author_email = u'erica@example.com'
        task_description, task_beneficiary = str(uuid4()), str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
        branch1_name = branch1.name
        branch1.checkout()

        # Add a file and complete the branch
        edit_functions.create_new_page(self.clone1, '', 'happy.md', dict(title='Hello'), 'Hello hello.')
        args1 = self.clone1, 'happy.md', 'added cool file', branch1.commit.hexsha, 'master'
        repo_functions.save_working_file(*args1)
        merge_commit = repo_functions.complete_branch(self.clone1, 'master', branch1_name)

        # The commit message is expected
        self.assertTrue(repo_functions.ACTIVITY_PUBLISHED_MESSAGE in merge_commit.message)
        # The branch is gone
        self.assertFalse(branch1_name in self.origin.branches)
        self.assertFalse(branch1_name in self.clone1.branches)
        # The file we created exists
        self.assertTrue(repo_functions.verify_file_exists_in_branch(self.clone1, 'happy.md', 'master'))
        self.assertTrue(repo_functions.verify_file_exists_in_branch(self.origin, 'happy.md', 'master'))
        # the task metadata file doesn't exist
        self.assertFalse(repo_functions.verify_file_exists_in_branch(self.clone1, repo_functions.TASK_METADATA_FILENAME, 'master'))
        self.assertFalse(repo_functions.verify_file_exists_in_branch(self.origin, repo_functions.TASK_METADATA_FILENAME, 'master'))

    # in TestRepo
    def test_merge_tagged_with_branch_metadata(self):
        ''' The merge commit is tagged with branch metadata on publish.
        '''
        # start an activity on clone1
        erica_email = u'erica@example.com'
        task_description = u'Attract Insects With Anthocyanin Pigments To The Cavity Formed By A Cupped Leaf'
        task_beneficiary = u'Nepenthes'
        clone1_branch = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, erica_email)
        branch_name = clone1_branch.name
        clone1_branch.checkout()
        clone1_branch_task_metadata = repo_functions.get_task_metadata_for_branch(self.clone1, branch_name)

        # check out the branch on clone2 and verify that it's the same
        clone2_branch = repo_functions.get_existing_branch(self.clone2, 'master', branch_name)
        clone2_branch.checkout()
        clone2_branch_task_metadata = repo_functions.get_task_metadata_for_branch(self.clone2, branch_name)
        self.assertEqual(clone2_branch.commit.hexsha, clone1_branch.commit.hexsha)
        self.assertEqual(clone1_branch_task_metadata, clone2_branch_task_metadata)

        # On clone1, add a file and complete the branch
        edit_functions.create_new_page(self.clone1, '', 'happy.md', dict(title='Hello'), 'Hello hello.')
        args1 = self.clone1, 'happy.md', 'added cool file', clone1_branch.commit.hexsha, 'master'
        repo_functions.save_working_file(*args1)
        merge_commit = repo_functions.complete_branch(self.clone1, 'master', branch_name)

        # update clone2
        self.clone2.git.fetch('origin')

        # the branch is no longer in clone1 or origin
        self.assertFalse(branch_name in self.clone1.branches)
        self.assertFalse(branch_name in self.origin.branches)
        # but it's still there in clone2
        self.assertTrue(branch_name in self.clone2.branches)

        # collect the tag ref, object, name
        clone1_tag_ref = self.clone1.tags[0]
        clone1_tag = clone1_tag_ref.tag
        clone1_tag_name = clone1_tag.tag
        clone2_tag_ref = self.clone2.tags[0]
        clone2_tag = clone2_tag_ref.tag
        clone2_tag_name = clone2_tag.tag
        origin_tag_ref = self.origin.tags[0]
        origin_tag = origin_tag_ref.tag
        origin_tag_name = origin_tag.tag
        # the tag exists
        self.assertIsNotNone(clone1_tag_ref)
        self.assertIsNotNone(clone2_tag_ref)
        self.assertIsNotNone(origin_tag_ref)
        # it's attached to the merge commit
        self.assertEqual(clone1_tag_ref.commit, merge_commit)
        self.assertEqual(clone2_tag_ref.commit, merge_commit)
        self.assertEqual(origin_tag_ref.commit, merge_commit)
        # it has the same name as the branch
        self.assertEqual(clone1_tag_name, branch_name)
        self.assertEqual(clone2_tag_name, branch_name)
        self.assertEqual(origin_tag_name, branch_name)

        # the tag message is the jsonified task metadata
        clone1_tag_metadata = json.loads(clone1_tag.message)
        clone2_tag_metadata = json.loads(clone2_tag.message)
        origin_tag_metadata = json.loads(origin_tag.message)
        self.assertEqual(clone1_tag_metadata, clone1_branch_task_metadata)
        self.assertEqual(clone2_tag_metadata, clone1_branch_task_metadata)
        self.assertEqual(origin_tag_metadata, clone1_branch_task_metadata)

        # the file we published in clone1 is in clone2's local branch and master
        self.clone2.git.pull('origin', branch_name)
        self.assertTrue(repo_functions.verify_file_exists_in_branch(self.clone2, 'happy.md', branch_name))
        self.clone2.branches['master'].checkout()
        self.clone2.git.pull('origin', 'master')
        self.assertTrue(repo_functions.verify_file_exists_in_branch(self.clone2, 'happy.md', 'master'))

    # in TestRepo
    def test_task_metadata_merge_conflict(self):
        ''' Task metadata file merge conflict is handled correctly
        '''
        fake_author_email1 = u'erica@example.com'
        fake_author_email2 = u'nobody@example.com'
        task_description1, task_description2 = str(uuid4()), str(uuid4())
        task_beneficiary1, task_beneficiary2 = str(uuid4()), str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description1, task_beneficiary1, fake_author_email1)
        branch2 = repo_functions.get_start_branch(self.clone2, 'master', task_description2, task_beneficiary2, fake_author_email2)
        branch1_name = branch1.name

        # Check out the branches
        branch1.checkout()
        branch2.checkout()

        # Save a task metadata file
        fake_metadata = {'task_description': u'Changed my mind', 'lead_singer': u'Johnny Rotten'}
        commit1 = repo_functions.save_task_metadata_for_branch(self.clone1, 'master', fake_metadata)
        self.assertEqual(self.origin.branches[branch1_name].commit, commit1)
        self.assertEqual(commit1, branch1.commit)

        # merge the branch to master manually so the task metadata file will be included
        message = u'Manual merge including task metadata'
        self.clone1.git.checkout('master')
        self.clone1.git.pull('origin', 'master')

        try:
            self.clone1.git.merge(branch1_name, '--no-ff', m=message)

        except GitCommandError:
            # raise the two commits in conflict.
            remote_commit = self.clone1.refs['origin/master'].commit
            self.clone1.git.reset('master', hard=True)
            self.clone1.git.checkout(branch1_name)
            raise repo_functions.MergeConflict(remote_commit, self.clone1.commit())

        self.clone1.git.push('origin', 'master')

        # Delete the working branch.
        self.clone1.remotes.origin.push(':' + branch1_name)
        self.clone1.delete_head([branch1_name])

        # verify that the branch has been deleted
        self.assertFalse(branch1_name in self.origin.branches)

        # Although there are conflicting changes in the two task metadata files,
        # there should be no conflict raised!
        try:
            args = self.clone2, repo_functions.TASK_METADATA_FILENAME, '...', branch2.commit.hexsha, 'master'
            repo_functions.save_working_file(*args)
        except repo_functions.MergeConflict:
            self.assertTrue(False)

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

class TestAppConfig (TestCase):

    # in TestAppConfig
    def test_missing_values(self):
        self.assertRaises(KeyError, lambda: create_app({}))

    # in TestAppConfig
    def test_present_values(self):
        create_app_environ = {}
        create_app_environ['RUNNING_STATE_DIR'] = 'Yo'
        create_app_environ['GA_CLIENT_ID'] = 'Yo'
        create_app_environ['GA_CLIENT_SECRET'] = 'Yo'
        create_app_environ['LIVE_SITE_URL'] = 'Hey'
        create_app_environ['BROWSERID_URL'] = 'Hey'
        create_app(create_app_environ)

    def test_error_template_args(self):
        ''' Default error template args are generated as expected
        '''
        create_app_environ = {}
        create_app_environ['RUNNING_STATE_DIR'] = 'Yo'
        create_app_environ['GA_CLIENT_ID'] = 'Yo'
        create_app_environ['GA_CLIENT_SECRET'] = 'Yo'
        create_app_environ['BROWSERID_URL'] = 'Hey'
        create_app_environ['LIVE_SITE_URL'] = 'Hey'
        fake_support_email = u'support@example.com'
        fake_support_phone_number = u'(123) 456-7890'
        create_app_environ['SUPPORT_EMAIL_ADDRESS'] = fake_support_email
        create_app_environ['SUPPORT_PHONE_NUMBER'] = fake_support_phone_number
        app = create_app(create_app_environ)
        template_args = errors.common_error_template_args(app.config)
        self.assertEqual(len(template_args), 3)
        self.assertTrue('activities_path' in template_args)
        self.assertTrue('support_email' in template_args)
        self.assertTrue('support_phone_number' in template_args)
        self.assertEqual(template_args['support_email'], fake_support_email)
        self.assertEqual(template_args['support_phone_number'], fake_support_phone_number)

class TestProcess (TestCase):

    def setUp(self):
        self.old_tempdir, tempfile.tempdir = tempfile.tempdir, mkdtemp(prefix='chime-TestProcess-')

        self.work_path = mkdtemp(prefix='chime-repo-clones-')

        repo_path = dirname(abspath(__file__)) + '/../test-app.git'
        upstream_repo_dir = mkdtemp(prefix='repo-upstream-', dir=self.work_path)
        upstream_repo_path = join(upstream_repo_dir, 'test-app.git')
        copytree(repo_path, upstream_repo_path)
        self.upstream = ChimeRepo(upstream_repo_path)
        repo_functions.ignore_task_metadata_on_merge(self.upstream)
        self.origin = self.upstream.clone(mkdtemp(prefix='repo-origin-', dir=self.work_path), bare=True)
        repo_functions.ignore_task_metadata_on_merge(self.origin)

        # environ['GIT_AUTHOR_NAME'] = ' '
        # environ['GIT_COMMITTER_NAME'] = ' '
        # environ['GIT_AUTHOR_EMAIL'] = u'erica@example.com'
        # environ['GIT_COMMITTER_EMAIL'] = u'erica@example.com'

        create_app_environ = {}

        create_app_environ['GA_CLIENT_ID'] = 'client_id'
        create_app_environ['GA_CLIENT_SECRET'] = 'meow_secret'

        self.ga_config_dir = mkdtemp(prefix='chime-config-', dir=self.work_path)
        create_app_environ['RUNNING_STATE_DIR'] = self.ga_config_dir
        create_app_environ['WORK_PATH'] = self.work_path
        create_app_environ['REPO_PATH'] = self.origin.working_dir
        create_app_environ['AUTH_DATA_HREF'] = 'http://example.com/auth.csv'
        create_app_environ['BROWSERID_URL'] = 'http://localhost'
        create_app_environ['LIVE_SITE_URL'] = 'http://example.org/'
        create_app_environ['SUPPORT_EMAIL_ADDRESS'] = u'support@example.com'
        create_app_environ['SUPPORT_PHONE_NUMBER'] = u'(123) 456-7890'

        self.app = create_app(create_app_environ)

        # write a tmp config file
        config_values = {
            "access_token": "meowser_token",
            "refresh_token": "refresh_meows",
            "profile_id": "12345678",
            "project_domain": ""
        }
        with self.app.app_context():
            google_api_functions.write_ga_config(config_values, self.app.config['RUNNING_STATE_DIR'])

        random.choice = MagicMock(return_value="P")

    def tearDown(self):
        rmtree(tempfile.tempdir)
        tempfile.tempdir = self.old_tempdir

    def auth_csv_example_allowed(self, url, request):
        if url.geturl() == 'http://example.com/auth.csv':
            return response(200, '''Email domain,Organization\nexample.com,Example Org''')

        raise Exception('Asked for unknown URL ' + url.geturl())

    def mock_persona_verify_erica(self, url, request):
        if url.geturl() == 'https://verifier.login.persona.org/verify':
            return response(200, '''{"status": "okay", "email": "erica@example.com"}''')

        else:
            return self.auth_csv_example_allowed(url, request)

    def mock_persona_verify_frances(self, url, request):
        if url.geturl() == 'https://verifier.login.persona.org/verify':
            return response(200, '''{"status": "okay", "email": "frances@example.com"}''')

        else:
            return self.auth_csv_example_allowed(url, request)

    # in TestProcess
    def test_editing_process_with_two_users(self):
        ''' Check edit process with a user looking at feedback from another user.
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in('erica@example.com')
            
            with HTTMock(self.mock_persona_verify_frances):
                frances = ChimeTestClient(self.app.test_client(), self)
                frances.sign_in('frances@example.com')
            
            # Start a new task, "Diving for Dollars".
            erica.start_task('Diving', 'Dollars')
            branch_name = erica.get_branch_name()
            
            # Look for an "other" link that we know about - is it a category?
            erica.follow_link('/tree/{}/edit/other'.format(branch_name))

            # Create a new category "Ninjas", subcategory "Flipping Out", and article "So Awesome".
            erica.add_category('Ninjas')
            erica.add_subcategory('Flipping Out')
            erica.add_article('So Awesome')
            
            # Edit the new article.
            erica.edit_article('So, So Awesome', 'It was the best of times.')
            
            # Ask for feedback
            erica.follow_link('/tree/{}'.format(branch_name))
            erica.request_feedback('Is this okay?')
            
            #
            # Switch users and comment on the activity.
            #
            frances.open_link(erica.path)
            frances.leave_feedback('It is super-great.')

            #
            # Switch back and look for that bit of feedback.
            #
            erica.reload()
            words = erica.soup.find(text='It is super-great.')
            comment = words.find_parent('div').find_parent('div')
            author = comment.find(text='frances@example.com')
            self.assertTrue(author is not None)

    # in TestProcess
    def test_editing_process_with_conflicting_publish(self):
        ''' Check edit process with a user attempting to change an activity that's been published.
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in('erica@example.com')
            
            with HTTMock(self.mock_persona_verify_frances):
                frances = ChimeTestClient(self.app.test_client(), self)
                frances.sign_in('frances@example.com')

            # Start a new task, "Diving for Dollars".
            erica.start_task(description='Diving', beneficiary='Dollars')
            branch_name = erica.get_branch_name()

            # Look for an "other" link that we know about - is it a category?
            erica.follow_link(href='/tree/{}/edit/other'.format(branch_name))

            # Create a new category "Ninjas", subcategory "Flipping Out", and article "So Awesome".
            erica.add_category(category_name='Ninjas')
            erica.add_subcategory(subcategory_name='Flipping Out')
            erica.add_article(article_name='So Awesome')

            # Edit the new article.
            erica.edit_article(title_str='So, So Awesome', body_str='It was the best of times.')
            article_path = erica.path

            # Ask for feedback
            erica.follow_link(href='/tree/{}'.format(branch_name))
            erica.request_feedback(feedback_str='Is this okay?')

            #
            # Switch users and publish the article.
            #
            frances.open_link(url=erica.path)
            frances.leave_feedback(feedback_str='It is super-great.')
            frances.approve_activity()
            frances.publish_activity()
            
            #
            # Check with upstream repository.
            #
            origin_commit = self.origin.refs.master.commit.hexsha
            upstream_commit = self.upstream.refs.master.commit.hexsha
            self.assertNotEqual(origin_commit, upstream_commit, 'Origin and upstream should not match before explicit synch')

            running_state_dir = self.app.config['RUNNING_STATE_DIR']
            repo_functions.push_upstream_if_needed(self.origin, running_state_dir)
            upstream_commit = self.upstream.refs.master.commit.hexsha
            self.assertEqual(origin_commit, upstream_commit, 'Origin and upstream should match after explicit synch')

            #
            # Switch back and try to make another edit, but watch it fail.
            #
            erica.open_link(article_path)
            erica.edit_outdated_article(title_str='Just Awful', body_str='It was the worst of times.')

    # in TestProcess
    def test_task_not_marked_published_after_merge_conflict(self):
        ''' When publishing an activity results in a merge conflict, it shouldn't be marked published.
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in('erica@example.com')

            with HTTMock(self.mock_persona_verify_frances):
                frances = ChimeTestClient(self.app.test_client(), self)
                frances.sign_in('frances@example.com')

            # Start a new task
            erica.start_task(description='Eating Carrion', beneficiary='Vultures')
            erica_branch_name = erica.get_branch_name()

            # Look for an "other" link that we know about - is it a category?
            erica.follow_link(href='/tree/{}/edit/other'.format(erica_branch_name))

            # Create a new category, subcategory, and article
            erica.add_category(category_name=u'Forage')
            erica.add_subcategory(subcategory_name='Dead Animals')
            erica.add_article(article_name='Dingos')

            # Edit the new article.
            erica.edit_article(title_str='Dingos', body_str='Canis Lupus Dingo')

            # Ask for feedback
            erica.follow_link(href='/tree/{}'.format(erica_branch_name))
            erica.request_feedback(feedback_str='Is this okay?')

            #
            # Switch users
            #
            # Start a new task
            frances.start_task(description='Flying in Circles', beneficiary='Vultures')
            frances_branch_name = frances.get_branch_name()

            # Look for an "other" link that we know about - is it a category?
            frances.follow_link(href='/tree/{}/edit/other'.format(frances_branch_name))

            # Create a duplicate new category, subcategory, and article
            frances.add_category(category_name=u'Forage')
            frances.add_subcategory(subcategory_name='Dead Animals')
            frances.add_article(article_name='Dingos')

            # Edit the new article.
            frances.edit_article(title_str='Dingos', body_str='Apex Predator')

            # Ask for feedback
            frances.follow_link(href='/tree/{}'.format(frances_branch_name))
            frances.request_feedback(feedback_str='Is this okay?')
            frances_overview_path = frances.path

            # frances approves and publishes erica's changes
            frances.open_link(url=erica.path)
            frances.leave_feedback(feedback_str='It is perfect.')
            frances.approve_activity()
            frances.publish_activity()

            # erica approves and publishes frances's changes
            erica.open_link(url=frances_overview_path)
            erica.leave_feedback(feedback_str='It is not bad.')
            erica.approve_activity()
            erica.publish_activity(expected_code=500)

            # we got a 500 error page about a merge conflict
            pattern_template_comment_stripped = sub(ur'<!--|-->', u'', PATTERN_TEMPLATE_COMMENT)
            comments = erica.soup.find_all(text=lambda text: isinstance(text, Comment))
            self.assertTrue(pattern_template_comment_stripped.format(u'error-500') in comments)
            self.assertIsNotNone(erica.soup.find(lambda tag: tag.name == 'a' and u'MergeConflict' in tag['href']))

            # re-load the overview page
            erica.open_link(url=frances_overview_path)
            # verify that the publish button is still available
            self.assertIsNotNone(erica.soup.find(lambda tag: tag.name == 'input' and tag['value'] == u'Publish'))

class TestApp (TestCase):

    def setUp(self):
        self.old_tempdir, tempfile.tempdir = tempfile.tempdir, mkdtemp(prefix='chime-TestApp-')

        self.work_path = mkdtemp(prefix='chime-repo-clones-')
        self.publish_path = mkdtemp(prefix='chime-publish-path-')

        repo_path = dirname(abspath(__file__)) + '/../test-app.git'
        temp_repo_dir = mkdtemp(prefix='chime-root')
        temp_repo_path = temp_repo_dir + '/test-app.git'
        copytree(repo_path, temp_repo_path)
        self.origin = ChimeRepo(temp_repo_path)
        repo_functions.ignore_task_metadata_on_merge(self.origin)
        self.clone1 = self.origin.clone(mkdtemp(prefix='chime-'))
        repo_functions.ignore_task_metadata_on_merge(self.clone1)

        fake_author_email = u'erica@example.com'
        self.session = dict(email=fake_author_email)

        environ['GIT_AUTHOR_NAME'] = ' '
        environ['GIT_COMMITTER_NAME'] = ' '
        environ['GIT_AUTHOR_EMAIL'] = self.session['email']
        environ['GIT_COMMITTER_EMAIL'] = self.session['email']

        create_app_environ = {}

        create_app_environ['SINGLE_USER'] = 'Yes'
        create_app_environ['GA_CLIENT_ID'] = 'client_id'
        create_app_environ['GA_CLIENT_SECRET'] = 'meow_secret'

        self.ga_config_dir = mkdtemp(prefix='chime-config-')
        create_app_environ['RUNNING_STATE_DIR'] = self.ga_config_dir
        create_app_environ['WORK_PATH'] = self.work_path
        create_app_environ['REPO_PATH'] = temp_repo_path
        create_app_environ['AUTH_DATA_HREF'] = 'http://example.com/auth.csv'
        create_app_environ['BROWSERID_URL'] = 'http://localhost'
        create_app_environ['LIVE_SITE_URL'] = 'http://example.org/'
        create_app_environ['PUBLISH_PATH'] = self.publish_path

        create_app_environ['SUPPORT_EMAIL_ADDRESS'] = u'support@example.com'
        create_app_environ['SUPPORT_PHONE_NUMBER'] = u'(123) 456-7890'

        self.app = create_app(create_app_environ)

        # write a tmp config file
        config_values = {
            "access_token": "meowser_token",
            "refresh_token": "refresh_meows",
            "profile_id": "12345678",
            "project_domain": ""
        }
        with self.app.app_context():
            google_api_functions.write_ga_config(config_values, self.app.config['RUNNING_STATE_DIR'])

        random.choice = MagicMock(return_value="P")

        self.app.app.debug = True
        self.test_client = self.app.test_client()

    def tearDown(self):
        rmtree(tempfile.tempdir)
        tempfile.tempdir = self.old_tempdir

    def auth_csv_example_disallowed(self, url, request):
        if url.geturl() == 'http://example.com/auth.csv':
            return response(200, '''Email domain,Organization\n''')

        raise Exception('Asked for unknown URL ' + url.geturl())

    def auth_csv_example_allowed(self, url, request):
        if url.geturl() == 'http://example.com/auth.csv':
            return response(200, '''Email domain,Organization\nexample.com,Example Org\n*,Anyone''')

        raise Exception('Asked for unknown URL ' + url.geturl())

    def mock_persona_verify_erica(self, url, request):
        if url.geturl() == 'https://verifier.login.persona.org/verify':
            return response(200, '''{"status": "okay", "email": "erica@example.com"}''', headers=dict(Link='<https://api.github.com/user/337792/repos?page=1>; rel="prev", <https://api.github.com/user/337792/repos?page=1>; rel="first"'))

        else:
            return self.auth_csv_example_allowed(url, request)

    def mock_persona_verify_frances(self, url, request):
        if url.geturl() == 'https://verifier.login.persona.org/verify':
            return response(200, '''{"status": "okay", "email": "frances@example.com"}''', headers=dict(Link='<https://api.github.com/user/337792/repos?page=1>; rel="prev", <https://api.github.com/user/337792/repos?page=1>; rel="first"'))

        else:
            return self.auth_csv_example_allowed(url, request)

    def mock_persona_verify_william(self, url, request):
        if url.geturl() == 'https://verifier.login.persona.org/verify':
            return response(200, '''{"status": "okay", "email": "william@example.org"}''', headers=dict(Link='<https://api.github.com/user/337792/repos?page=1>; rel="prev", <https://api.github.com/user/337792/repos?page=1>; rel="first"'))

        else:
            return self.auth_csv_example_allowed(url, request)

    def mock_google_authorization(self, url, request):
        if 'https://accounts.google.com/o/oauth2/auth' in url.geturl():
            return response(200, '''{"access_token": "meowser_token", "token_type": "meowser_type", "refresh_token": "refresh_meows", "expires_in": 3920}''')

        else:
            return self.auth_csv_example_allowed(url, request)

    def mock_successful_google_callback(self, url, request):
        if google_api_functions.GOOGLE_ANALYTICS_TOKENS_URL in url.geturl():
            return response(200, '''{"access_token": "meowser_token", "token_type": "meowser_type", "refresh_token": "refresh_meows", "expires_in": 3920}''')

        elif google_api_functions.GOOGLE_PLUS_WHOAMI_URL in url.geturl():
            return response(200, '''{"displayName": "Jane Doe", "emails": [{"type": "account", "value": "erica@example.com"}]}''')

        elif google_api_functions.GOOGLE_ANALYTICS_PROPERTIES_URL in url.geturl():
            return response(200, '''{"items": [{"defaultProfileId": "12345678", "name": "Property One", "websiteUrl": "http://propertyone.example.com"}, {"defaultProfileId": "87654321", "name": "Property Two", "websiteUrl": "http://propertytwo.example.com"}]}''')

        else:
            return self.auth_csv_example_allowed(url, request)

    def mock_failed_google_callback(self, url, request):
        if google_api_functions.GOOGLE_ANALYTICS_TOKENS_URL in url.geturl():
            return response(500, '''{}''')
        elif google_api_functions.GOOGLE_PLUS_WHOAMI_URL in url.geturl():
            return response(200, '''{"displayName": "Jane Doe", "emails": [{"type": "account", "value": "erica@example.com"}]}''')
        elif google_api_functions.GOOGLE_ANALYTICS_PROPERTIES_URL in url.geturl():
            return response(200, '''{"items": [{"defaultProfileId": "12345678", "name": "Property One", "websiteUrl": "http://propertyone.example.com"}, {"defaultProfileId": "87654321", "name": "Property Two", "websiteUrl": "http://propertytwo.example.com"}]}''')
        else:
            return self.auth_csv_example_allowed(url, request)

    def mock_google_invalid_credentials_response(self, url, request):
        if 'https://www.googleapis.com/analytics/' in url.geturl() or google_api_functions.GOOGLE_ANALYTICS_PROPERTIES_URL in url.geturl():
            return response(401, '''{"error": {"code": 401, "message": "Invalid Credentials", "errors": [{"locationType": "header", "domain": "global", "message": "Invalid Credentials", "reason": "authError", "location": "Authorization"}]}}''')
        elif google_api_functions.GOOGLE_PLUS_WHOAMI_URL in url.geturl():
            return response(403, '''{"error": {"code": 403, "message": "Access Not Configured. The API (Google+ API) is not enabled for your project. Please use the Google Developers Console to update your configuration.", "errors": [{"domain": "usageLimits", "message": "Access Not Configured. The API (Google+ API) is not enabled for your project. Please use the Google Developers Console to update your configuration.", "reason": "accessNotConfigured", "extendedHelp": "https://console.developers.google.com"}]}}''')
        else:
            return self.auth_csv_example_allowed(url, request)

    def mock_google_no_properties_response(self, url, request):
        if google_api_functions.GOOGLE_ANALYTICS_PROPERTIES_URL in url.geturl():
            return response(200, '''{"kind": "analytics#webproperties", "username": "erica@example.com", "totalResults": 0, "startIndex": 1, "itemsPerPage": 1000, "items": []}''')
        elif google_api_functions.GOOGLE_PLUS_WHOAMI_URL in url.geturl():
            return response(200, '''{"displayName": "Jane Doe", "emails": [{"type": "account", "value": "erica@example.com"}]}''')
        else:
            return self.auth_csv_example_allowed(url, request)

    def mock_google_analytics(self, url, request):
        start_date = (date.today() - timedelta(days=7)).isoformat()
        end_date = date.today().isoformat()
        url_string = url.geturl()

        if 'ids=ga%3A12345678' in url_string and 'end-date=' + end_date in url_string and 'start-date=' + start_date in url_string and 'filters=ga%3ApagePath%3D~%28hello.html%7Chello%29' in url_string:
            return response(200, '''{"ga:previousPagePath": "/about/", "ga:pagePath": "/lib/", "ga:pageViews": "12", "ga:avgTimeOnPage": "56.17", "ga:exiteRate": "43.75", "totalsForAllResults": {"ga:pageViews": "24", "ga:avgTimeOnPage": "67.36363636363636"}}''')

        else:
            return self.auth_csv_example_allowed(url, request)

    def mock_internal_server_error(self, url, request):
        from flask import abort
        abort(500)

    def mock_exception(self, url, request):
        raise Exception(u'This is a generic exception.')

    # in TestApp
    def test_bad_login(self):
        ''' Check basic log in / log out flow without talking to Persona.
        '''
        response = self.test_client.get('/')
        self.assertFalse('erica@example.com' in response.data)

        with HTTMock(self.mock_persona_verify_erica):
            response = self.test_client.post('/sign-in', data={'email': 'erica@example.com'})
            self.assertEqual(response.status_code, 200)

        with HTTMock(self.auth_csv_example_disallowed):
            response = self.test_client.get('/')
            self.assertFalse('Create' in response.data)

    # in TestApp
    def test_login(self):
        ''' Check basic log in / log out flow without talking to Persona.
        '''
        response = self.test_client.get('/')
        self.assertFalse('Start' in response.data)

        with HTTMock(self.mock_persona_verify_erica):
            response = self.test_client.post('/sign-in', data={'email': 'erica@example.com'})
            self.assertEqual(response.status_code, 200)

        with HTTMock(self.auth_csv_example_allowed):
            response = self.test_client.get('/')
            self.assertTrue('Start' in response.data)
            self.assertTrue('http://example.org' in response.data, 'Should see LIVE_SITE_URL in response')

            response = self.test_client.post('/sign-out')
            self.assertEqual(response.status_code, 200)

            response = self.test_client.get('/')
            self.assertFalse('Start' in response.data)

    # in TestApp
    def test_login_splat(self):
        ''' Check basic log in / log out flow without talking to Persona.
        '''
        response = self.test_client.get('/')
        self.assertFalse('Start' in response.data)

        with HTTMock(self.mock_persona_verify_william):
            response = self.test_client.post('/sign-in', data={'email': 'william@example.org'})
            self.assertEqual(response.status_code, 200)

        with HTTMock(self.auth_csv_example_allowed):
            response = self.test_client.get('/')
            self.assertTrue('Start' in response.data)

    # in TestApp
    def test_default_auth_href_warning(self):
        ''' Check basic log in / log out flow without talking to Persona.
        '''
        with patch('chime.view_functions.AUTH_DATA_HREF_DEFAULT', new='http://example.com/auth.csv'):
            response = self.test_client.get('/not-allowed')
            expected = 'Your Chime <code>AUTH_DATA_HREF</code> is set to default value.'
            self.assertTrue(expected in response.data, 'Should see a warning')

    # in TestApp
    @patch('chime.view_functions.AUTH_CHECK_LIFESPAN', new=1.0)
    def test_login_timeout(self):
        ''' Check basic log in / log out flow with auth check lifespan.
        '''
        response = self.test_client.get('/')
        self.assertFalse('Start' in response.data)

        with HTTMock(self.mock_persona_verify_erica):
            response = self.test_client.post('/sign-in', data={'email': 'erica@example.com'})
            self.assertEqual(response.status_code, 200)

        with HTTMock(self.auth_csv_example_allowed):
            response = self.test_client.get('/')
            self.assertTrue('Start' in response.data)

        with patch('chime.view_functions.get_auth_data_file') as get_auth_data_file:
            # Show that email status does not require a call to auth CSV.
            response = self.test_client.get('/')
            self.assertEqual(response.status_code, 200, 'Should have worked')
            self.assertEqual(get_auth_data_file.call_count, 0, 'Should not have called get_auth_data_file()')
            
            # Show that a call to auth CSV was made, outside the timeout period.
            time.sleep(1.1)
            response = self.test_client.get('/')
            self.assertEqual(get_auth_data_file.call_count, 1, 'Should have called get_auth_data_file()')

        with HTTMock(self.auth_csv_example_allowed):
            # Show that email status was correctly updatedw with call to CSV.
            response = self.test_client.get('/')
            self.assertEqual(response.status_code, 200, 'Should have worked')

            response = self.test_client.post('/sign-out')
            self.assertEqual(response.status_code, 200)

            response = self.test_client.get('/')
            self.assertFalse('Start' in response.data)

    def test_need_description_to_start_activity(self):
        ''' You need a description to start a new activity
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.test_client, self)
                erica.sign_in(email='erica@example.com')

            pattern_template_comment_stripped = sub(ur'<!--|-->', u'', PATTERN_TEMPLATE_COMMENT)
            flash_message_text = u'Please describe what you\'re doing when you start a new activity!'

            # start a new task without a description or beneficiary
            erica.start_task(description=u'', beneficiary=u'')
            # the activities-list template reloaded
            comments = erica.soup.findAll(text=lambda text: isinstance(text, Comment))
            self.assertTrue(pattern_template_comment_stripped.format(u'activities-list') in comments)
            # verify that there's a flash message warning about submitting an empty description
            self.assertEqual(flash_message_text, erica.soup.find('li', class_='flash').text)

            # start a new task with no description but with a beneficiary
            fake_task_beneficiary = u'Scary Ghosts'
            erica.start_task(description=u'', beneficiary=fake_task_beneficiary)
            # the activities-list template reloaded
            comments = erica.soup.findAll(text=lambda text: isinstance(text, Comment))
            self.assertTrue(pattern_template_comment_stripped.format(u'activities-list') in comments)
            # verify that there's a flash message warning about submitting an empty description
            self.assertEqual(flash_message_text, erica.soup.find('li', class_='flash').text)
            # verify that the entered beneficiary text has been pre-filled in the form
            self.assertEqual(fake_task_beneficiary, erica.soup.find('input', attrs={'name': u'task_beneficiary'}).attrs['value'])

    # in TestApp
    def test_notification_on_create_category(self):
        ''' You get a flash notification when you create a category
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in('erica@example.com')

            # Start a new task
            erica.start_task(description=u'Lick Water Droplets From Leaves', beneficiary=u'Leopard Geckos')
            # Get the branch name
            branch_name = erica.get_branch_name()

            # Enter the "other" folder
            other_slug = u'other'
            erica.follow_link(href='/tree/{}/edit/{}'.format(branch_name, other_slug))

            # Create a category
            category_name = u'Rubber Plants'
            category_slug = slugify(category_name)
            erica.add_category(category_name=category_name)
            # the category is correctly represented on the page
            self.assertIsNotNone(erica.soup.find(lambda tag: bool(tag.name == 'a' and category_name in tag.text)))
            self.assertIsNotNone(erica.soup.find(lambda tag: bool(tag.name == 'a' and category_slug in tag['href'])))
            # a flash message appeared
            self.assertEqual(PATTERN_FLASH_CREATED_CATEGORY.format(title=category_name), erica.soup.find('li', class_='flash').text)

    # in TestApp
    def test_notifications_on_create_and_edit_article(self):
        ''' You get a flash notification when you create an article
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in('erica@example.com')

            # Start a new task
            erica.start_task(description=u'Lick Water Droplets From Leaves', beneficiary=u'Leopard Geckos')
            # Get the branch name
            branch_name = erica.get_branch_name()

            # Enter the "other" folder
            other_slug = u'other'
            erica.follow_link(href='/tree/{}/edit/{}'.format(branch_name, other_slug))

            # Create a category and sub-category
            category_name = u'Rubber Plants'
            subcategory_name = u'Leaves'
            erica.add_category(category_name=category_name)
            erica.add_subcategory(subcategory_name=subcategory_name)

            # Create an article
            article_name = u'Water Droplets'
            erica.add_article(article_name=article_name)
            # a flash message appeared
            self.assertEqual(PATTERN_FLASH_CREATED_ARTICLE.format(title=article_name), erica.soup.find('li', class_='flash').text)

            # edit the article
            erica.edit_article(title_str=u'Water Droplets', body_str=u'Watch out for poisonous insects.')
            # a flash message appeared
            self.assertEqual(PATTERN_FLASH_SAVED_ARTICLE.format(title=article_name), erica.soup.find('li', class_='flash').text)

    # in TestApp
    def test_branches(self):
        ''' Check basic branching functionality.
        '''
        fake_task_description = u'do things'
        fake_task_beneficiary = u'somebody else'
        fake_author_email = u'erica@example.com'
        fake_endorser_email = u'frances@example.com'
        fake_page_slug = u'hello'
        fake_page_path = u'{}/index.{}'.format(fake_page_slug, view_functions.CONTENT_FILE_EXTENSION)
        fake_page_content = u'People of earth we salute you.'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # create a new branch
            response = self.test_client.post('/start', data={'task_description': fake_task_description, 'task_beneficiary': fake_task_beneficiary}, follow_redirects=True)
            self.assertTrue(PATTERN_TEMPLATE_COMMENT.format('articles-list') in response.data)
            self.assertTrue(PATTERN_TASK_COMMENT.format(fake_task_description) in response.data)
            self.assertTrue(PATTERN_BENEFICIARY_COMMENT.format(fake_task_beneficiary) in response.data)
            self.assertTrue(PATTERN_AUTHOR_COMMENT.format(fake_author_email) in response.data)

            # extract the generated branch name from the returned HTML
            generated_branch_search = search(r'<!-- branch: (.{{{}}}) -->'.format(repo_functions.BRANCH_NAME_LENGTH), response.data)
            self.assertIsNotNone(generated_branch_search)
            try:
                generated_branch_name = generated_branch_search.group(1)
            except AttributeError:
                raise Exception('No match for generated branch name.')

        with HTTMock(self.mock_google_analytics):
            # create a new file
            response = self.test_client.post('/tree/{}/edit/'.format(generated_branch_name),
                                             data={'action': 'create', 'create_what': view_functions.ARTICLE_LAYOUT, 'request_path': fake_page_slug},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(fake_page_path in response.data)

            # get the index page for the branch and verify that the new file is listed
            response = self.test_client.get('/tree/{}/edit/'.format(generated_branch_name), follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(PATTERN_BRANCH_COMMENT.format(generated_branch_name) in response.data)
            self.assertTrue(PATTERN_FILE_COMMENT.format(**{"file_name": fake_page_slug, "file_title": fake_page_slug, "file_type": view_functions.ARTICLE_LAYOUT}) in response.data)

            # get the edit page for the new file and extract the hexsha value
            response = self.test_client.get('/tree/{}/edit/{}'.format(generated_branch_name, fake_page_path))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(fake_page_path in response.data)
            hexsha = search(r'<input name="hexsha" value="(\w+)"', response.data).group(1)
            # now save the file with new content
            response = self.test_client.post('/tree/{}/save/{}'.format(generated_branch_name, fake_page_path),
                                             data={'layout': view_functions.ARTICLE_LAYOUT, 'hexsha': hexsha,
                                                   'en-title': 'Greetings',
                                                   'en-body': u'{}\n'.format(fake_page_content),
                                                   'fr-title': '', 'fr-body': '',
                                                   'url-slug': u'{}/index'.format(fake_page_slug)},
                                             follow_redirects=True)

            self.assertEqual(response.status_code, 200)
            self.assertTrue(fake_page_path in response.data)
            self.assertTrue(fake_page_content in response.data)

        # Check that English and French forms are both present.
        self.assertTrue('name="fr-title"' in response.data)
        self.assertTrue('name="en-title"' in response.data)

        # Verify that navigation tabs are in the correct order.
        self.assertTrue(response.data.index('id="fr-nav"') < response.data.index('id="en-nav"'))

        # Request feedback on the change
        with HTTMock(self.auth_csv_example_allowed):
            response = self.test_client.post('/tree/{}/'.format(generated_branch_name), data={'comment_text': u'', 'request_feedback': u'Request Feedback'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(u'{} {}'.format(fake_author_email, repo_functions.ACTIVITY_FEEDBACK_MESSAGE) in response.data)

        #
        #
        # Log in as a different person
        with HTTMock(self.mock_persona_verify_frances):
            self.test_client.post('/sign-in', data={'email': fake_endorser_email})

        # Endorse the change
        with HTTMock(self.auth_csv_example_allowed):
            response = self.test_client.post('/tree/{}/'.format(generated_branch_name), data={'comment_text': u'', 'endorse_edits': 'Looks Good!'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(u'{} {}'.format(fake_endorser_email, repo_functions.ACTIVITY_ENDORSED_MESSAGE) in response.data)

        # And publish the change!
        with HTTMock(self.auth_csv_example_allowed):
            response = self.test_client.post('/tree/{}/'.format(generated_branch_name), data={'comment_text': u'', 'merge': 'Publish'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        # should've been redirected to the front page
        self.assertTrue(PATTERN_TEMPLATE_COMMENT.format('activities-list') in response.data)
        # the activity we just published shouldn't be listed on the page
        self.assertTrue(generated_branch_name not in response.data)
        
        # Look in the published directory and see if the words are there.
        with open(join(self.publish_path, fake_page_slug, 'index.html')) as file:
            self.assertTrue(fake_page_content in file.read())

    # in TestApp
    def test_delete_strange_tasks(self):
        ''' Delete a task that you can see on the activity list but haven't viewed or edited.
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            disposable_task_description = u'unimportant task'
            disposable_task_beneficiary = u'unimportant person'
            response = self.test_client.post('/start', data={'task_description': disposable_task_description, 'task_beneficiary': disposable_task_beneficiary}, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(PATTERN_TEMPLATE_COMMENT.format('articles-list') in response.data)
            self.assertTrue(PATTERN_TASK_COMMENT.format(disposable_task_description) in response.data)
            self.assertTrue(PATTERN_BENEFICIARY_COMMENT.format(disposable_task_beneficiary) in response.data)

            # create a branch programmatically on our pre-made clone
            check_task_description = u'Creating a Star Child'
            check_task_beneficiary = u'Ancient Aliens'
            check_branch = repo_functions.get_start_branch(self.clone1, 'master', check_task_description, check_task_beneficiary, fake_author_email)
            self.assertTrue(check_branch.name in self.clone1.branches)
            self.assertTrue(check_branch.name in self.origin.branches)
            # verify that the branch doesn't exist in our new clone
            with self.app.app_context():
                with self.app.test_request_context():
                    from flask import session
                    session['email'] = fake_author_email
                    new_clone = view_functions.get_repo(flask_app=self.app)
                    self.assertFalse(check_branch.name in new_clone.branches)

            # load the activity list and verify that the branch is visible there
            response = self.test_client.get('/', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(check_branch.name in response.data)

            # Delete the activity
            response = self.test_client.post('/update', data={'abandon': 'Delete', 'branch': '{}'.format(check_branch.name)}, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(check_branch.name in response.data)

    # in TestApp
    def test_review_process(self):
        ''' Check the review process
        '''
        fake_task_description = u'groom pets'
        fake_task_beneficiary = u'pet owners'
        fake_author_email = u'erica@example.com'
        fake_endorser_email = u'frances@example.com'
        fake_page_slug = u'hello'

        # log in
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # create a new branch
            response = self.test_client.post('/start', data={'task_description': fake_task_description, 'task_beneficiary': fake_task_beneficiary}, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(PATTERN_TEMPLATE_COMMENT.format('articles-list') in response.data)

            # extract the generated branch name from the returned HTML
            generated_branch_search = search(r'<!-- branch: (.{{{}}}) -->'.format(repo_functions.BRANCH_NAME_LENGTH), response.data)
            self.assertIsNotNone(generated_branch_search)
            try:
                generated_branch_name = generated_branch_search.group(1)
            except AttributeError:
                raise Exception('No match for generated branch name.')

            # create a new file
            response = self.test_client.post('/tree/{}/edit/'.format(generated_branch_name),
                                             data={'action': 'create', 'create_what': view_functions.ARTICLE_LAYOUT, 'request_path': fake_page_slug},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            # get the edit page for the branch
            response = self.test_client.get('/tree/{}/edit/'.format(generated_branch_name), follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # verify that there's a 'request feedback' button
            self.assertTrue(PATTERN_REQUEST_FEEDBACK_BUTTON in response.data)

            # get the overview page for the branch
            response = self.test_client.get('/tree/{}/'.format(generated_branch_name), follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # verify that there's a 'request feedback' button
            self.assertTrue(PATTERN_REQUEST_FEEDBACK_BUTTON in response.data)

            # get the activity list page
            response = self.test_client.get('/', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # verify that there's an 'unreviewed edits' link
            self.assertTrue(PATTERN_UNREVIEWED_EDITS_LINK.format(branch_name=generated_branch_name) in response.data)

        # Request feedback on the change
        with HTTMock(self.auth_csv_example_allowed):
            response = self.test_client.post('/tree/{}/'.format(generated_branch_name), data={'comment_text': u'', 'request_feedback': u'Request Feedback'}, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(u'{} {}'.format(fake_author_email, repo_functions.ACTIVITY_FEEDBACK_MESSAGE) in response.data)

        #
        #
        # Log in as a different person
        with HTTMock(self.mock_persona_verify_frances):
            self.test_client.post('/sign-in', data={'email': fake_endorser_email})

        with HTTMock(self.auth_csv_example_allowed):
            # get the edit page for the branch
            response = self.test_client.get('/tree/{}/edit/'.format(generated_branch_name), follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # verify that there's a 'looks good!' button
            self.assertTrue(PATTERN_ENDORSE_BUTTON in response.data)

            # get the overview page for the branch
            response = self.test_client.get('/tree/{}/'.format(generated_branch_name), follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # verify that there's a 'looks good!' button
            self.assertTrue(PATTERN_ENDORSE_BUTTON in response.data)

            # get the activity list page
            response = self.test_client.get('/', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # verify that there's an 'feedback requested' link
            self.assertTrue(PATTERN_FEEDBACK_REQUESTED_LINK.format(branch_name=generated_branch_name) in response.data)

        # Endorse the change
        with HTTMock(self.auth_csv_example_allowed):
            response = self.test_client.post('/tree/{}/'.format(generated_branch_name), data={'comment_text': u'', 'endorse_edits': 'Looks Good!'}, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(u'{} {}'.format(fake_endorser_email, repo_functions.ACTIVITY_ENDORSED_MESSAGE) in response.data)

        # log back in as the original editor
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # get the edit page for the branch
            response = self.test_client.get('/tree/{}/edit/'.format(generated_branch_name), follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # verify that there's a 'publish' button
            self.assertTrue(PATTERN_PUBLISH_BUTTON in response.data)

            # get the overview page for the branch
            response = self.test_client.get('/tree/{}/'.format(generated_branch_name), follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # verify that there's a 'publish' button
            self.assertTrue(PATTERN_PUBLISH_BUTTON in response.data)

            # get the activity list page
            response = self.test_client.get('/', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # verify that there's an 'ready to publish' link
            self.assertTrue(PATTERN_READY_TO_PUBLISH_LINK.format(branch_name=generated_branch_name) in response.data)

        # And publish the change!
        with HTTMock(self.auth_csv_example_allowed):
            response = self.test_client.post('/tree/{}/'.format(generated_branch_name), data={'comment_text': u'', 'merge': 'Publish'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        # should've been redirected to the front page
        self.assertTrue(PATTERN_TEMPLATE_COMMENT.format('activities-list') in response.data)
        # the activity we just published shouldn't be listed on the page
        self.assertTrue(generated_branch_name not in response.data)

    # in TestApp
    def test_get_request_does_not_create_branch(self):
        ''' Navigating to a made-up URL should not create a branch
        '''
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': 'erica@example.com'})

        with HTTMock(self.auth_csv_example_allowed):
            fake_branch_name = 'this-should-not-create-a-branch'
            #
            # edit
            #
            response = self.test_client.get('/tree/{}/edit/'.format(fake_branch_name), follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # the branch path should not be in the returned HTML
            self.assertFalse(PATTERN_BRANCH_COMMENT.format(fake_branch_name) in response.data)
            # the branch name should not be in the origin's branches list
            self.assertFalse(fake_branch_name in self.origin.branches)

            #
            # history
            #
            response = self.test_client.get('/tree/{}/history/'.format(fake_branch_name), follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # the branch path should not be in the returned HTML
            self.assertFalse(PATTERN_BRANCH_COMMENT.format(fake_branch_name) in response.data)
            # the branch name should not be in the origin's branches list
            self.assertFalse(fake_branch_name in self.origin.branches)

            #
            # view
            #
            response = self.test_client.get('/tree/{}/view/'.format(fake_branch_name), follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # the branch path should not be in the returned HTML
            self.assertFalse(PATTERN_BRANCH_COMMENT.format(fake_branch_name) in response.data)
            # the branch name should not be in the origin's branches list
            self.assertFalse(fake_branch_name in self.origin.branches)

    # in TestApp
    def test_post_request_does_not_create_branch(self):
        ''' Certain POSTs to a made-up URL should not create a branch
        '''
        fake_page_slug = u'hello'
        fake_page_path = u'{}/index.{}'.format(fake_page_slug, view_functions.CONTENT_FILE_EXTENSION)

        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': 'erica@example.com'})

        with HTTMock(self.auth_csv_example_allowed):
            #
            # try adding a new file
            #
            fake_task_description = u'This should not create a branch'
            fake_task_beneficiary = u'Nobody'
            fake_branch_name = repo_functions.make_branch_name()
            response = self.test_client.post('/tree/{}/edit/'.format(fake_branch_name), data={'action': 'create', 'create_what': view_functions.ARTICLE_LAYOUT, 'request_path': fake_page_slug}, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # the branch name should not be in the returned HTML
            # :TODO: need an assertion for this
            # the branch name should not be in the origin's branches list
            self.assertFalse(fake_branch_name in self.origin.branches)

            #
            # create a branch then delete it right before a POSTing a save command
            #
            response = self.test_client.post('/start', data={'task_description': fake_task_description, 'task_beneficiary': fake_task_beneficiary}, follow_redirects=True)
            # we should be on the new task's edit page
            self.assertEqual(response.status_code, 200)
            self.assertTrue(PATTERN_TEMPLATE_COMMENT.format('articles-list') in response.data)
            self.assertTrue(PATTERN_TASK_COMMENT.format(fake_task_description) in response.data)
            self.assertTrue(PATTERN_BENEFICIARY_COMMENT.format(fake_task_beneficiary) in response.data)

            # extract the generated branch name from the returned HTML
            generated_branch_search = search(r'<!-- branch: (.{{{}}}) -->'.format(repo_functions.BRANCH_NAME_LENGTH), response.data)
            self.assertIsNotNone(generated_branch_search)
            try:
                generated_branch_name = generated_branch_search.group(1)
            except AttributeError:
                raise Exception('No match for generated branch name.')

            # create a new article
            response = self.test_client.post('/tree/{}/edit/'.format(generated_branch_name), data={'action': 'create', 'create_what': view_functions.ARTICLE_LAYOUT, 'request_path': fake_page_slug}, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(PATTERN_TEMPLATE_COMMENT.format('article-edit') in response.data)

            response = self.test_client.get('/tree/{}/edit/'.format(generated_branch_name), follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(PATTERN_TEMPLATE_COMMENT.format('articles-list') in response.data)
            self.assertTrue(PATTERN_BRANCH_COMMENT.format(generated_branch_name) in response.data)
            self.assertTrue(PATTERN_FILE_COMMENT.format(**{"file_name": fake_page_slug, "file_title": fake_page_slug, "file_type": view_functions.ARTICLE_LAYOUT}) in response.data)

            response = self.test_client.get('/tree/{}/edit/{}'.format(generated_branch_name, fake_page_path))
            self.assertEqual(response.status_code, 200)
            hexsha = search(r'<input name="hexsha" value="(\w+)"', response.data).group(1)

            # delete the branch
            response = self.test_client.post('/update', data={'abandon': 'Delete', 'branch': '{}'.format(generated_branch_name)}, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(generated_branch_name in response.data)

            response = self.test_client.post('/tree/{}/save/{}'.format(generated_branch_name, fake_page_path), data={'layout': view_functions.ARTICLE_LAYOUT, 'hexsha': hexsha, 'en-title': 'Greetings', 'en-body': 'Hello world.\n', 'fr-title': '', 'fr-body': '', 'url-slug': 'hello'}, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # the task name should not be in the returned HTML
            self.assertFalse(PATTERN_BRANCH_COMMENT.format(fake_task_description) in response.data)
            # 'content tips', which is in the tree-branch-edit template, shouldn't be in the returned HTML either
            self.assertFalse('Content tips' in response.data)
            # the branch name should not be in the origin's branches list
            self.assertFalse('{}'.format(generated_branch_name) in self.origin.branches)

    # in TestApp
    def test_accessing_local_branch_fetches_remote(self):
        ''' GETting or POSTing to a URL that indicates a branch that exists remotely but not locally
            fetches the remote branch and allows access
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            disposable_task_description = u'unimportant task'
            disposable_task_beneficiary = u'unimportant person'
            response = self.test_client.post('/start', data={'task_description': disposable_task_description, 'task_beneficiary': disposable_task_beneficiary}, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(PATTERN_TEMPLATE_COMMENT.format('articles-list') in response.data)
            self.assertTrue(PATTERN_TASK_COMMENT.format(disposable_task_description) in response.data)
            self.assertTrue(PATTERN_BENEFICIARY_COMMENT.format(disposable_task_beneficiary) in response.data)

            # create a branch programmatically on our pre-made clone
            check_task_description = u'the branch we are checking for'
            check_task_beneficiary = u'just me'
            check_branch = repo_functions.get_start_branch(self.clone1, 'master', check_task_description, check_task_beneficiary, fake_author_email)
            self.assertTrue(check_branch.name in self.clone1.branches)
            self.assertTrue(check_branch.name in self.origin.branches)
            # verify that the branch doesn't exist in our new clone
            with self.app.app_context():
                with self.app.test_request_context():
                    from flask import session
                    session['email'] = fake_author_email
                    new_clone = view_functions.get_repo(flask_app=self.app)
                    self.assertFalse(check_branch.name in new_clone.branches)

            # request an edit page for the check branch through the http interface
            response = self.test_client.get('/tree/{}/edit/'.format(check_branch.name), follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # the task description should be in the returned HTML
            self.assertTrue(PATTERN_TEMPLATE_COMMENT.format('articles-list') in response.data)
            self.assertTrue(PATTERN_TASK_COMMENT.format(check_task_description) in response.data)
            self.assertTrue(PATTERN_BENEFICIARY_COMMENT.format(check_task_beneficiary) in response.data)

            # the branch name should now be in the original repo's branches list
            self.assertTrue(check_branch.name in new_clone.branches)

    # in TestApp
    def test_git_merge_strategy_implemented(self):
        ''' The Git merge strategy has been implmemented for a new clone.
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # create a new clone via get_repo
            with self.app.app_context():
                with self.app.test_request_context():
                    from flask import session
                    session['email'] = fake_author_email
                    new_clone = view_functions.get_repo(flask_app=self.app)

            # check for the config setting
            self.assertEqual(new_clone.config_reader().get_value('merge "ignored"', 'driver'), True)

            # check for the attributes setting
            attributes_path = join(new_clone.git_dir, 'info/attributes')
            self.assertTrue(exists(attributes_path))
            with open(attributes_path, 'r') as file:
                content = file.read().decode("utf-8")
            self.assertEqual(content, u'{} merge=ignored'.format(repo_functions.TASK_METADATA_FILENAME))

    # in TestApp
    def test_task_metadata_should_exist(self):
        ''' Task metadata file should exist but doesn't
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        fake_task_description = u'unimportant task'
        fake_task_beneficiary = u'unimportant person'
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', fake_task_description, fake_task_beneficiary, fake_author_email)
        branch1_name = branch1.name
        branch1.checkout()

        # verify that the most recent commit on the new branch is for the task metadata file
        # by checking for the name of the file in the commit message
        self.assertTrue(repo_functions.TASK_METADATA_FILENAME in branch1.commit.message)

        # validate the existence of the task metadata file
        self.assertTrue(repo_functions.verify_file_exists_in_branch(self.clone1, repo_functions.TASK_METADATA_FILENAME, branch1_name))

        # now delete it
        repo_functions.delete_task_metadata_for_branch(self.clone1, 'master')
        self.assertFalse(repo_functions.verify_file_exists_in_branch(self.clone1, repo_functions.TASK_METADATA_FILENAME, branch1_name))

        # verify that we can load a functional edit page for the branch
        with HTTMock(self.auth_csv_example_allowed):
            # request an edit page for the check branch through the http interface
            response = self.test_client.get('/tree/{}/edit/'.format(branch1_name), follow_redirects=True)
            # it's a good response
            self.assertEqual(response.status_code, 200)
            # the branch name should be in the returned HTML
            self.assertTrue(PATTERN_BRANCH_COMMENT.format(branch1_name) in response.data)
            # the 'Started by' should be 'Unknown' for now
            self.assertTrue(PATTERN_AUTHOR_COMMENT.format(u'unknown') in response.data)

    # in TestApp
    def test_google_callback_is_successful(self):
        ''' Ensure we get a successful page load on callback from Google authentication
        '''
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': 'erica@example.com'})

        with HTTMock(self.mock_google_authorization):
            self.test_client.post('/authorize')

        with HTTMock(self.mock_successful_google_callback):
            response = self.test_client.get('/callback?state=PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP&code=code')

        with self.app.app_context():
            ga_config = google_api_functions.read_ga_config(self.app.config['RUNNING_STATE_DIR'])

        self.assertEqual(ga_config['access_token'], 'meowser_token')
        self.assertEqual(ga_config['refresh_token'], 'refresh_meows')

        self.assertTrue('/setup' in response.location)

    # in TestApp
    def test_analytics_setup_is_successful(self):
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': 'erica@example.com'})

        with HTTMock(self.mock_google_authorization):
            self.test_client.post('/authorize')

        # mock-post the form in authorize.html to authorization-complete.html with some dummy values and check the results
        response = self.test_client.post('/authorization-complete', data={'email': 'erica@example.com', 'name': 'Jane Doe', 'google_email': 'erica@example.com', 'return_link': 'http://example.com', 'property': '12345678', '12345678-domain': 'http://propertyone.example.com', '12345678-name': 'Property One'})

        self.assertEqual(u'200 OK', response.status)

        with self.app.app_context():
            ga_config = google_api_functions.read_ga_config(self.app.config['RUNNING_STATE_DIR'])

        # views.authorization_complete() strips the 'http://' from the domain
        self.assertEqual(ga_config['project_domain'], 'propertyone.example.com')
        self.assertEqual(ga_config['profile_id'], '12345678')

    # in TestApp
    def test_handle_bad_analytics_response(self):
        ''' Verify that an unauthorized analytics response is handled correctly
        '''
        with HTTMock(self.mock_google_invalid_credentials_response):
            with self.app.app_context():
                analytics_dict = google_api_functions.fetch_google_analytics_for_page(self.app.config, u'index.html', 'meowser_token')
            self.assertEqual(analytics_dict, {})

    # in TestApp
    def test_google_callback_fails(self):
        ''' Ensure that we get an appropriate error flashed when we fail to auth with google
        '''
        with HTTMock(self.mock_persona_verify_erica):
            response = self.test_client.post('/sign-in', data={'email': 'erica@example.com'})

        with HTTMock(self.mock_google_authorization):
            response = self.test_client.post('/authorize')

        with HTTMock(self.mock_failed_google_callback):
            response = self.test_client.get('/callback?state=PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP&code=code', follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        # find the flashed error message in the returned HTML
        self.assertTrue('Google rejected authorization request' in response.data)

    # in TestApp
    def test_invalid_access_token(self):
        ''' Ensure that we get an appropriate error flashed when we have an invalid access token
        '''
        with HTTMock(self.mock_persona_verify_erica):
            response = self.test_client.post('/sign-in', data={'email': 'erica@example.com'})
            self.assertEqual(response.status_code, 200)

        with HTTMock(self.mock_google_invalid_credentials_response):
            response = self.test_client.get('/setup', follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        # find the flashed error message in the returned HTML
        self.assertTrue('Invalid Credentials' in response.data)

    # in TestApp
    def test_no_properties_found(self):
        ''' Ensure that we get an appropriate error flashed when no analytics properties are
            associated with the authorized Google account
        '''
        with HTTMock(self.mock_persona_verify_erica):
            response = self.test_client.post('/sign-in', data={'email': 'erica@example.com'})
            self.assertEqual(response.status_code, 200)

        with HTTMock(self.mock_google_no_properties_response):
            response = self.test_client.get('/setup', follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        # find the flashed error message in the returned HTML
        self.assertTrue('Your Google Account is not associated with any Google Analytics properties' in response.data)

    # in TestApp
    def test_redirect(self):
        ''' Check redirect to BROWSERID_URL.
        '''
        with HTTMock(self.mock_persona_verify_erica):
            response = self.test_client.get('/not-allowed', headers={'Host': 'wrong.local'})

        expected_url = urljoin(self.app.config['BROWSERID_URL'], '/not-allowed')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], expected_url)

    # in TestApp
    def test_create_category(self):
        ''' Creating a new category creates a directory with an appropriate index file inside.
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            task_description = u'force a clam shell open'
            task_beneficiary = u'starfish'

            working_branch = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
            self.assertTrue(working_branch.name in self.clone1.branches)
            self.assertTrue(working_branch.name in self.origin.branches)
            working_branch_name = working_branch.name
            working_branch.checkout()

            # create a new category
            page_slug = u'hello'
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch_name),
                                             data={'action': 'create', 'create_what': view_functions.CATEGORY_LAYOUT, 'request_path': page_slug},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # a directory was created
            dir_location = join(self.clone1.working_dir, page_slug)
            idx_location = u'{}/index.{}'.format(dir_location, view_functions.CONTENT_FILE_EXTENSION)
            self.assertTrue(exists(dir_location) and isdir(dir_location))
            # an index page was created inside
            self.assertTrue(exists(idx_location))
            # the directory and index page pass the category test
            self.assertTrue(view_functions.is_category_dir(dir_location))

    # in TestApp
    def test_period_in_category_name(self):
        ''' Putting a period in a category or subcategory name doesn't crop it.
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.test_client, self)
                erica.sign_in(email='erica@example.com')

            # Start a new task
            erica.start_task(description=u'Be Shot Hundreds Of Feet Into The Air', beneficiary=u'A Geyser Of Highly Pressurized Water')
            # Get the branch name
            branch_name = erica.get_branch_name()

            # Enter the "other" folder
            other_slug = u'other'
            erica.follow_link(href='/tree/{}/edit/{}'.format(branch_name, other_slug))

            # Create a category that has a period in its name
            category_name = u'Mt. Splashmore'
            category_slug = slugify(category_name)
            erica.add_category(category_name=category_name)
            # the category is correctly represented on the page
            self.assertIsNotNone(erica.soup.find(lambda tag: bool(tag.name == 'a' and category_name in tag.text)))
            self.assertIsNotNone(erica.soup.find(lambda tag: bool(tag.name == 'a' and category_slug in tag['href'])))

            # the category is correctly represented on disk
            repo = view_functions.get_repo(repo_path=self.app.config['REPO_PATH'], work_path=self.app.config['WORK_PATH'], email='erica@example.com')
            cat_location = join(repo.working_dir, u'{}/{}'.format(other_slug, category_slug))
            self.assertTrue(exists(cat_location))
            self.assertTrue(view_functions.is_category_dir(cat_location))

    # in TestApp
    def test_empty_category_or_article_name(self):
        ''' Submitting an empty category or article name reloads with a warning.
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.test_client, self)
                erica.sign_in(email='erica@example.com')

            pattern_template_comment_stripped = sub(ur'<!--|-->', u'', PATTERN_TEMPLATE_COMMENT)

            # Start a new task
            erica.start_task(description=u'Deep-Fry a Buffalo in Forty Seconds', beneficiary=u'Moe')
            # Get the branch name
            branch_name = erica.get_branch_name()

            # Enter the "other" folder
            other_slug = u'other'
            erica.follow_link(href='/tree/{}/edit/{}'.format(branch_name, other_slug))

            # Try to create a category with no name
            category_name = u''
            erica.add_category(category_name=category_name)
            # the articles-list template reloaded
            comments = erica.soup.findAll(text=lambda text: isinstance(text, Comment))
            self.assertTrue(pattern_template_comment_stripped.format(u'articles-list') in comments)
            # verify that there's a flash message warning about submitting an empty description
            self.assertEqual(u'Please enter a name to create a category!', erica.soup.find('li', class_='flash').text)

            # Try to create a category with a name that slufigies to an empty string
            category_name = u'(╯□）╯︵ ┻━┻'
            self.assertEqual(u'', slugify(category_name))
            erica.add_category(category_name=category_name)
            # the articles-list template reloaded
            comments = erica.soup.findAll(text=lambda text: isinstance(text, Comment))
            self.assertTrue(pattern_template_comment_stripped.format(u'articles-list') in comments)
            # verify that there's a flash message warning about submitting an empty description
            self.assertEqual(u'{} is not an acceptable category name!'.format(category_name), erica.soup.find('li', class_='flash').text)

            # Create a category and sub-category
            category_name = u'Mammals'
            subcategory_name = u'Bison'
            erica.add_category(category_name=category_name)
            erica.add_subcategory(subcategory_name=subcategory_name)

            # Try to create an article with no name
            article_name = u''
            erica.add_article(article_name=article_name)
            # the articles-list template reloaded
            comments = erica.soup.findAll(text=lambda text: isinstance(text, Comment))
            self.assertTrue(pattern_template_comment_stripped.format(u'articles-list') in comments)
            # verify that there's a flash message warning about submitting an empty description
            self.assertEqual(u'Please enter a name to create an article!', erica.soup.find('li', class_='flash').text)

            # Try to create a article with a name that slufigies to an empty string
            article_name = u'(╯□）╯︵ ┻━┻'
            self.assertEqual(u'', slugify(article_name))
            erica.add_article(article_name=article_name)
            # the articles-list template reloaded
            comments = erica.soup.findAll(text=lambda text: isinstance(text, Comment))
            self.assertTrue(pattern_template_comment_stripped.format(u'articles-list') in comments)
            # verify that there's a flash message warning about submitting an empty description
            self.assertEqual(u'{} is not an acceptable article name!'.format(article_name), erica.soup.find('li', class_='flash').text)

    # in TestApp
    def test_create_duplicate_category(self):
        ''' If we ask to create a category that exists, let's not and say we did.
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            working_branch = repo_functions.get_start_branch(self.clone1, 'master', u'force a clam shell open',
                                                             u'starfish', fake_author_email)
            working_branch.checkout()

            # create a new category
            request_data = {'action': 'create', 'create_what': view_functions.CATEGORY_LAYOUT, 'request_path': u'hello'}
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch.name),
                                             data=request_data,
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            # now do it again
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch.name),
                                             data=request_data,
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            response_data = sub('&#34;', '"', response.data.decode('utf-8'))
            self.assertTrue(u'Category "hello" already exists' in response_data)

            # pull the changes
            self.clone1.git.pull('origin', working_branch.name)

            # everything looks good
            dir_location = join(self.clone1.working_dir, u'hello')
            idx_location = u'{}/index.{}'.format(dir_location, view_functions.CONTENT_FILE_EXTENSION)
            self.assertTrue(exists(dir_location) and isdir(dir_location))
            # an index page was created inside
            self.assertTrue(exists(idx_location))
            # the directory and index page pass the category test
            self.assertTrue(view_functions.is_category_dir(dir_location))

    # in TestApp
    def test_delete_categories_and_articles(self):
        ''' Non-empty categories and articles can be deleted
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            task_description = u'vomit digestive fluid onto rotting flesh'
            task_beneficiary = u'flies'

            working_branch = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
            self.assertTrue(working_branch.name in self.clone1.branches)
            self.assertTrue(working_branch.name in self.origin.branches)
            working_branch_name = working_branch.name
            working_branch.checkout()

            # create a categories directory
            categories_slug = u'categories'
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch_name),
                                             data={'action': 'create', 'create_what': view_functions.CATEGORY_LAYOUT, 'request_path': categories_slug},
                                             follow_redirects=True)

            # and put a new category inside it
            cata_title = u'Mouth Parts'
            cata_slug = slugify(cata_title)
            response = self.test_client.post('/tree/{}/edit/{}'.format(working_branch_name, categories_slug),
                                             data={'action': 'create', 'create_what': view_functions.CATEGORY_LAYOUT, 'request_path': cata_title},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            # put another cateogry inside that
            catb_title = u'Esophagus'
            catb_slug = slugify(catb_title)
            response = self.test_client.post('/tree/{}/edit/{}'.format(working_branch_name, join(categories_slug, cata_slug)),
                                             data={'action': 'create', 'create_what': view_functions.CATEGORY_LAYOUT, 'request_path': catb_title},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            # and an article inside that
            art_title = u'Stomach'
            art_slug = slugify(art_title)
            response = self.test_client.post('/tree/{}/edit/{}'.format(working_branch_name, join(categories_slug, cata_slug, catb_slug)),
                                             data={'action': 'create', 'create_what': view_functions.ARTICLE_LAYOUT, 'request_path': art_title},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # verify that the categories and article exist
            art_location = join(self.clone1.working_dir, categories_slug, cata_slug, catb_slug, art_slug)
            catb_location = join(self.clone1.working_dir, categories_slug, cata_slug, catb_slug)
            cata_location = join(self.clone1.working_dir, categories_slug, cata_slug)
            self.assertTrue(exists(art_location))
            self.assertTrue(view_functions.is_article_dir(art_location))

            # delete category a while in category b
            response = self.test_client.post('/tree/{}/edit/{}'.format(working_branch_name, join(categories_slug, cata_slug, catb_slug)),
                                             data={'action': 'delete', 'request_path': join(categories_slug, cata_slug)},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # verify that the deleted category and article no longer exist
            self.assertFalse(exists(art_location))
            self.assertFalse(exists(catb_location))
            self.assertFalse(exists(cata_location))

    # in TestApp
    def test_delete_commit_accuracy(self):
        ''' The record of a delete in the corresponding commit is accurate.
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                user = ChimeTestClient(self.test_client, self)
                user.sign_in(email='erica@example.com')

            # Start a new task
            user.start_task(description=u'Ferment Tuber Fibres Using Symbiotic Bacteria in the Intestines', beneficiary=u'Naked Mole Rats')
            # Get the branch name
            branch_name = user.get_branch_name()

            # Enter the "other" folder
            user.follow_link(href='/tree/{}/edit/other'.format(branch_name))

            # Create a category and fill it with some subcategories and articles
            category_names = [u'Indigestible Cellulose']
            subcategory_names = [u'Volatile Fatty Acids', u'Non-Reproducing Females', u'Arid African Deserts']
            article_names = [u'Eusocial Exhibition', u'Old Enough to Eat Solid Food', u'Contributing to Extension of Tunnels', u'Foraging and Nest Building']
            user.add_category(category_name=category_names[0])
            
            category_path = user.path
            user.add_subcategory(subcategory_name=subcategory_names[0])
            user.open_link(category_path)
            user.add_subcategory(subcategory_name=subcategory_names[1])
            user.open_link(category_path)
            user.add_subcategory(subcategory_name=subcategory_names[2])

            subcategory_path = user.path
            user.add_article(article_name=article_names[0])
            user.open_link(subcategory_path)
            user.add_article(article_name=article_names[1])
            user.open_link(subcategory_path)
            user.add_article(article_name=article_names[2])
            user.open_link(subcategory_path)
            user.add_article(article_name=article_names[3])

            # Delete the all-containing category
            user.open_link(category_path)
            user.follow_modify_category_link(category_names[0])
            user.delete_category()

            # get and check the history
            repo = view_functions.get_repo(repo_path=self.app.config['REPO_PATH'], work_path=self.app.config['WORK_PATH'], email='erica@example.com')
            activity_history = view_functions.make_activity_history(repo=repo)
            delete_history = json.loads(activity_history[0]['commit_body'])
            for item in delete_history:
                self.assertEqual(item['action'], u'delete')
                if item['title'] in category_names:
                    self.assertEqual(item['display_type'], u'category')
                    category_names.remove(item['title'])

                elif item['title'] in subcategory_names:
                    self.assertEqual(item['display_type'], u'category')
                    subcategory_names.remove(item['title'])

                elif item['title'] in article_names:
                    self.assertEqual(item['display_type'], u'article')
                    article_names.remove(item['title'])

            # we should have fewer category, subcategory, and article names
            self.assertEqual(len(category_names), 0)
            self.assertEqual(len(subcategory_names), 0)
            self.assertEqual(len(article_names), 0)

    # in TestApp
    def test_delete_article(self):
        ''' An article can be deleted
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            task_description = u'Remove Small Organic Particles From Seawater Passing Over Outspread Tentacles'
            task_beneficiary = u'Sea Anemones'

            working_branch = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
            self.assertTrue(working_branch.name in self.clone1.branches)
            self.assertTrue(working_branch.name in self.origin.branches)
            working_branch_name = working_branch.name
            working_branch.checkout()

            # create an article
            art_title = u'Zooplankters'
            art_slug = slugify(art_title)
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch_name),
                                             data={'action': 'create', 'create_what': view_functions.ARTICLE_LAYOUT, 'request_path': art_title},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # verify that the article exists
            art_location = join(self.clone1.working_dir, art_slug)
            self.assertTrue(exists(art_location))
            self.assertTrue(view_functions.is_article_dir(art_location))

            # delete the article
            response = self.test_client.post('/tree/{}/edit/{}'.format(working_branch_name, art_slug),
                                             data={'action': 'delete', 'request_path': art_slug},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # verify that the deleted category and article no longer exist
            self.assertFalse(exists(art_location))

    # in TestApp
    def test_article_creation_with_unicode_via_web_interface(self):
        ''' An article with unicode in its title is created as expected.
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            task_description = u'eviscerate a salmon'
            task_beneficiary = u'baby grizzly bears'

            working_branch = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
            self.assertTrue(working_branch.name in self.clone1.branches)
            self.assertTrue(working_branch.name in self.origin.branches)
            working_branch_name = working_branch.name
            working_branch.checkout()

            # create a new article
            art_title = u'快速狐狸'
            art_slug = slugify(art_title)
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch_name), data={'action': 'create', 'create_what': view_functions.ARTICLE_LAYOUT, 'request_path': art_title}, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(PATTERN_TEMPLATE_COMMENT.format(u'article-edit') in response.data.decode('utf-8'))

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # a directory was created
            dir_location = join(self.clone1.working_dir, art_slug)
            idx_location = u'{}/index.{}'.format(dir_location, view_functions.CONTENT_FILE_EXTENSION)
            self.assertTrue(exists(dir_location) and isdir(dir_location))
            # an index page was created inside
            self.assertTrue(exists(idx_location))
            # the directory and index page pass the article test
            self.assertTrue(view_functions.is_article_dir(dir_location))
            # the title saved in the index front matter is the same text that was used to create the article
            self.assertEqual(view_functions.get_value_from_front_matter('title', idx_location), art_title)

            # the title saved in the index front matter is displayed on the article list page
            response = self.test_client.get('/tree/{}/edit/'.format(working_branch_name), follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(PATTERN_TEMPLATE_COMMENT.format(u'articles-list') in response.data.decode('utf-8'))
            self.assertTrue(PATTERN_BRANCH_COMMENT.format(working_branch) in response.data.decode('utf-8'))
            self.assertTrue(PATTERN_FILE_COMMENT.format(**{"file_name": art_slug, "file_title": art_title, "file_type": view_functions.ARTICLE_LAYOUT}) in response.data.decode('utf-8'))

    # in TestApp
    def test_new_item_has_name_and_title(self):
        ''' A slugified directory name and display title are created when a new category or article is created.
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            task_description = u'eviscerate a salmon'
            task_beneficiary = u'baby grizzly bears'

            working_branch = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
            self.assertTrue(working_branch.name in self.clone1.branches)
            self.assertTrue(working_branch.name in self.origin.branches)
            working_branch_name = working_branch.name
            working_branch.checkout()

            # create a new category
            cat_title = u'grrowl!! Yeah'
            cat_slug = slugify(cat_title)
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch_name),
                                             data={'action': 'create', 'create_what': view_functions.CATEGORY_LAYOUT, 'request_path': cat_title},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # a directory was created
            dir_location = join(self.clone1.working_dir, cat_slug)
            idx_location = u'{}/index.{}'.format(dir_location, view_functions.CONTENT_FILE_EXTENSION)
            self.assertTrue(exists(dir_location) and isdir(dir_location))
            # an index page was created inside
            self.assertTrue(exists(idx_location))
            # the directory and index page pass the category test
            self.assertTrue(view_functions.is_category_dir(dir_location))
            # the title saved in the index front matter is the same text that was used to create the category
            self.assertEqual(view_functions.get_value_from_front_matter('title', idx_location), cat_title)

            # the title saved in the index front matter is displayed on the article list page
            response = self.test_client.get('/tree/{}/edit/'.format(working_branch_name), follow_redirects=True)
            self.assertTrue(PATTERN_FILE_COMMENT.format(**{"file_name": cat_slug, "file_title": cat_title, "file_type": view_functions.CATEGORY_LAYOUT}) in response.data)

            # create a new article
            art_title = u'快速狐狸'
            art_slug = slugify(art_title)
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch_name), data={'action': 'create', 'create_what': view_functions.ARTICLE_LAYOUT, 'request_path': art_title}, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(PATTERN_TEMPLATE_COMMENT.format(u'article-edit') in response.data.decode('utf-8'))

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # a directory was created
            dir_location = join(self.clone1.working_dir, art_slug)
            idx_location = u'{}/index.{}'.format(dir_location, view_functions.CONTENT_FILE_EXTENSION)
            self.assertTrue(exists(dir_location) and isdir(dir_location))
            # an index page was created inside
            self.assertTrue(exists(idx_location))
            # the directory and index page pass the article test
            self.assertTrue(view_functions.is_article_dir(dir_location))
            # the title saved in the index front matter is the same text that was used to create the article
            self.assertEqual(view_functions.get_value_from_front_matter('title', idx_location), art_title)

            # the title saved in the index front matter is displayed on the article list page
            response = self.test_client.get('/tree/{}/edit/'.format(working_branch_name), follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(PATTERN_TEMPLATE_COMMENT.format(u'articles-list') in response.data.decode('utf-8'))
            self.assertTrue(PATTERN_BRANCH_COMMENT.format(working_branch) in response.data.decode('utf-8'))
            self.assertTrue(PATTERN_FILE_COMMENT.format(**{"file_name": art_slug, "file_title": art_title, "file_type": view_functions.ARTICLE_LAYOUT}) in response.data.decode('utf-8'))

    # in TestApp
    def test_edit_category_title_and_description(self):
        ''' A category's title and description can be edited.
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            task_description = u'rapidly discharge black ink into the mantle cavity'
            task_beneficiary = u'squids'

            working_branch = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
            self.assertTrue(working_branch.name in self.clone1.branches)
            self.assertTrue(working_branch.name in self.origin.branches)
            working_branch_name = working_branch.name
            working_branch.checkout()

            # create a categories directory
            categories_slug = u'categories'
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch_name),
                                             data={'action': 'create', 'create_what': view_functions.CATEGORY_LAYOUT, 'request_path': categories_slug},
                                             follow_redirects=True)

            # and put a new category inside it
            cat_title = u'Bolus'
            cat_slug = slugify(cat_title)
            response = self.test_client.post('/tree/{}/edit/{}'.format(working_branch_name, categories_slug),
                                             data={'action': 'create', 'create_what': view_functions.CATEGORY_LAYOUT, 'request_path': cat_title},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # get the hexsha
            hexsha = self.clone1.commit().hexsha

            # get the modify page and verify that the form renders with the correct values
            cat_path = join(categories_slug, cat_slug, u'index.{}'.format(view_functions.CONTENT_FILE_EXTENSION))
            response = self.test_client.get('/tree/{}/modify/{}'.format(working_branch_name, view_functions.strip_index_file(cat_path)), follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(PATTERN_FORM_CATEGORY_TITLE.format(title=cat_title) in response.data)
            self.assertTrue(PATTERN_FORM_CATEGORY_DESCRIPTION.format(description=u'') in response.data)

            # now save a new title and description for the category
            new_cat_title = u'Caecum'
            cat_description = u'An intraperitoneal pouch, that is considered to be the beginning of the large intestine.'
            response = self.test_client.post('/tree/{}/modify/{}'.format(working_branch_name, cat_path),
                                             data={'layout': view_functions.CATEGORY_LAYOUT, 'hexsha': hexsha, 'url-slug': u'{}/{}/'.format(categories_slug, cat_slug),
                                                   'en-title': new_cat_title, 'en-description': cat_description, 'order': u'0', 'save': u''},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # check the returned HTML for the description and title values (format will change as pages are designed)
            response_data = sub('&#39;', '\'', response.data.decode('utf-8'))
            self.assertTrue(PATTERN_FLASH_SAVED_CATEGORY.format(title=new_cat_title) in response_data)
            self.assertTrue(PATTERN_FORM_CATEGORY_DESCRIPTION.format(description=cat_description) in response_data)
            self.assertTrue(PATTERN_FORM_CATEGORY_TITLE.format(title=new_cat_title) in response_data)

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # a directory was created
            dir_location = join(self.clone1.working_dir, categories_slug, cat_slug)
            idx_location = u'{}/index.{}'.format(dir_location, view_functions.CONTENT_FILE_EXTENSION)
            self.assertTrue(exists(dir_location) and isdir(dir_location))
            # an index page was created inside
            self.assertTrue(exists(idx_location))
            # the directory and index page pass the category test
            self.assertTrue(view_functions.is_category_dir(dir_location))
            # the title and description saved in the index front matter is the same text that was used to create the category
            self.assertEqual(view_functions.get_value_from_front_matter('title', idx_location), new_cat_title)
            self.assertEqual(view_functions.get_value_from_front_matter('description', idx_location), cat_description)

            # the title saved in the index front matter is displayed on the article list page
            response = self.test_client.get('/tree/{}/edit/{}'.format(working_branch_name, categories_slug), follow_redirects=True)
            self.assertTrue(PATTERN_FILE_COMMENT.format(**{"file_name": cat_slug, "file_title": new_cat_title, "file_type": view_functions.CATEGORY_LAYOUT}) in response.data)

    # in TestApp
    def test_delete_category(self):
        ''' A category can be deleted
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            task_description = u'clasp with front legs and draw up the hind end'
            task_beneficiary = u'geometridae'

            working_branch = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
            self.assertTrue(working_branch.name in self.clone1.branches)
            self.assertTrue(working_branch.name in self.origin.branches)
            working_branch_name = working_branch.name
            working_branch.checkout()

            # create a categories directory
            categories_slug = u'categories'
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch_name),
                                             data={'action': 'create', 'create_what': view_functions.CATEGORY_LAYOUT, 'request_path': categories_slug},
                                             follow_redirects=True)

            # and put a new category inside it
            cat_title = u'Soybean Looper'
            cat_slug = slugify(cat_title)
            response = self.test_client.post('/tree/{}/edit/{}'.format(working_branch_name, categories_slug),
                                             data={'action': 'create', 'create_what': view_functions.CATEGORY_LAYOUT, 'request_path': cat_title},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # get the hexsha
            hexsha = self.clone1.commit().hexsha

            # now delete the category
            cat_description = u''
            url_slug = u'{}/{}/'.format(categories_slug, cat_slug)
            response = self.test_client.post('/tree/{}/modify/{}'.format(working_branch_name, url_slug.rstrip('/')),
                                             data={'layout': view_functions.CATEGORY_LAYOUT, 'hexsha': hexsha, 'url-slug': url_slug,
                                                   'en-title': cat_title, 'en-description': cat_description, 'order': u'0', 'delete': u''},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # check the returned HTML for the description and title values (format will change as pages are designed)
            response_data = sub('&#34;', '"', response.data.decode('utf-8'))
            self.assertTrue(u'<li class="flash flash--notice">The "{}" category was deleted</li>'.format(cat_title) in response_data)

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # the directory was deleted
            dir_location = join(self.clone1.working_dir, categories_slug, cat_slug)
            self.assertFalse(exists(dir_location) and isdir(dir_location))

            # the title is not displayed on the article list page
            response = self.test_client.get('/tree/{}/edit/{}'.format(working_branch_name, categories_slug), follow_redirects=True)
            self.assertFalse(PATTERN_FILE_COMMENT.format(**{"file_name": cat_slug, "file_title": cat_title, "file_type": view_functions.CATEGORY_LAYOUT}) in response.data)

    # in TestApp
    def test_set_and_retrieve_order_and_description(self):
        ''' Order and description can be set to and retrieved from an article's or category's front matter.
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            task_description = u'regurgitate partially digested worms and grubs'
            task_beneficiary = u'baby birds'

            working_branch = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
            self.assertTrue(working_branch.name in self.clone1.branches)
            self.assertTrue(working_branch.name in self.origin.branches)
            working_branch_name = working_branch.name
            working_branch.checkout()

            # create a categories directory
            categories_slug = u'categories'
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch_name),
                                             data={'action': 'create', 'create_what': view_functions.CATEGORY_LAYOUT, 'request_path': categories_slug},
                                             follow_redirects=True)

            # and put a new category inside it
            cat_title = u'Small Intestine'
            cat_slug = slugify(cat_title)
            response = self.test_client.post('/tree/{}/edit/{}'.format(working_branch_name, categories_slug),
                                             data={'action': 'create', 'create_what': view_functions.CATEGORY_LAYOUT, 'request_path': cat_title},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # get the hexsha
            hexsha = self.clone1.commit().hexsha

            # now save some values into the category's index page's front matter
            new_cat_title = u'The Small Intestine'
            cat_description = u'The part of the GI tract following the stomach and followed by the large intestine where much of the digestion and absorption of food takes place.'
            cat_order = 3
            cat_path = join(categories_slug, cat_slug, u'index.{}'.format(view_functions.CONTENT_FILE_EXTENSION))
            response = self.test_client.post('/tree/{}/save/{}'.format(working_branch_name, cat_path),
                                             data={'layout': view_functions.CATEGORY_LAYOUT, 'hexsha': hexsha,
                                                   'en-title': new_cat_title, 'en-description': cat_description, 'order': cat_order},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # check the returned HTML for the description and order values (format will change as pages are designed)
            self.assertTrue(u'<input name="en-description" type="hidden" value="{}" />'.format(cat_description) in response.data)
            self.assertTrue(u'<input name="order" type="hidden" value="{}" />'.format(cat_order) in response.data)

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # a directory was created
            dir_location = join(self.clone1.working_dir, categories_slug, cat_slug)
            idx_location = u'{}/index.{}'.format(dir_location, view_functions.CONTENT_FILE_EXTENSION)
            self.assertTrue(exists(dir_location) and isdir(dir_location))
            # an index page was created inside
            self.assertTrue(exists(idx_location))
            # the directory and index page pass the category test
            self.assertTrue(view_functions.is_category_dir(dir_location))
            # the title saved in the index front matter is the same text that was used to create the category
            self.assertEqual(view_functions.get_value_from_front_matter('title', idx_location), new_cat_title)

            # check order and description
            self.assertEqual(view_functions.get_value_from_front_matter('order', idx_location), cat_order)
            self.assertEqual(view_functions.get_value_from_front_matter('description', idx_location), cat_description)

            # the title saved in the index front matter is displayed on the article list page
            response = self.test_client.get('/tree/{}/edit/{}'.format(working_branch_name, categories_slug), follow_redirects=True)
            self.assertTrue(PATTERN_FILE_COMMENT.format(**{"file_name": cat_slug, "file_title": new_cat_title, "file_type": view_functions.CATEGORY_LAYOUT}) in response.data)

    # in TestApp
    def test_create_many_categories_with_slash_separated_input(self):
        ''' Entering a slash-separated string into the new article or category
            field will create category folders where folders don't already exist
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            task_description = u'put the needle on the record'
            task_beneficiary = u'all the people in the house'

            working_branch = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
            self.assertTrue(working_branch.name in self.clone1.branches)
            self.assertTrue(working_branch.name in self.origin.branches)
            working_branch_name = working_branch.name
            working_branch.checkout()

            # create multiple new categories
            page_slug = u'when/the/drum/beat'
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch_name),
                                             data={'action': 'create', 'create_what': view_functions.CATEGORY_LAYOUT, 'request_path': page_slug},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # category directories were created
            dirs = page_slug.split('/')
            for i in range(len(dirs)):
                dir_location = join(self.clone1.working_dir, u'/'.join(dirs[:i + 1]))
                # dir_location = join(self.clone1.working_dir, u'drum/beat/goes/like')
                idx_location = u'{}/index.{}'.format(dir_location, view_functions.CONTENT_FILE_EXTENSION)
                self.assertTrue(exists(dir_location) and isdir(dir_location))
                # an index page was created inside
                self.assertTrue(exists(idx_location))
                # the directory and index page pass the category test
                self.assertTrue(view_functions.is_category_dir(dir_location))

            # now create a new page
            page_slug = u'goes/like/this'
            page_path = u'{}/index.{}'.format(page_slug, view_functions.CONTENT_FILE_EXTENSION)
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch_name),
                                             data={'action': 'create', 'create_what': view_functions.ARTICLE_LAYOUT, 'request_path': page_slug},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(page_path in response.data)

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # category directories were created
            dirs = page_slug.split('/')
            for i in range(len(dirs)):
                dir_location = join(self.clone1.working_dir, u'/'.join(dirs[:i + 1]))
                # dir_location = join(self.clone1.working_dir, u'drum/beat/goes/like')
                idx_location = u'{}/index.{}'.format(dir_location, view_functions.CONTENT_FILE_EXTENSION)
                self.assertTrue(exists(dir_location) and isdir(dir_location))
                # an index page was created inside
                self.assertTrue(exists(idx_location))
                if i < len(dirs) - 1:
                    # the directory and index page pass the category test
                    self.assertTrue(view_functions.is_category_dir(dir_location))
                else:
                    # the directory and index page pass the article test
                    self.assertTrue(view_functions.is_article_dir(dir_location))

    # in TestApp
    def test_column_navigation_structure(self):
        ''' The column navigation structure matches the structure of the site.
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            task_description = u'force a clam shell open'
            task_beneficiary = u'starfish'

            working_branch = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
            self.assertTrue(working_branch.name in self.clone1.branches)
            self.assertTrue(working_branch.name in self.origin.branches)
            working_branch_name = working_branch.name
            working_branch.checkout()

            # create some nested categories
            slug_hello = u'hello'
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch_name),
                                             data={'action': 'create', 'create_what': view_functions.CATEGORY_LAYOUT, 'request_path': slug_hello},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            slug_world = u'world'
            response = self.test_client.post('/tree/{}/edit/{}'.format(working_branch_name, slug_hello),
                                             data={'action': 'create', 'create_what': view_functions.CATEGORY_LAYOUT, 'request_path': slug_world},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            slug_how = u'how'
            response = self.test_client.post('/tree/{}/edit/{}'.format(working_branch_name, sep.join([slug_hello, slug_world])),
                                             data={'action': 'create', 'create_what': view_functions.CATEGORY_LAYOUT, 'request_path': slug_how},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            slug_are = u'are'
            response = self.test_client.post('/tree/{}/edit/{}'.format(working_branch_name, sep.join([slug_hello, slug_world, slug_how])),
                                             data={'action': 'create', 'create_what': view_functions.CATEGORY_LAYOUT, 'request_path': slug_are},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # get the columns
            dir_columns = view_functions.make_directory_columns(self.clone1, working_branch_name, sep.join([slug_hello, slug_world, slug_how, slug_are]))

            # test that the contents match our expectations
            self.assertEqual(len(dir_columns), 4)
            self.assertEqual(len(dir_columns[0]['files']), 5)
            expected = {'hello': u'category', 'index.md': u'file', 'other': u'folder', 'other.md': u'file', 'sub': u'folder'}
            for item in dir_columns[0]['files']:
                self.assertTrue(item['name'] in expected)
                self.assertTrue(expected[item['name']] == item['display_type'])
            self.assertTrue(dir_columns[1]['files'][0]['name'] == slug_world)
            self.assertTrue(dir_columns[2]['files'][0]['name'] == slug_how)
            self.assertTrue(dir_columns[3]['files'][0]['name'] == slug_are)

    # in TestApp
    def test_activity_overview_page_is_accurate(self):
        ''' The activity history page accurately displays the activity history
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            task_description = u'deposit eggs in a syconium'
            task_beneficiary = u'fig wasp larvae'

            working_branch = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
            self.assertTrue(working_branch.name in self.clone1.branches)
            self.assertTrue(working_branch.name in self.origin.branches)
            working_branch_name = working_branch.name
            working_branch.checkout()

            title_fig_zh = u'无花果'
            slug_fig_zh = u'wu-hua-guo'
            title_syconium = u'Syconium'
            slug_syconium = u'syconium'
            title_ostiole = u'Ostiole'
            title_fig_en = u'Fig'
            title_fig_bn = u'Dumur'
            create_details = [
                (u'', title_fig_zh, view_functions.CATEGORY_LAYOUT),
                (slug_fig_zh, title_syconium, view_functions.CATEGORY_LAYOUT),
                (u'{}/{}'.format(slug_fig_zh, slug_syconium), title_ostiole, view_functions.ARTICLE_LAYOUT),
                (u'', title_fig_en, view_functions.CATEGORY_LAYOUT),
                (u'', title_fig_bn, view_functions.CATEGORY_LAYOUT)
            ]

            for detail in create_details:
                response = self.test_client.post('/tree/{}/edit/{}'.format(working_branch_name, detail[0]),
                                                 data={'action': 'create', 'create_what': detail[2], 'request_path': detail[1]},
                                                 follow_redirects=True)
                self.assertEqual(response.status_code, 200)

            # add a comment
            comment_text = u'The flowers provide a safe haven and nourishment for the next generation of wasps. ᙙᙖ'
            response = self.test_client.post('/tree/{}/'.format(working_branch_name),
                                             data={'comment': 'Comment', 'comment_text': comment_text},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            # delete a directory
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch_name),
                                             data={'action': 'delete', 'request_path': slug_fig_zh},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)

            # get the activity history page
            response = self.test_client.get('/tree/{}/'.format(working_branch_name), follow_redirects=True)
            # TODO: for some reason (encoding?) my double-quotes are being replaced by &#34; in the returned HTML
            response_data = sub('&#34;', '"', response.data.decode('utf-8'))
            # make sure everything we did above is shown on the activity page
            self.assertTrue(PATTERN_TEMPLATE_COMMENT.format('activity-overview') in response_data)
            self.assertTrue(PATTERN_OVERVIEW_ACTIVITY_STARTED.format(**{"activity_name": task_description, "author_email": fake_author_email}) in response_data)
            self.assertTrue(PATTERN_OVERVIEW_COMMENT_BODY.format(**{"comment_body": comment_text}) in response_data)
            self.assertTrue(PATTERN_OVERVIEW_ITEM_DELETED.format(**{"deleted_name": title_fig_zh, "deleted_type": view_functions.CATEGORY_LAYOUT, "deleted_also": u'(containing 1 category and 1 article) ', "author_email": fake_author_email}) in response_data)
            for detail in create_details:
                self.assertTrue(PATTERN_OVERVIEW_ITEM_CREATED.format(**{"created_name": detail[1], "created_type": detail[2], "author_email": fake_author_email}), response_data)

    # in TestApp
    def test_activity_history_summary_accuracy(self):
        ''' The summary of an activity's history is displayed as expected.
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.test_client, self)
                erica.sign_in(email='erica@example.com')

            # Start a new task
            erica.start_task(description=u'Parasitize with Ichneumonidae', beneficiary=u'Moth Larvae')
            # Get the branch name
            branch_name = erica.get_branch_name()

            # Load the activity overview page
            erica.follow_link(href='/tree/{}'.format(branch_name))
            # there shouldn't be a summary yet
            summary_div = erica.soup.find("div", class_="activity-summary")
            self.assertIsNone(summary_div)

            # Load the "other" folder
            erica.open_link(url='/tree/{}/edit/other/'.format(branch_name))

            # Create a category, sub-category, article
            category_name = u'Antennae Segments'
            subcategory_name = u'Short Ovipositors'
            article_names = [u'Inject Eggs Directly Into a Host Body', u'A Technique Of Celestial Navigation Called Transverse Orientation']
            erica.add_category(category_name=category_name)
            erica.add_subcategory(subcategory_name=subcategory_name)
            subcategory_path = erica.path
            erica.add_article(article_name=article_names[0])

            # edit the article
            erica.edit_article(title_str=article_names[0], body_str=u'Inject venom along with the egg')
            # create another article and delete it
            erica.open_link(subcategory_path)
            erica.add_article(article_name=article_names[1])
            erica.open_link(subcategory_path)
            erica.delete_article(article_names[1])

            # Load the activity overview page
            erica.open_link(url='/tree/{}/'.format(branch_name))
            # there is a summary
            summary_div = erica.soup.find("div", class_="activity-summary")
            self.assertIsNotNone(summary_div)
            # it's right about what's changed
            self.assertIsNotNone(summary_div.find(lambda tag: bool(tag.name == 'a' and '2 articles and 2 categories' in tag.text)))
            # grab all the table rows
            check_rows = summary_div.find_all('tr')

            # make sure they match what we did above
            category_row = check_rows.pop()
            category_cells = category_row.find_all('td')
            self.assertIsNotNone(category_cells[0].find('a'))
            self.assertEqual(category_cells[0].text, category_name)
            self.assertEqual(category_cells[1].text, u'Category')
            self.assertEqual(category_cells[2].text, u'Created')

            subcategory_row = check_rows.pop()
            subcategory_cells = subcategory_row.find_all('td')
            self.assertIsNotNone(subcategory_cells[0].find('a'))
            self.assertEqual(subcategory_cells[0].text, subcategory_name)
            self.assertEqual(subcategory_cells[1].text, u'Category')
            self.assertEqual(subcategory_cells[2].text, u'Created')

            article_1_row = check_rows.pop()
            article_1_cells = article_1_row.find_all('td')
            self.assertIsNotNone(article_1_cells[0].find('a'))
            self.assertEqual(article_1_cells[0].text, article_names[0])
            self.assertEqual(article_1_cells[1].text, u'Article')
            self.assertEqual(article_1_cells[2].text, u'Created, Edited')

            article_2_row = check_rows.pop()
            article_2_cells = article_2_row.find_all('td')
            self.assertIsNone(article_2_cells[0].find('a'))
            self.assertEqual(article_2_cells[0].text, article_names[1])
            self.assertEqual(article_2_cells[1].text, u'Article')
            self.assertEqual(article_2_cells[2].text, u'Created, Deleted')

            # only the header row's left
            self.assertEqual(len(check_rows), 1)

    # in TestApp
    def test_create_page_creates_directory_containing_index(self):
        ''' Creating a new page creates a directory with an editable index file inside.
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            task_description = u'filter plankton from sea water'
            task_beneficiary = u'humpback whales'

            working_branch = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
            self.assertTrue(working_branch.name in self.clone1.branches)
            self.assertTrue(working_branch.name in self.origin.branches)
            working_branch_name = working_branch.name
            working_branch.checkout()

            # create a new page
            page_slug = u'hello'
            page_path = u'{}/index.{}'.format(page_slug, view_functions.CONTENT_FILE_EXTENSION)
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch_name),
                                             data={'action': 'create', 'create_what': view_functions.ARTICLE_LAYOUT, 'request_path': page_slug},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(page_path in response.data)

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # a directory was created
            dir_location = join(self.clone1.working_dir, page_slug)
            idx_location = u'{}/index.{}'.format(dir_location, view_functions.CONTENT_FILE_EXTENSION)
            self.assertTrue(exists(dir_location) and isdir(dir_location))
            # an index page was created inside
            self.assertTrue(exists(idx_location))
            # the directory and index page pass the article test
            self.assertTrue(view_functions.is_article_dir(dir_location))

    # in TestApp
    def test_can_rename_editable_directories(self):
        ''' Can rename an editable directory.
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            task_description = u'filter plankton from sea water'
            task_beneficiary = u'humpback whales'

            working_branch = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
            self.assertTrue(working_branch.name in self.clone1.branches)
            self.assertTrue(working_branch.name in self.origin.branches)
            working_branch_name = working_branch.name
            working_branch.checkout()

            # create a new page
            page_slug = u'hello'
            page_path = u'{}/index.{}'.format(page_slug, view_functions.CONTENT_FILE_EXTENSION)
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch_name),
                                             data={'action': 'create', 'create_what': view_functions.ARTICLE_LAYOUT, 'request_path': page_slug},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(page_path in response.data)
            hexsha = search(r'<input name="hexsha" value="(\w+)"', response.data).group(1)

            # now save the file with new content
            new_page_slug = u'goodbye'
            new_page_path = u'{}/index.{}'.format(new_page_slug, view_functions.CONTENT_FILE_EXTENSION)
            response = self.test_client.post('/tree/{}/save/{}'.format(working_branch_name, page_path),
                                             data={'layout': view_functions.ARTICLE_LAYOUT, 'hexsha': hexsha,
                                                   'en-title': u'',
                                                   'en-body': u'',
                                                   'fr-title': u'', 'fr-body': u'',
                                                   'url-slug': u'{}'.format(new_page_slug)},
                                             follow_redirects=True)

            self.assertEqual(response.status_code, 200)
            self.assertTrue(new_page_path in response.data)

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # the old directory is gone
            old_dir_location = join(self.clone1.working_dir, page_slug)
            self.assertFalse(exists(old_dir_location))

            # the new directory exists and is properly structured
            new_dir_location = join(self.clone1.working_dir, new_page_slug)
            self.assertTrue(exists(new_dir_location) and isdir(new_dir_location))
            # an index page is inside
            idx_location = u'{}/index.{}'.format(new_dir_location, view_functions.CONTENT_FILE_EXTENSION)
            self.assertTrue(exists(idx_location))
            # the directory and index page pass the editable test
            self.assertTrue(view_functions.is_article_dir(new_dir_location))

    # in TestApp
    def test_cannot_move_a_directory_inside_iteslf(self):
        ''' Can't rename an editable directory in a way which moves it inside itself
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            task_description = u'filter plankton from sea water'
            task_beneficiary = u'humpback whales'

            working_branch = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
            self.assertTrue(working_branch.name in self.clone1.branches)
            self.assertTrue(working_branch.name in self.origin.branches)
            working_branch_name = working_branch.name
            working_branch.checkout()

            # create a new page
            page_slug = u'hello'
            page_path = u'{}/index.{}'.format(page_slug, view_functions.CONTENT_FILE_EXTENSION)
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch_name),
                                             data={'action': 'create', 'create_what': view_functions.ARTICLE_LAYOUT, 'request_path': page_slug},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(page_path in response.data)
            hexsha = search(r'<input name="hexsha" value="(\w+)"', response.data).group(1)

            # now save the file with new content
            new_page_slug = u'hello/is/better/than/goodbye'
            new_page_path = u'{}/index.{}'.format(new_page_slug, view_functions.CONTENT_FILE_EXTENSION)
            response = self.test_client.post('/tree/{}/save/{}'.format(working_branch_name, page_path),
                                             data={'layout': view_functions.ARTICLE_LAYOUT, 'hexsha': hexsha,
                                                   'en-title': u'',
                                                   'en-body': u'',
                                                   'fr-title': u'', 'fr-body': u'',
                                                   'url-slug': u'{}'.format(new_page_slug)},
                                             follow_redirects=True)

            self.assertEqual(response.status_code, 200)
            # the new page shouldn't have been created
            self.assertFalse(new_page_path in response.data)
            # there shoudld be a flashed error message
            self.assertTrue(u'I cannot move a directory inside itself!' in response.data)

            # pull the changes
            self.clone1.git.pull('origin', working_branch_name)

            # the old directory is not gone
            old_dir_location = join(self.clone1.working_dir, page_slug)
            self.assertTrue(exists(old_dir_location))

            # the new directory doesn't exist
            new_dir_location = join(self.clone1.working_dir, new_page_slug)
            self.assertFalse(exists(new_dir_location) and isdir(new_dir_location))

    # in TestApp
    def test_editable_directories_are_shown_as_articles(self):
        ''' Editable directories (directories containing only an editable index file) are displayed as articles.
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            task_description = u'filter plankton from sea water'
            task_beneficiary = u'humpback whales'

            working_branch = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
            self.assertTrue(working_branch.name in self.clone1.branches)
            self.assertTrue(working_branch.name in self.origin.branches)
            working_branch_name = working_branch.name
            working_branch.checkout()

            # create a new page
            page_slug = u'hello'
            page_path = u'{}/index.{}'.format(page_slug, view_functions.CONTENT_FILE_EXTENSION)
            response = self.test_client.post('/tree/{}/edit/'.format(working_branch_name),
                                             data={'action': 'create', 'create_what': view_functions.ARTICLE_LAYOUT, 'request_path': page_slug},
                                             follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(page_path in response.data)

            # load the index page
            response = self.test_client.get('/tree/{}/edit/'.format(working_branch_name), follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            # verify that the new folder is represented as a file in the HTML
            self.assertTrue(PATTERN_BRANCH_COMMENT.format(working_branch_name) in response.data)
            self.assertTrue(PATTERN_FILE_COMMENT.format(**{"file_name": page_slug, "file_title": page_slug, "file_type": view_functions.ARTICLE_LAYOUT}) in response.data)

    # in TestApp
    def test_page_not_found_error(self):
        ''' A 404 page is generated when we get an address that doesn't exist
        '''
        fake_author_email = u'erica@example.com'
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_author_email})

        with HTTMock(self.auth_csv_example_allowed):
            # start a new branch via the http interface
            # invokes view_functions/get_repo which creates a clone
            task_description = u'drink quinine'
            task_beneficiary = u'mosquitos'

            working_branch = repo_functions.get_start_branch(self.clone1, 'master', task_description, task_beneficiary, fake_author_email)
            self.assertTrue(working_branch.name in self.clone1.branches)
            self.assertTrue(working_branch.name in self.origin.branches)
            working_branch_name = working_branch.name
            working_branch.checkout()

            # get a non-existent page
            response = self.test_client.get('tree/{}/malaria'.format(working_branch_name), follow_redirects=True)
            self.assertTrue(PATTERN_TEMPLATE_COMMENT.format('error-404') in response.data)
            # these values are set in setUp() above
            self.assertTrue(u'support@example.com' in response.data)
            self.assertTrue(u'(123) 456-7890' in response.data)

    # in TestApp
    def test_internal_server_error(self):
        ''' A 500 page is generated when we provoke a server error
        '''
        with HTTMock(self.mock_persona_verify_erica):
            response = self.test_client.post('/sign-in', data={'email': 'erica@example.com'})

        with HTTMock(self.mock_internal_server_error):
            response = self.test_client.get('/', follow_redirects=True)
            self.assertTrue(PATTERN_TEMPLATE_COMMENT.format('error-500') in response.data)
            # these values are set in setUp() above
            self.assertTrue(u'support@example.com' in response.data)
            self.assertTrue(u'(123) 456-7890' in response.data)

    # in TestApp
    def test_exception_error(self):
        ''' A 500 page is generated when we provoke an uncaught exception
        '''
        with HTTMock(self.mock_persona_verify_erica):
            response = self.test_client.post('/sign-in', data={'email': 'erica@example.com'})

        with HTTMock(self.mock_exception):
            response = self.test_client.get('/', follow_redirects=True)
            self.assertTrue(PATTERN_TEMPLATE_COMMENT.format('error-500') in response.data)
            # these values are set in setUp() above
            self.assertTrue(u'support@example.com' in response.data)
            self.assertTrue(u'(123) 456-7890' in response.data)

    # in TestApp
    def test_merge_conflict_error(self):
        ''' We get a merge conflict error page when there's a merge conflict
        '''
        fake_task_description_1 = u'do things'
        fake_task_beneficiary_1 = u'somebody else'
        fake_task_description_2 = u'do other things'
        fake_task_beneficiary_2 = u'somebody even else'
        fake_email_1 = u'erica@example.com'
        fake_email_2 = u'frances@example.com'
        fake_page_slug = u'hello'
        fake_page_path = u'{}/index.{}'.format(fake_page_slug, view_functions.CONTENT_FILE_EXTENSION)
        fake_page_content_1 = u'Hello world.'
        fake_page_content_2 = u'Hello moon.'
        #
        #
        # Log in as person 1
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_email_1})

        with HTTMock(self.auth_csv_example_allowed):
            # create a new branch
            response = self.test_client.post('/start', data={'task_description': fake_task_description_1, 'task_beneficiary': fake_task_beneficiary_1}, follow_redirects=True)
            # extract the generated branch name from the returned HTML
            generated_branch_search = search(r'<!-- branch: (.{{{}}}) -->'.format(repo_functions.BRANCH_NAME_LENGTH), response.data)
            self.assertIsNotNone(generated_branch_search)
            try:
                generated_branch_name_1 = generated_branch_search.group(1)
            except AttributeError:
                raise Exception('No match for generated branch name.')

        with HTTMock(self.mock_google_analytics):
            # create a new file
            response = self.test_client.post('/tree/{}/edit/'.format(generated_branch_name_1),
                                             data={'action': 'create', 'create_what': view_functions.ARTICLE_LAYOUT, 'request_path': fake_page_slug},
                                             follow_redirects=True)
            # get the edit page for the new file and extract the hexsha value
            response = self.test_client.get('/tree/{}/edit/{}'.format(generated_branch_name_1, fake_page_path))
            hexsha = search(r'<input name="hexsha" value="(\w+)"', response.data).group(1)
            # now save the file with new content
            response = self.test_client.post('/tree/{}/save/{}'.format(generated_branch_name_1, fake_page_path),
                                             data={'layout': view_functions.ARTICLE_LAYOUT, 'hexsha': hexsha,
                                                   'en-title': 'Greetings',
                                                   'en-body': u'{}\n'.format(fake_page_content_1),
                                                   'url-slug': u'{}/index'.format(fake_page_slug)},
                                             follow_redirects=True)

        # Request feedback on person 1's change
        with HTTMock(self.auth_csv_example_allowed):
            response = self.test_client.post('/tree/{}/'.format(generated_branch_name_1), data={'comment_text': u'', 'request_feedback': u'Request Feedback'}, follow_redirects=True)

        #
        #
        # Log in as person 2
        with HTTMock(self.mock_persona_verify_frances):
            self.test_client.post('/sign-in', data={'email': fake_email_2})

        with HTTMock(self.auth_csv_example_allowed):
            # create a new branch
            response = self.test_client.post('/start', data={'task_description': fake_task_description_2, 'task_beneficiary': fake_task_beneficiary_2}, follow_redirects=True)
            # extract the generated branch name from the returned HTML
            generated_branch_search = search(r'<!-- branch: (.{{{}}}) -->'.format(repo_functions.BRANCH_NAME_LENGTH), response.data)
            try:
                generated_branch_name_2 = generated_branch_search.group(1)
            except AttributeError:
                raise Exception('No match for generated branch name.')

        with HTTMock(self.mock_google_analytics):
            # create a new file
            response = self.test_client.post('/tree/{}/edit/'.format(generated_branch_name_2),
                                             data={'action': 'create', 'create_what': view_functions.ARTICLE_LAYOUT, 'request_path': fake_page_slug},
                                             follow_redirects=True)

            # get the edit page for the new file and extract the hexsha value
            response = self.test_client.get('/tree/{}/edit/{}'.format(generated_branch_name_2, fake_page_path))
            hexsha = search(r'<input name="hexsha" value="(\w+)"', response.data).group(1)
            # now save the file with new content
            fake_new_title = u'Bloople'
            response = self.test_client.post('/tree/{}/save/{}'.format(generated_branch_name_2, fake_page_path),
                                             data={'layout': view_functions.ARTICLE_LAYOUT, 'hexsha': hexsha,
                                                   'en-title': fake_new_title,
                                                   'en-body': u'{}\n'.format(fake_page_content_2),
                                                   'url-slug': u'{}/index'.format(fake_page_slug)},
                                             follow_redirects=True)

        # Request feedback on person 2's change
        with HTTMock(self.auth_csv_example_allowed):
            response = self.test_client.post('/tree/{}/'.format(generated_branch_name_2), data={'comment_text': u'', 'request_feedback': u'Request Feedback'}, follow_redirects=True)

        # Endorse person 1's change
        with HTTMock(self.auth_csv_example_allowed):
            response = self.test_client.post('/tree/{}/'.format(generated_branch_name_1), data={'comment_text': u'', 'endorse_edits': 'Looks Good!'}, follow_redirects=True)

        # And publish person 1's change!
        with HTTMock(self.auth_csv_example_allowed):
            response = self.test_client.post('/tree/{}/'.format(generated_branch_name_1), data={'comment_text': u'', 'merge': 'Publish'}, follow_redirects=True)

        #
        #
        # Log in as person 1
        with HTTMock(self.mock_persona_verify_erica):
            self.test_client.post('/sign-in', data={'email': fake_email_1})

        # Endorse person 2's change
        with HTTMock(self.auth_csv_example_allowed):
            response = self.test_client.post('/tree/{}/'.format(generated_branch_name_2), data={'comment_text': u'', 'endorse_edits': 'Looks Good!'}, follow_redirects=True)

        # And publish person 2's change!
        with HTTMock(self.auth_csv_example_allowed):
            response = self.test_client.post('/tree/{}/'.format(generated_branch_name_2), data={'comment_text': u'', 'merge': 'Publish'}, follow_redirects=True)

        # verify that we got an error page about the merge conflict
        self.assertTrue(PATTERN_TEMPLATE_COMMENT.format('error-500') in response.data)
        self.assertTrue(u'MergeConflict' in response.data)
        self.assertTrue(u'{}/index.{}'.format(fake_page_slug, view_functions.CONTENT_FILE_EXTENSION) in response.data)

        self.assertTrue(u'<td><a href="/tree/{}/edit/{}/">{}</a></td>'.format(generated_branch_name_2, fake_page_slug, fake_new_title))
        self.assertTrue(u'<td>Article</td>' in response.data)
        self.assertTrue(u'<td>Edited</td>' in response.data)

        # these values are set in setUp() above
        self.assertTrue(u'support@example.com' in response.data)
        self.assertTrue(u'(123) 456-7890' in response.data)

    # in TestApp
    def test_redirect_into_solo_folder(self):
        ''' Loading a folder with a sole non-article or -category directory in it redirects to the contents of that directory.
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in('erica@example.com')

            # Start a new task
            erica.start_task(description=u'Be Shot Hundreds Of Feet Into The Air', beneficiary=u'A Geyser Of Highly Pressurized Water')
            # Get the branch name
            branch_name = erica.get_branch_name()

            # create a directory containing only another directory
            repo = view_functions.get_repo(repo_path=self.app.config['REPO_PATH'], work_path=self.app.config['WORK_PATH'], email='erica@example.com')
            testing_slug = u'testing'
            categories_slug = u'categories'
            mkdir(join(repo.working_dir, testing_slug))
            mkdir(join(repo.working_dir, testing_slug, categories_slug))

            # open the top level directory
            erica.open_link(url='/tree/{}/edit/'.format(branch_name))
            # enter the 'testing' directory
            erica.follow_link(href='/tree/{}/edit/{}'.format(branch_name, testing_slug))
            # we should've automatically been redirected into the 'categories' directory
            self.assertEqual(erica.path, '/tree/{}/edit/{}/'.format(branch_name, join(testing_slug, categories_slug)))

class TestPublishApp (TestCase):

    def setUp(self):
        self.old_tempdir, tempfile.tempdir = tempfile.tempdir, mkdtemp(prefix='chime-TestPublishApp-')

        self.work_path = mkdtemp(prefix='chime-publish-app-')

        app_args = {}

        self.app = publish.create_app(app_args)
        self.client = self.app.test_client()

    def tearDown(self):
        rmtree(tempfile.tempdir)
        tempfile.tempdir = self.old_tempdir

    def mock_github_request(self, url, request):
        '''
        '''
        _, host, path, _, _, _ = urlparse(url.geturl())

        if (host, path) == ('github.com', '/chimecms/chime-starter/archive/93250f1308daef66c5809fe87fc242d092e61db7.zip'):
            return response(302, '', headers={'Location': 'https://codeload.github.com/chimecms/chime-starter/tar.gz/93250f1308daef66c5809fe87fc242d092e61db7'})

        if (host, path) == ('codeload.github.com', '/chimecms/chime-starter/tar.gz/93250f1308daef66c5809fe87fc242d092e61db7'):
            with open(join(dirname(__file__), '93250f1308daef66c5809fe87fc242d092e61db7.zip')) as file:
                return response(200, file.read(), headers={'Content-Type': 'application/zip'})

        raise Exception('Unknown URL {}'.format(url.geturl()))

    # in TestPublishApp
    def test_webhook_post(self):
        ''' Check basic webhook flow.
        '''
        payload = '''
            {
              "head": "93250f1308daef66c5809fe87fc242d092e61db7",
              "ref": "refs/heads/master",
              "size": 1,
              "commits": [
                {
                  "sha": "93250f1308daef66c5809fe87fc242d092e61db7",
                  "message": "Clean up braces",
                  "author": {
                    "name": "Frances Berriman",
                    "email": "phae@example.com"
                  },
                  "url": "https://github.com/chimecms/chime-starter/commit/93250f1308daef66c5809fe87fc242d092e61db7",
                  "distinct": true
                }
              ]
            }
            '''

        with HTTMock(self.mock_github_request):
            response = self.client.post('/', data=payload)

        self.assertTrue(response.status_code in range(200, 299))

    # in TestPublishApp
    def test_load(self):
        from chime import publish
        ''' makes sure that the file loads properly
        '''
        self.assertIsNotNone(publish.logger)


class TestHttpdStuff (TestCase):
    def test_load(self):
        from chime import httpd
        ''' makes sure that the file loads properly
        '''
        self.assertIsNotNone(httpd.config)


if __name__ == '__main__':
    main()
