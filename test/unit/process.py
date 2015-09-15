# -- coding: utf-8 --
from __future__ import absolute_import

from unittest import main, TestCase

from tempfile import mkdtemp
from os.path import join, dirname, abspath
from shutil import rmtree, copytree
from re import sub
import random
import sys
from chime.repo_functions import ChimeRepo
from slugify import slugify
import logging
import tempfile
logging.disable(logging.CRITICAL)

repo_root = abspath(join(dirname(__file__), '..'))
sys.path.insert(0, repo_root)

from box.util.rotunicode import RotUnicode
from httmock import response, HTTMock
from mock import MagicMock
from bs4 import Comment

from chime import create_app, repo_functions, google_api_functions, view_functions

from unit.chime_test_client import ChimeTestClient

import codecs
codecs.register(RotUnicode.search_function)

# these patterns help us search the HTML of a response to determine if the expected page loaded
PATTERN_BRANCH_COMMENT = u'<!-- branch: {} -->'
PATTERN_AUTHOR_COMMENT = u'<!-- author: {} -->'
PATTERN_TASK_COMMENT = u'<!-- task: {} -->'
PATTERN_TEMPLATE_COMMENT = u'<!-- template name: {} -->'
PATTERN_FILE_COMMENT = u'<!-- file type: {file_type}, file name: {file_name}, file title: {file_title} -->'
PATTERN_OVERVIEW_ITEM_CREATED = u'<p>The "{created_name}" {created_type} was created by {author_email}.</p>'
PATTERN_OVERVIEW_ACTIVITY_STARTED = u'<p>The "{activity_name}" activity was started by {author_email}.</p>'
PATTERN_OVERVIEW_COMMENT_BODY = u'<div class="comment__body">{comment_body}</div>'
PATTERN_OVERVIEW_ITEM_DELETED = u'<p>The "{deleted_name}" {deleted_type} {deleted_also}was deleted by {author_email}.</p>'
PATTERN_FLASH_TASK_DELETED = u'You deleted the "{description}" activity!'

PATTERN_FLASH_SAVED_CATEGORY = u'<li class="flash flash--notice">Saved changes to the {title} topic! Remember to submit this change for feedback when you\'re ready to go live.</li>'
PATTERN_FLASH_CREATED_CATEGORY = u'Created a new topic named {title}! Remember to submit this change for feedback when you\'re ready to go live.'
PATTERN_FLASH_CREATED_ARTICLE = u'Created a new article named {title}! Remember to submit this change for feedback when you\'re ready to go live.'
PATTERN_FLASH_SAVED_ARTICLE = u'Saved changes to the {title} article! Remember to submit this change for feedback when you\'re ready to go live.'
PATTERN_FLASH_DELETED_ARTICLE = u'The "{title}" article was deleted! Remember to submit this change for feedback when you\'re ready to go live.'
PATTERN_FORM_CATEGORY_TITLE = u'<input name="en-title" type="text" value="{title}" class="directory-modify__name" placeholder="Crime Statistics and Maps">'
PATTERN_FORM_CATEGORY_DESCRIPTION = u'<textarea name="en-description" class="directory-modify__description" placeholder="Crime statistics and reports by district and map">{description}</textarea>'

# review stuff
PATTERN_REQUEST_FEEDBACK_BUTTON = u'<button class="toolbar__item button button--orange" type="submit" name="request_feedback">Request Feedback</button>'
PATTERN_UNREVIEWED_EDITS_LINK = u'<a href="/tree/{branch_name}/" class="toolbar__item button">Unreviewed Edits</a>'
PATTERN_ENDORSE_BUTTON = u'<button class="toolbar__item button button--green" type="submit" name="endorse_edits">Endorse Edits</button>'
PATTERN_FEEDBACK_REQUESTED_LINK = u'<a href="/tree/{branch_name}/" class="toolbar__item button">Feedback requested</a>'
PATTERN_PUBLISH_BUTTON = u'<button class="toolbar__item button button--blue" type="submit" name="merge">Publish</button>'
PATTERN_READY_TO_PUBLISH_LINK = u'<a href="/tree/{branch_name}/" class="toolbar__item button">Ready to publish</a>'

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

            # Start a new task
            erica.open_link('/')
            args = 'Diving for Dollars', 'Ninjas', 'Flipping Out', 'So Awesome'
            branch_name = erica.quick_activity_setup(*args)
            
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
    def test_editing_process_with_two_categories(self):
        ''' Check edit process with a user looking at activity from another user.
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in('erica@example.com')
            
            with HTTMock(self.mock_persona_verify_frances):
                frances = ChimeTestClient(self.app.test_client(), self)
                frances.sign_in('frances@example.com')
            
            # Erica starts a new task, "Diving for Dollars".
            erica.open_link('/')
            erica.start_task('Diving for Dollars')
            erica_branchname = erica.get_branch_name()
            
            # Erica creates a new category and asks for feedback.
            erica.follow_link('/tree/{}/edit/other/'.format(erica_branchname))
            erica.add_category('Dollars')
            erica.follow_link('/tree/{}'.format(erica_branchname))
            erica.request_feedback('Is this okay?')
            
            # Frances starts a new task, "Bobbing for Apples".
            frances.open_link('/')
            frances.start_task('Bobbing for Apples')
            frances_branchname = frances.get_branch_name()
            
            # Frances creates a new category.
            frances.follow_link('/tree/{}/edit/other/'.format(frances_branchname))
            frances.add_category('Apples')
            
            # Frances approves Erica's new work and publishes it.
            frances.open_link(erica.path)
            frances.leave_feedback('It is super-great.')
            frances.approve_activity()
            frances.publish_activity()
            
            # Erica should now expect to see her own new category.
            erica.open_link('/')
            erica.start_task('Canticle for Leibowitz')
            erica_branchname2 = erica.get_branch_name()
            erica.follow_link('/tree/{}/edit/other/'.format(erica_branchname2))
            self.assertIsNotNone(erica.soup.find(text='Dollars'), 'Should see first published category')
            
            # Frances should still not expect to see Erica's published category.
            frances.open_link('/tree/{}/edit/'.format(frances_branchname))
            frances.follow_link('/tree/{}/edit/other/'.format(frances_branchname))
            self.assertIsNone(frances.soup.find(text='Dollars'), 'Should not see first published category')

    # in TestProcess
    def test_editing_process_with_conflicting_edit(self):
        ''' Check edit process with a user attempting to change an activity with a conflict.
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in('erica@example.com')
            
            with HTTMock(self.mock_persona_verify_frances):
                frances = ChimeTestClient(self.app.test_client(), self)
                frances.sign_in('frances@example.com')

            # Start a new task
            frances.open_link('/')
            args = 'Bobbing for Apples', 'Ninjas', 'Flipping Out', 'So Awesome'
            f_branch_name = frances.quick_activity_setup(*args)
            f_article_path = frances.path

            # Start a new task
            erica.open_link('/')
            args = 'Diving for Dollars', 'Ninjas', 'Flipping Out', 'So Awesome'
            e_branch_name = erica.quick_activity_setup(*args)

            # Edit the new article.
            erica.edit_article(title_str='So, So Awesome', body_str='It was the best of times.')

            # Ask for feedback
            erica.follow_link(href='/tree/{}'.format(e_branch_name))
            erica.request_feedback(feedback_str='Is this okay?')

            #
            # Switch users and publish the article.
            #
            frances.open_link(url=erica.path)
            frances.leave_feedback(feedback_str='It is super-great.')
            frances.approve_activity()
            frances.publish_activity()
            
            #
            # Now introduce a conflicting change on the original activity,
            # and verify that the expected flash warning is displayed.
            #
            frances.open_link(f_article_path)
            frances.edit_article(title_str='So, So Awful', body_str='It was the worst of times.')
            self.assertIsNotNone(frances.soup.find(text=repo_functions.MERGE_CONFLICT_WARNING_FLASH_MESSAGE),
                                 'Should see a warning about the conflict above the article.')

            frances.follow_link(href='/tree/{}'.format(f_branch_name))
            self.assertIsNotNone(frances.soup.find(text=repo_functions.MERGE_CONFLICT_WARNING_FLASH_MESSAGE),
                                 'Should see a warning about the conflict in the activity history.')

    # in TestProcess
    def test_editing_process_with_conflicting_edit_but_no_publish(self):
        ''' Check edit process with a user attempting to change an activity with a conflict.
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in('erica@example.com')

            with HTTMock(self.mock_persona_verify_frances):
                frances = ChimeTestClient(self.app.test_client(), self)
                frances.sign_in('frances@example.com')

            # Frances: Start a new task
            frances.open_link('/')
            args = 'Bobbing for Apples', 'Ninjas', 'Flipping Out', 'So Awesome'
            frances.quick_activity_setup(*args)

            # Erica: Start a new task
            erica.open_link('/')
            args = 'Diving for Dollars', 'Ninjas', 'Flipping Out', 'So Awesome'
            erica.quick_activity_setup(*args)

            # Erica edits the new article.
            erica.edit_article(title_str='So, So Awesome', body_str='It was the best of times.')

            # Frances edits the new article.
            frances.edit_article(title_str='So, So Awful', body_str='It was the worst of times.')

    def test_editing_process_with_nonconflicting_edit(self):
        ''' Check edit process with a user attempting to change an activity with no conflict.
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in('erica@example.com')
            
            with HTTMock(self.mock_persona_verify_frances):
                frances = ChimeTestClient(self.app.test_client(), self)
                frances.sign_in('frances@example.com')

            # Start a new task
            frances.open_link('/')
            args = 'Bobbing for Apples', 'Ninjas', 'Flipping Out', 'So Awesome'
            f_branch_name = frances.quick_activity_setup(*args)
            f_article_path = frances.path

            # Start a new task
            erica.open_link('/')
            args = 'Diving for Dollars', 'Samurai', 'Flipping Out', 'So Awesome'
            e_branch_name = erica.quick_activity_setup(*args)

            # Edit the new article.
            erica.edit_article(title_str='So, So Awesome', body_str='It was the best of times.')

            # Ask for feedback
            erica.follow_link(href='/tree/{}'.format(e_branch_name))
            erica.request_feedback(feedback_str='Is this okay?')

            #
            # Switch users and publish the article.
            #
            frances.open_link(url=erica.path)
            frances.leave_feedback(feedback_str='It is super-great.')
            frances.approve_activity()
            frances.publish_activity()
            
            #
            # Now introduce a conflicting change on the original activity,
            # and verify that the expected flash warning is displayed.
            #
            frances.open_link(f_article_path)
            frances.edit_article(title_str='So, So Awful', body_str='It was the worst of times.')
            self.assertIsNone(frances.soup.find(text=repo_functions.UPSTREAM_EDIT_INFO_FLASH_MESSAGE),
                              'Should not see a warning about the conflict in the activity history.')

            frances.follow_link(href='/tree/{}'.format(f_branch_name))
            self.assertIsNone(frances.soup.find(text=repo_functions.UPSTREAM_EDIT_INFO_FLASH_MESSAGE),
                              'Should not see a warning about the conflict in the activity history.')

    # in TestProcess
    def test_editing_process_with_conflicting_edit_on_same_article(self):
        ''' Two people editing the same article in the same branch get a useful error.
        '''
        with HTTMock(self.auth_csv_example_allowed):
            erica_email = u'erica@example.com'
            frances_email = u'frances@example.com'
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in(erica_email)

            with HTTMock(self.mock_persona_verify_frances):
                frances = ChimeTestClient(self.app.test_client(), self)
                frances.sign_in(frances_email)

            # Frances: Start a new task, topic, subtopic, article
            frances.open_link('/')
            args = 'Triassic for Artemia', 'Biological', 'Toxicity', 'Assays'
            frances.quick_activity_setup(*args)
            branch_name = frances.get_branch_name()

            # Frances and Erica load the same article
            erica.open_link(frances.path)

            # Erica edits the new article.
            erica.edit_article(title_str='Assays', body_str='Broad leaf-like appendages')
            # Frances edits the same article and gets an error
            frances.edit_article(title_str='Assays', body_str='Typical primitive arthropod')
            # we can't get the date exactly right, so test for every other part of the message
            message_edited = view_functions.MESSAGE_PAGE_EDITED.format(published_date=u'xxx', published_by=erica_email)
            message_edited_split = message_edited.split(u'xxx')
            for part in message_edited_split:
                self.assertIsNotNone(frances.soup.find(lambda tag: tag.name == 'li' and part in tag.text))

            # Frances successfully browses elsewhere in the activity
            frances.open_link(url='/tree/{}/'.format(branch_name))
            # Frances successfully deletes the task
            frances.open_link(url='/')
            frances.delete_task(branch_name=branch_name)
            # Frances successfully creates a new task
            frances.start_task(description='Narrow Braincase for Larger Carnassials')

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
            erica.open_link('/')
            erica.start_task(description='Eating Carrion for Vultures')
            erica_branch_name = erica.get_branch_name()

            # Look for an "other" link that we know about - is it a category?
            erica.follow_link(href='/tree/{}/edit/other/'.format(erica_branch_name))

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
            frances.open_link('/')
            frances.start_task(description='Flying in Circles for Vultures')
            frances_branch_name = frances.get_branch_name()

            # Look for an "other" link that we know about - is it a category?
            frances.follow_link(href='/tree/{}/edit/other/'.format(frances_branch_name))

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
            erica.publish_activity(expected_status_code=500)

            # we got a 500 error page about a merge conflict
            pattern_template_comment_stripped = sub(ur'<!--|-->', u'', PATTERN_TEMPLATE_COMMENT)
            comments = erica.soup.find_all(text=lambda text: isinstance(text, Comment))
            self.assertTrue(pattern_template_comment_stripped.format(u'error-500') in comments)
            self.assertIsNotNone(erica.soup.find(lambda tag: tag.name == 'a' and u'MergeConflict' in tag['href']))

            # re-load the overview page
            erica.open_link(url=frances_overview_path)
            # verify that the publish button is still available
            self.assertIsNotNone(erica.soup.find(lambda tag: tag.name == 'button' and tag['value'] == u'Publish'))

    # in TestProcess
    def test_page_not_found_when_branch_published(self):
        ''' When you're working in a published branch and don't have a local copy, you get a 404 error
        '''
        with HTTMock(self.auth_csv_example_allowed):
            erica_email = u'erica@example.com'
            frances_email = u'frances@example.com'
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in(erica_email)

            with HTTMock(self.mock_persona_verify_frances):
                frances = ChimeTestClient(self.app.test_client(), self)
                frances.sign_in(frances_email)

            # Start a new task
            erica.open_link('/')
            erica.start_task(description='Eating Carrion for Vultures')
            erica_branch_name = erica.get_branch_name()

            # Enter the "other" folder
            erica.follow_link(href='/tree/{}/edit/other/'.format(erica_branch_name))

            # Create a new category
            category_name = u'Forage'
            category_slug = slugify(category_name)
            erica.add_category(category_name=category_name)

            # Ask for feedback
            erica.follow_link(href='/tree/{}'.format(erica_branch_name))
            erica.request_feedback(feedback_str='Is this okay?')

            #
            # Switch users
            #
            # approve and publish erica's changes
            frances.open_link(url=erica.path)
            frances.leave_feedback(feedback_str='It is perfect.')
            frances.approve_activity()
            frances.publish_activity()

            # delete all trace of the branch locally
            repo = view_functions.get_repo(repo_path=self.app.config['REPO_PATH'], work_path=self.app.config['WORK_PATH'], email='erica@example.com')
            repo.git.checkout('master')
            repo.git.branch('-D', erica_branch_name)
            repo.git.remote('prune', 'origin')

            #
            # Switch users
            #
            # load an edit page
            erica.open_link(url='/tree/{}/edit/other/{}/'.format(erica_branch_name, category_slug), expected_status_code=404)
            # a warning is flashed about working in a published branch
            # we can't get the date exactly right, so test for every other part of the message
            message_published = view_functions.MESSAGE_ACTIVITY_PUBLISHED.format(published_date=u'xxx', published_by=frances_email)
            message_published_split = message_published.split(u'xxx')
            for part in message_published_split:
                self.assertIsNotNone(erica.soup.find(lambda tag: tag.name == 'li' and part in tag.text))

            # the 404 page was loaded
            pattern_template_comment_stripped = sub(ur'<!--|-->', u'', PATTERN_TEMPLATE_COMMENT)
            comments = erica.soup.find_all(text=lambda text: isinstance(text, Comment))
            self.assertTrue(pattern_template_comment_stripped.format(u'error-404') in comments)

    # in TestProcess
    def test_notified_when_working_in_deleted_task(self):
        ''' When someone else deletes a task you're working in, you're notified.
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in('erica@example.com')

            with HTTMock(self.mock_persona_verify_frances):
                frances = ChimeTestClient(self.app.test_client(), self)
                frances.sign_in('frances@example.com')

            # Start a new task
            erica.open_link('/')
            task_description = u'Eating Carrion for Vultures'
            erica.start_task(description=task_description)
            erica_branch_name = erica.get_branch_name()

            # Enter the "other" folder
            erica.follow_link(href='/tree/{}/edit/other/'.format(erica_branch_name))

            #
            # Switch users
            #
            # delete erica's task
            frances.open_link(url='/')
            frances.delete_task(branch_name=erica_branch_name)
            self.assertEqual(PATTERN_FLASH_TASK_DELETED.format(description=task_description), frances.soup.find('li', class_='flash').text)

            #
            # Switch users
            #
            # load an edit page
            erica.open_link(url='/tree/{}/edit/other/'.format(erica_branch_name))
            # a warning is flashed about working in a deleted branch
            self.assertIsNotNone(erica.soup.find(text=view_functions.MESSAGE_ACTIVITY_DELETED))

    # in TestProcess
    def test_page_not_found_when_branch_deleted(self):
        ''' When you're working in a deleted branch and don't have a local copy, you get a 404 error
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in('erica@example.com')

            with HTTMock(self.mock_persona_verify_frances):
                frances = ChimeTestClient(self.app.test_client(), self)
                frances.sign_in('frances@example.com')

            # Start a new task
            erica.open_link('/')
            task_description = u'Eating Carrion for Vultures'
            erica.start_task(description=task_description)
            erica_branch_name = erica.get_branch_name()

            # Enter the "other" folder
            erica.follow_link(href='/tree/{}/edit/other/'.format(erica_branch_name))

            #
            # Switch users
            #
            # delete erica's task
            frances.open_link(url='/')
            frances.delete_task(branch_name=erica_branch_name)
            self.assertEqual(PATTERN_FLASH_TASK_DELETED.format(description=task_description), frances.soup.find('li', class_='flash').text)

            # delete all trace of the branch locally
            repo = view_functions.get_repo(repo_path=self.app.config['REPO_PATH'], work_path=self.app.config['WORK_PATH'], email='erica@example.com')
            repo.git.checkout('master')
            repo.git.branch('-D', erica_branch_name)
            repo.git.remote('prune', 'origin')

            #
            # Switch users
            #
            # load an edit page
            erica.open_link(url='/tree/{}/edit/other/'.format(erica_branch_name), expected_status_code=404)
            # a warning is flashed about working in a deleted branch
            self.assertIsNotNone(erica.soup.find(text=view_functions.MESSAGE_ACTIVITY_DELETED))
            # the 404 page was loaded
            pattern_template_comment_stripped = sub(ur'<!--|-->', u'', PATTERN_TEMPLATE_COMMENT)
            comments = erica.soup.find_all(text=lambda text: isinstance(text, Comment))
            self.assertTrue(pattern_template_comment_stripped.format(u'error-404') in comments)

    # in TestProcess
    def test_deleted_branch_not_resurrected_on_save(self):
        ''' Saving a change on a branch that exists locally but isn't at origin because it was deleted doesn't re-create the branch.
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in('erica@example.com')

            with HTTMock(self.mock_persona_verify_frances):
                frances = ChimeTestClient(self.app.test_client(), self)
                frances.sign_in('frances@example.com')

            # Start a new task
            erica.open_link('/')
            task_description = u'Squeeze A School Of Fish Into A Bait Ball for Dolphins'
            erica.start_task(description=task_description)
            erica_branch_name = erica.get_branch_name()

            # Enter the "other" folder
            erica.follow_link(href='/tree/{}/edit/other/'.format(erica_branch_name))

            # Create a category, subcategory, and article
            article_name = u'Stunned Fish'
            erica.add_category(category_name=u'Plowing Through')
            erica.add_subcategory(subcategory_name=u'Feeding On')
            erica.add_article(article_name=article_name)
            erica_article_path = erica.path

            # verify that the branch exists locally and remotely
            repo = view_functions.get_repo(repo_path=self.app.config['REPO_PATH'], work_path=self.app.config['WORK_PATH'], email='erica@example.com')
            self.assertTrue(erica_branch_name in repo.branches)
            self.assertIsNotNone(repo_functions.get_branch_if_exists_at_origin(clone=repo, default_branch_name='master', new_branch_name=erica_branch_name))

            #
            # Switch users
            #
            # delete erica's task
            frances.open_link(url='/')
            frances.delete_task(branch_name=erica_branch_name)
            self.assertEqual(PATTERN_FLASH_TASK_DELETED.format(description=task_description), frances.soup.find('li', class_='flash').text)

            #
            # Switch users
            #
            # load the article edit page
            erica.open_link(url=erica_article_path)
            # a warning is flashed about working in a deleted branch
            self.assertIsNotNone(erica.soup.find(text=view_functions.MESSAGE_ACTIVITY_DELETED))

            # try to save an edit to the article
            erica.edit_article(title_str=article_name, body_str=u'Chase fish into shallow water to catch them.')
            # we're in the article-edit template
            pattern_template_comment_stripped = sub(ur'<!--|-->', u'', PATTERN_TEMPLATE_COMMENT)
            comments = erica.soup.find_all(text=lambda text: isinstance(text, Comment))
            self.assertTrue(pattern_template_comment_stripped.format(u'article-edit') in comments)
            # a warning is flashed about working in a deleted branch
            self.assertIsNotNone(erica.soup.find(text=view_functions.MESSAGE_ACTIVITY_DELETED))

            # verify that the branch exists locally and not remotely
            self.assertTrue(erica_branch_name in repo.branches)
            self.assertIsNone(repo_functions.get_branch_if_exists_at_origin(clone=repo, default_branch_name='master', new_branch_name=erica_branch_name))

    # in TestProcess
    def test_forms_for_changes_in_active_task(self):
        ''' When working in an active (not published or deleted) task, forms or form buttons that allow
            you to make changes are visible.
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in('erica@example.com')

            with HTTMock(self.mock_persona_verify_frances):
                frances = ChimeTestClient(self.app.test_client(), self)
                frances.sign_in('frances@example.com')

            # Start a new task
            erica.open_link('/')
            task_description = u'Eating Carrion for Vultures'
            erica.start_task(description=task_description)
            erica_branch_name = erica.get_branch_name()

            # Enter the "other" folder
            erica.follow_link(href='/tree/{}/edit/other/'.format(erica_branch_name))

            # Create a category, sub-category, article
            category_name = u'Antennae Segments'
            category_slug = slugify(category_name)
            subcategory_name = u'Short Ovipositors'
            article_name = u'Inject Eggs Directly Into a Host Body'
            erica.add_category(category_name=category_name)
            erica.add_subcategory(subcategory_name=subcategory_name)
            subcategory_path = erica.path
            erica.add_article(article_name=article_name)
            article_path = erica.path

            #
            # All the edit forms and buttons are there as expected
            #

            # load an edit page
            erica.open_link(url=subcategory_path)

            # the drop-down comment form is there
            dropdown_form = erica.soup.find(lambda tag: bool(tag.name == 'div' and 'dropdown__popup' in tag.get('class'))).find('form')
            self.assertIsNotNone(dropdown_form)

            # the add new topic, subtopic, and article fields is there
            self.assertIsNotNone(erica.soup.find(lambda tag: bool(tag.name == 'input' and tag.get('placeholder') == 'Add topic')))
            self.assertIsNotNone(erica.soup.find(lambda tag: bool(tag.name == 'input' and tag.get('placeholder') == 'Add subtopic')))
            self.assertIsNotNone(erica.soup.find(lambda tag: bool(tag.name == 'input' and tag.get('placeholder') == 'Add article')))

            # there's an edit (pencil) button on the category or subcategory, and a delete (trashcan) button on the article
            topic_li = erica.soup.find(lambda tag: bool(tag.name == 'a' and tag.text == category_name)).find_parent('li')
            self.assertIsNotNone(topic_li.find(lambda tag: bool(tag.name == 'span' and 'fa-pencil' in tag.get('class'))))
            subtopic_li = erica.soup.find(lambda tag: bool(tag.name == 'a' and tag.text == subcategory_name)).find_parent('li')
            self.assertIsNotNone(subtopic_li.find(lambda tag: bool(tag.name == 'span' and 'fa-pencil' in tag.get('class'))))
            article_li = erica.soup.find(lambda tag: bool(tag.name == 'a' and tag.text == article_name)).find_parent('li')
            self.assertIsNotNone(article_li.find(lambda tag: bool(tag.name == 'span' and 'fa-trash' in tag.get('class'))))

            # load a modify page
            erica.open_link(url='/tree/{}/modify/other/{}/'.format(erica_branch_name, category_slug))

            # there's a save and delete button on the modify category form
            modify_form = erica.soup.find(lambda tag: bool(tag.name == 'textarea' and tag.get('name') == 'en-description')).find_parent('form')
            delete_button = modify_form.find('button', attrs={'name': 'delete'})
            save_button = modify_form.find('button', attrs={'name': 'save'})
            self.assertIsNotNone(delete_button)
            self.assertIsNotNone(save_button)

            # load an article edit page
            erica.open_link(url=article_path)

            # there's a save button on the edit form
            edit_form = erica.soup.find(lambda tag: bool(tag.name == 'form' and u'/tree/{}/save/'.format(erica_branch_name) in tag.get('action')))
            save_button = edit_form.find('button', value='Save')
            self.assertIsNotNone(save_button)

    # in TestProcess
    def test_no_forms_for_changes_in_inactive_task(self):
        ''' When working in an inactive (published or deleted) task, forms or form buttons that would
            allow you to make changes are hidden.
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in('erica@example.com')

            with HTTMock(self.mock_persona_verify_frances):
                frances = ChimeTestClient(self.app.test_client(), self)
                frances.sign_in('frances@example.com')

            # Start a new task
            erica.open_link('/')
            task_description = u'Eating Carrion for Vultures'
            erica.start_task(description=task_description)
            erica_branch_name = erica.get_branch_name()

            # Enter the "other" folder
            erica.follow_link(href='/tree/{}/edit/other/'.format(erica_branch_name))

            # Create a category, sub-category, article
            category_name = u'Antennae Segments'
            category_slug = slugify(category_name)
            subcategory_name = u'Short Ovipositors'
            article_name = u'Inject Eggs Directly Into a Host Body'
            erica.add_category(category_name=category_name)
            erica.add_subcategory(subcategory_name=subcategory_name)
            subcategory_path = erica.path
            erica.add_article(article_name=article_name)
            article_path = erica.path

            #
            # Switch users
            #
            # delete erica's task
            frances.open_link(url='/')
            frances.delete_task(branch_name=erica_branch_name)
            self.assertEqual(PATTERN_FLASH_TASK_DELETED.format(description=task_description), frances.soup.find('li', class_='flash').text)

            #
            # Switch users
            #
            # load an edit page
            erica.open_link(url=subcategory_path)

            # the drop-down comment form isn't there
            dropdown_form = erica.soup.find(lambda tag: bool(tag.name == 'div' and 'dropdown__popup' in tag.get('class'))).find('form')
            self.assertIsNone(dropdown_form)

            # the add new topic, subtopic, and article fields aren't there
            self.assertIsNone(erica.soup.find(lambda tag: bool(tag.name == 'input' and tag.get('placeholder') == 'Add topic')))
            self.assertIsNone(erica.soup.find(lambda tag: bool(tag.name == 'input' and tag.get('placeholder') == 'Add subtopic')))
            self.assertIsNone(erica.soup.find(lambda tag: bool(tag.name == 'input' and tag.get('placeholder') == 'Add article')))

            # there's no edit (pencil) button on the category or subcategory, and no delete (trashcan) button on the article
            topic_li = erica.soup.find(lambda tag: bool(tag.name == 'a' and tag.text == category_name)).find_parent('li')
            self.assertIsNone(topic_li.find(lambda tag: bool(tag.name == 'span' and 'fa-pencil' in tag.get('class'))))
            subtopic_li = erica.soup.find(lambda tag: bool(tag.name == 'a' and tag.text == subcategory_name)).find_parent('li')
            self.assertIsNone(subtopic_li.find(lambda tag: bool(tag.name == 'span' and 'fa-pencil' in tag.get('class'))))
            article_li = erica.soup.find(lambda tag: bool(tag.name == 'a' and tag.text == article_name)).find_parent('li')
            self.assertIsNone(article_li.find(lambda tag: bool(tag.name == 'span' and 'fa-trash' in tag.get('class'))))

            # load a modify page
            erica.open_link(url='/tree/{}/modify/other/{}/'.format(erica_branch_name, category_slug))

            # there's no save or delete button on the modify category form
            modify_form = erica.soup.find(lambda tag: bool(tag.name == 'textarea' and tag.get('name') == 'en-description')).find_parent('form')
            delete_button = modify_form.find('button', attrs={'name': 'delete'})
            save_button = modify_form.find('button', attrs={'name': 'save'})
            self.assertIsNone(delete_button)
            self.assertIsNone(save_button)

            # load an article edit page
            erica.open_link(url=article_path)

            # there's no save button on the edit form
            edit_form = erica.soup.find(lambda tag: bool(tag.name == 'form' and u'/tree/{}/save/'.format(erica_branch_name) in tag.get('action')))
            save_button = edit_form.find('button', value='Save')
            self.assertIsNone(save_button)

    def test_editing_out_of_date_article(self):
        ''' Check edit process with a user attempting to edit an out-of-date article.
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in('erica@example.com')
            
            with HTTMock(self.mock_persona_verify_frances):
                frances = ChimeTestClient(self.app.test_client(), self)
                frances.sign_in('frances@example.com')

            # Start a new task
            frances.open_link('/')
            args = 'Bobbing for Apples', 'Ninjas', 'Flipping Out', 'So Awesome'
            frances.quick_activity_setup(*args)
            frances.edit_article(title_str='So, So Awesome', body_str='It was the best of times.')
            
            # Erica now opens the article that Frances started.
            erica.open_link(frances.path)
            
            # Frances starts a different article.
            frances.open_link(dirname(dirname(frances.path)) + '/')
            frances.add_article('So Terrible')
            
            # Meanwhile, Erica completes her edits.
            erica.edit_article(title_str='So, So Awesome', body_str='It was the best of times.\n\nBut also the worst of times.')

if __name__ == '__main__':
    main()
