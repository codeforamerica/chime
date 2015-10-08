# -- coding: utf-8 --
from __future__ import absolute_import

from unittest import main, TestCase

from tempfile import mkdtemp
from os.path import join, exists, dirname, isdir, abspath, realpath
from urllib import quote
from os import environ
from shutil import rmtree, copytree
from uuid import uuid4
import sys
from chime.repo_functions import ChimeRepo
from slugify import slugify
import json
import logging
import tempfile
logging.disable(logging.CRITICAL)

repo_root = abspath(join(dirname(__file__), '..'))
sys.path.insert(0, repo_root)

from git.cmd import GitCommandError
from box.util.rotunicode import RotUnicode

from chime import jekyll_functions, repo_functions, edit_functions, view_functions
from chime import constants
from chime import chime_activity

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
PATTERN_UNREVIEWED_EDITS_LINK = u'<a href="/tree/{branch_name}/" class="toolbar__item button">Unreviewed Edits</a>'
PATTERN_FEEDBACK_REQUESTED_LINK = u'<a href="/tree/{branch_name}/" class="toolbar__item button">Feedback requested</a>'
PATTERN_READY_TO_PUBLISH_LINK = u'<a href="/tree/{branch_name}/" class="toolbar__item button">Ready to publish</a>'

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
        task_description = str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, u'erica@example.com')

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
        task_description = str(uuid4())

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
        branch2 = repo_functions.get_start_branch(self.clone2, 'master', task_description, self.session['email'])

        self.assertTrue(branch2.name in self.clone2.branches)
        # compare the second-to-last commit on branch2 (by adding ".parents[0]", as
        # the most recent one is the creation of the task metadata file
        self.assertEqual(branch2.commit.parents[0].hexsha, self.origin.refs['master'].commit.hexsha)

    # in TestRepo
    def test_delete_missing_branch(self):
        ''' Delete a branch in a clone that's still in origin, see if it can be deleted anyway.
        '''
        task_description = str(uuid4())

        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, u'erica@example.com')

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
        task_description = str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, self.session['email'])

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
        first_result = view_functions.add_article_or_category(self.clone1, None, 'categories', 'My New Category', constants.CATEGORY_LAYOUT)
        self.assertEqual(u'The "My New Category" topic was created\n\n{"branch_name": "master", "actions": [{"action": "create", "file_path": "categories/my-new-category/index.markdown", "display_type": "category", "title": "My New Category"}]}', first_result[0])
        self.assertEqual(u'categories/my-new-category/index.markdown', first_result[1])
        self.assertEqual(u'categories/my-new-category/', first_result[2])
        self.assertEqual(True, first_result[3])
        second_result = view_functions.add_article_or_category(self.clone1, None, 'categories', 'My New Category', constants.CATEGORY_LAYOUT)
        self.assertEqual('Topic "My New Category" already exists', second_result[0])
        self.assertEqual(u'categories/my-new-category/index.markdown', second_result[1])
        self.assertEqual(u'categories/my-new-category/', second_result[2])
        self.assertEqual(False, second_result[3])

    # in TestRepo
    def test_try_to_create_existing_article(self):
        ''' We can't create an article that exists already
        '''
        first_result = view_functions.add_article_or_category(self.clone1, None, 'categories/example', 'New Article', constants.ARTICLE_LAYOUT)
        self.assertEqual(u'The "New Article" article was created\n\n{"branch_name": "master", "actions": [{"action": "create", "file_path": "categories/example/new-article/index.markdown", "display_type": "article", "title": "New Article"}]}', first_result[0])
        self.assertEqual(u'categories/example/new-article/index.markdown', first_result[1])
        self.assertEqual(u'categories/example/new-article/index.markdown', first_result[2])
        self.assertEqual(True, first_result[3])
        second_result = view_functions.add_article_or_category(self.clone1, None, 'categories/example', 'New Article', constants.ARTICLE_LAYOUT)
        self.assertEqual('Article "New Article" already exists', second_result[0])
        self.assertEqual(u'categories/example/new-article/index.markdown', first_result[1])
        self.assertEqual(u'categories/example/new-article/index.markdown', first_result[2])
        self.assertEqual(False, second_result[3])

    # in TestRepo
    def test_create_category_with_slash_in_name(self):
        ''' Trying to create an category with /s in its name creates a single category
        '''
        category_name = u'Kristen/Melissa/Kate/Leslie'
        category_slug = slugify(category_name)
        add_result = view_functions.add_article_or_category(self.clone1, None, 'categories', category_name, constants.CATEGORY_LAYOUT)
        self.assertEqual(u'The "{category_name}" topic was created\n\n{{"branch_name": "{branch_name}", "actions": [{{"action": "create", "file_path": "categories/{category_slug}/index.markdown", "display_type": "category", "title": "{category_name}"}}]}}'.format(branch_name='master', category_name=category_name, category_slug=category_slug), add_result[0])
        self.assertEqual(u'categories/{category_slug}/index.markdown'.format(category_slug=category_slug), add_result[1])
        self.assertEqual(u'categories/{category_slug}/'.format(category_slug=category_slug), add_result[2])
        self.assertEqual(True, add_result[3])

    # in TestRepo
    def test_create_article_with_slash_in_name(self):
        ''' Trying to create an article with /s in its name creates a single article
        '''
        article_name = u'Erin/Abby/Jillian/Patty'
        article_slug = slugify(article_name)

        add_result = view_functions.add_article_or_category(self.clone1, None, 'categories/example', article_name, constants.ARTICLE_LAYOUT)
        self.assertEqual(u'The "{article_name}" article was created\n\n{{"branch_name": "{branch_name}", "actions": [{{"action": "create", "file_path": "categories/example/{article_slug}/index.markdown", "display_type": "article", "title": "{article_name}"}}]}}'.format(branch_name='master', article_name=article_name, article_slug=article_slug), add_result[0])
        self.assertEqual(u'categories/example/{article_slug}/index.markdown'.format(article_slug=article_slug), add_result[1])
        self.assertEqual(u'categories/example/{article_slug}/index.markdown'.format(article_slug=article_slug), add_result[2])
        self.assertEqual(True, add_result[3])

    # in TestRepo
    def test_delete_directory(self):
        ''' Make a new file and directory and delete them.
        '''
        task_description = str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, u'erica@example.com')

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
        task_description = str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, u'erica@example.com')

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
        # Show that upstream changes from master have NOT been merged here.
        #
        with open(self.clone2.working_dir + '/index.md') as file:
            front2b, body2b = jekyll_functions.load_jekyll_doc(file)

        self.assertNotEqual(front2b[title_key_name], front1[title_key_name])
        self.assertEqual(body2b.strip(), 'Another change to the body')
        self.assertFalse(self.clone2.commit().message.startswith('Merged work from'))

        # There's no conflict; the merge would be clean.
        self.assertIsNone(repo_functions.get_conflict(self.clone2, 'master'), "There is no conflict")
        self.assertIsNotNone(repo_functions.get_changed(self.clone2, 'master'), "A change should be visible")

    # in TestRepo
    def test_multifile_merge(self):
        ''' Test that two non-conflicting new files merge cleanly.
        '''
        fake_author_email = u'erica@example.com'
        task_description = str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, fake_author_email)
        branch2 = repo_functions.get_start_branch(self.clone2, 'master', task_description, fake_author_email)
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
        task_description = str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, fake_author_email)
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
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description1, fake_author_email)
        branch2 = repo_functions.get_start_branch(self.clone2, 'master', task_description2, fake_author_email)
        branch1_name = branch1.name

        #
        # Make new files in each branch and save them.
        #
        branch1.checkout()
        branch2.checkout()

        edit_functions.create_new_page(self.clone1, '', 'conflict.md',
                                       dict(title='Hello'), 'Hello hello.')

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
        repo_functions.complete_branch(self.clone1, 'master', branch1_name)
        self.assertFalse(branch1_name in self.origin.branches)

        #
        # Show that the changes from the second branch conflict with the first.
        #
        self.assertIsNone(repo_functions.get_conflict(self.clone2, 'master'),
                          "Shouldn't see any conflict yet")

        edit_functions.create_new_page(self.clone2, '', 'conflict.md',
                                       dict(title='Goodbye'), 'Goodbye goodbye.')

        args2 = self.clone2, 'conflict.md', '...', branch2.commit.hexsha, 'master'
        repo_functions.save_working_file(*args2)

        conflict = repo_functions.get_conflict(self.clone2, 'master')

        self.assertTrue(bool(conflict))
        diffs = conflict.remote_commit.diff(conflict.local_commit)

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
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description1, fake_author_email)
        branch2 = repo_functions.get_start_branch(self.clone2, 'master', task_description2, fake_author_email)
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
        task_description = str(uuid4())
        title_branch = repo_functions.get_existing_branch(self.clone1, 'master', 'title')
        compare_branch = repo_functions.get_start_branch(self.clone2, 'master', task_description, fake_author_email)
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
        task_description = str(uuid4())
        title_branch_name = 'title'
        repo_functions.get_existing_branch(self.clone1, 'master', title_branch_name)
        compare_branch = repo_functions.get_start_branch(self.clone2, 'master', task_description, fake_author_email)
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
        self.assertTrue(self.clone2.commit().message.startswith(u'The "{}" {}'.format(task_description, repo_functions.ACTIVITY_DELETED_MESSAGE)))

    # in TestRepo
    def test_peer_review(self):
        ''' Exercise the review process
        '''
        fake_author_email = u'erica@example.com'
        task_description = str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, fake_author_email)
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
        self.assertEqual(review_state, constants.REVIEW_STATE_FRESH)
        self.assertTrue(review_authorized)

        edit_functions.update_page(self.clone1, 'index.md',
                                   dict(title=task_description), 'Hello you-all.')

        repo_functions.save_working_file(self.clone1, 'index.md', 'I made a change',
                                         self.clone1.commit().hexsha, 'master')

        # verify that the activity has unreviewed edits and that Jim Content Creator is authorized to request feedback
        review_state, review_authorized = repo_functions.get_review_state_and_authorized(self.clone1, 'master', branch1_name, fake_creator_email)
        self.assertEqual(review_state, constants.REVIEW_STATE_EDITED)
        self.assertTrue(review_authorized)

        # request feedback as Jim Content Creator
        repo_functions.update_review_state(self.clone1, branch1_name, constants.REVIEW_STATE_FEEDBACK)
        # verify that the activity has feedback requested and that fake is authorized to endorse
        review_state, review_authorized = repo_functions.get_review_state_and_authorized(self.clone1, 'master', branch1_name, fake_author_email)
        self.assertEqual(review_state, constants.REVIEW_STATE_FEEDBACK)
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
        repo_functions.update_review_state(self.clone1, branch1_name, constants.REVIEW_STATE_ENDORSED)
        # verify that the activity has been endorsed and that Joe Reviewer is authorized to publish
        review_state, review_authorized = repo_functions.get_review_state_and_authorized(self.clone1, 'master', branch1_name, fake_reviewer_email)
        self.assertEqual(review_state, constants.REVIEW_STATE_ENDORSED)
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
        self.assertEqual(review_state, constants.REVIEW_STATE_EDITED)
        self.assertTrue(review_authorized)

        # request feedback as Joe Reviewer
        repo_functions.update_review_state(self.clone1, branch1_name, constants.REVIEW_STATE_FEEDBACK)
        # verify that the activity has feedback requested and that Joe Reviewer is not authorized to endorse
        review_state, review_authorized = repo_functions.get_review_state_and_authorized(self.clone1, 'master', branch1_name, fake_reviewer_email)
        self.assertEqual(review_state, constants.REVIEW_STATE_FEEDBACK)
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
        repo_functions.update_review_state(self.clone1, branch1_name, constants.REVIEW_STATE_ENDORSED)
        # verify that the activity has been endorsed and that Jane Reviewer is authorized to publish
        review_state, review_authorized = repo_functions.get_review_state_and_authorized(self.clone1, 'master', branch1_name, fake_nonprofit_email)
        self.assertEqual(review_state, constants.REVIEW_STATE_ENDORSED)
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
        task_description = u'suck blood from a mammal for mosquito larvae'

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

        working_branch = repo_functions.get_start_branch(new_clone, 'master', task_description, fake_author_email)
        self.assertTrue(working_branch.name in new_clone.branches)
        self.assertTrue(working_branch.name in self.origin.branches)
        working_branch.checkout()

        # create an article
        art_title = u'快速狐狸'
        art_slug = slugify(art_title)
        add_message, file_path, redirect_path, do_save = view_functions.add_article_or_category(new_clone, None, u'', art_title, constants.ARTICLE_LAYOUT)
        self.assertEqual(u'{}/index.{}'.format(art_slug, constants.CONTENT_FILE_EXTENSION), file_path)
        self.assertEqual(u'The "{art_title}" article was created\n\n{{"branch_name": "{branch_name}", "actions": [{{"action": "create", "file_path": "{file_path}", "display_type": "article", "title": "{art_title}"}}]}}'.format(branch_name=working_branch.name, art_title=art_title, file_path=file_path), add_message)
        self.assertEqual(u'{}/index.{}'.format(art_slug, constants.CONTENT_FILE_EXTENSION), redirect_path)
        self.assertEqual(True, do_save)
        # commit the article
        repo_functions.save_working_file(new_clone, file_path, add_message, new_clone.commit().hexsha, 'master')

    # in TestRepo
    def test_edit_category_title_and_description(self):
        ''' Edits to category details are saved
        '''
        # start a new branch
        fake_author_email = u'erica@example.com'
        task_description = u'squeezing lemons for lemonade lovers'

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

        working_branch = repo_functions.get_start_branch(new_clone, 'master', task_description, fake_author_email)
        self.assertTrue(working_branch.name in new_clone.branches)
        self.assertTrue(working_branch.name in self.origin.branches)
        working_branch.checkout()

        # create a category
        cat_title = u'快速狐狸'
        cat_slug = slugify(cat_title)
        add_message, file_path, redirect_path, do_save = view_functions.add_article_or_category(new_clone, working_branch.name, u'', cat_title, constants.CATEGORY_LAYOUT)
        self.assertEqual(u'{}/index.{}'.format(cat_slug, constants.CONTENT_FILE_EXTENSION), file_path)
        self.assertEqual(u'The "{cat_title}" topic was created\n\n{{"branch_name": "{branch_name}", "actions": [{{"action": "create", "file_path": "{file_path}", "display_type": "category", "title": "{cat_title}"}}]}}'.format(branch_name=working_branch.name, cat_title=cat_title, file_path=file_path), add_message)
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
        task_description = u'grating lemons for zest lovers'

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

        working_branch = repo_functions.get_start_branch(new_clone, 'master', task_description, fake_author_email)
        self.assertTrue(working_branch.name in new_clone.branches)
        self.assertTrue(working_branch.name in self.origin.branches)
        working_branch.checkout()

        # create a category
        cat_title = u'Daffodils and Drop Cloths'
        cat_slug = slugify(cat_title)
        add_message, file_path, redirect_path, do_save = view_functions.add_article_or_category(new_clone, working_branch.name, u'', cat_title, constants.CATEGORY_LAYOUT)
        self.assertEqual(u'{}/index.{}'.format(cat_slug, constants.CONTENT_FILE_EXTENSION), file_path)
        self.assertEqual(u'The "{cat_title}" topic was created\n\n{{"branch_name": "{branch_name}", "actions": [{{"action": "create", "file_path": "{file_path}", "display_type": "category", "title": "{cat_title}"}}]}}'.format(branch_name=working_branch.name, cat_title=cat_title, file_path=file_path), add_message)
        self.assertEqual(u'{}/'.format(cat_slug), redirect_path)
        self.assertEqual(True, do_save)
        # commit the category
        repo_functions.save_working_file(new_clone, file_path, add_message, new_clone.commit().hexsha, 'master')

        # verify that the directory and index file exist
        cat_index_path = join(new_clone.working_dir, file_path)
        self.assertTrue(exists(cat_index_path))
        self.assertTrue(exists(repo_functions.strip_index_file(cat_index_path)))

        # create a category inside that
        cat2_title = u'Drain Bawlers'
        cat2_slug = slugify(cat2_title)
        add_message, cat2_path, redirect_path, do_save = view_functions.add_article_or_category(new_clone, working_branch.name, cat_slug, cat2_title, constants.CATEGORY_LAYOUT)
        self.assertEqual(u'{}/{}/index.{}'.format(cat_slug, cat2_slug, constants.CONTENT_FILE_EXTENSION), cat2_path)
        self.assertEqual(u'The "{cat_title}" topic was created\n\n{{"branch_name": "{branch_name}", "actions": [{{"action": "create", "file_path": "{file_path}", "display_type": "category", "title": "{cat_title}"}}]}}'.format(branch_name=working_branch.name, cat_title=cat2_title, file_path=cat2_path), add_message)
        self.assertEqual(u'{}/{}/'.format(cat_slug, cat2_slug), redirect_path)
        self.assertEqual(True, do_save)
        # commit the category
        repo_functions.save_working_file(new_clone, cat2_path, add_message, new_clone.commit().hexsha, 'master')

        # verify that the directory and index file exist
        cat2_index_path = join(new_clone.working_dir, cat2_path)
        self.assertTrue(exists(cat2_index_path))
        self.assertTrue(exists(repo_functions.strip_index_file(cat2_index_path)))

        # and an article inside that
        art_title = u'သံပုရာဖျော်ရည်'
        art_slug = slugify(art_title)
        dir_path = redirect_path.rstrip('/')
        add_message, art_path, redirect_path, do_save = view_functions.add_article_or_category(new_clone, working_branch.name, dir_path, art_title, constants.ARTICLE_LAYOUT)
        self.assertEqual(u'{}/{}/{}/index.{}'.format(cat_slug, cat2_slug, art_slug, constants.CONTENT_FILE_EXTENSION), art_path)
        self.assertEqual(u'The "{art_title}" article was created\n\n{{"branch_name": "{branch_name}", "actions": [{{"action": "create", "file_path": "{file_path}", "display_type": "article", "title": "{art_title}"}}]}}'.format(branch_name=working_branch.name, art_title=art_title, file_path=art_path), add_message)
        self.assertEqual(u'{}/{}/{}/index.{}'.format(cat_slug, cat2_slug, art_slug, constants.CONTENT_FILE_EXTENSION), redirect_path)
        self.assertEqual(True, do_save)
        # commit the article
        repo_functions.save_working_file(new_clone, art_path, add_message, new_clone.commit().hexsha, 'master')

        # verify that the directory and index file exist
        art_index_path = join(new_clone.working_dir, art_path)
        self.assertTrue(exists(art_index_path))
        self.assertTrue(exists(repo_functions.strip_index_file(art_index_path)))

        # now delete the second category
        browse_path = repo_functions.strip_index_file(art_path)
        redirect_path, do_save, commit_message = view_functions.delete_page(repo=new_clone, working_branch_name=working_branch.name, browse_path=browse_path, target_path=dir_path)
        self.assertEqual(cat_slug.rstrip('/'), redirect_path.rstrip('/'))
        self.assertEqual(True, do_save)
        self.assertEqual(u'The "{cat2_title}" topic (containing 1 article) was deleted\n\n{{"branch_name": "{branch_name}", "actions": [{{"action": "delete", "file_path": "{cat2_path}", "display_type": "category", "title": "{cat2_title}"}}, {{"action": "delete", "file_path": "{art_path}", "display_type": "article", "title": "{art_title}"}}]}}'.format(branch_name=working_branch.name, cat2_title=cat2_title, cat2_path=cat2_path, art_path=art_path, art_title=art_title), commit_message)

        repo_functions.save_working_file(clone=new_clone, path=dir_path, message=commit_message, base_sha=new_clone.commit().hexsha, default_branch_name='master')

        # verify that the files are gone
        self.assertFalse(exists(cat2_index_path))
        self.assertFalse(exists(repo_functions.strip_index_file(cat2_index_path)))
        self.assertFalse(exists(art_index_path))
        self.assertFalse(exists(repo_functions.strip_index_file(art_index_path)))

    # in TestRepo
    def test_activity_history_recorded(self):
        ''' The activity history accurately records activity events.
        '''
        # start a new branch
        fake_author_email = u'erica@example.com'
        task_description = u'shake trees until coconuts fall off for castaways'

        environ['GIT_AUTHOR_EMAIL'] = fake_author_email
        environ['GIT_COMMITTER_EMAIL'] = fake_author_email

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

        working_branch = repo_functions.get_start_branch(new_clone, 'master', task_description, fake_author_email)
        self.assertTrue(working_branch.name in new_clone.branches)
        self.assertTrue(working_branch.name in self.origin.branches)
        working_branch.checkout()

        # create some category/article structure
        create_details = [
            ('', 'Tree', constants.CATEGORY_LAYOUT),
            ('tree', 'Coconut', constants.CATEGORY_LAYOUT),
            ('tree/coconut', 'Coconut Milk', constants.ARTICLE_LAYOUT),
            ('', 'Rock', constants.CATEGORY_LAYOUT),
            ('rock', 'Barnacle', constants.CATEGORY_LAYOUT),
            ('', 'Sand', constants.CATEGORY_LAYOUT)
        ]
        updated_details = []
        for detail in create_details:
            add_message, file_path, redirect_path, do_save = view_functions.add_article_or_category(new_clone, working_branch.name, detail[0], detail[1], detail[2])
            updated_details.append(detail + (file_path,))
            repo_functions.save_working_file(new_clone, file_path, add_message, new_clone.commit().hexsha, 'master')

        # add a comment
        funny_comment = u'I like coconuts ᶘ ᵒᴥᵒᶅ'
        repo_functions.provide_feedback(new_clone, working_branch.name, funny_comment)

        # add another comment with newlines
        newline_comment = u'You wound me sir.\n\nI thought we were friends\nBut I guess we are not.'
        repo_functions.provide_feedback(new_clone, working_branch.name, newline_comment)

        # delete a category with stuff in it
        commit_message = view_functions.make_delete_display_commit_message(new_clone, working_branch.name, 'tree')
        deleted_file_paths, do_save = edit_functions.delete_file(new_clone, 'tree')
        # commit
        repo_functions.save_working_file(new_clone, 'tree', commit_message, new_clone.commit().hexsha, 'master')

        # checkout
        working_branch.checkout()

        # get and check the history
        activity = chime_activity.ChimeActivity(repo=new_clone, branch_name=working_branch.name, default_branch_name='master', actor_email=fake_author_email)
        activity_history = activity.history
        self.assertEqual(len(activity_history), 10)

        # check the creation of the activity
        check_item = activity_history.pop()
        self.assertEqual(u'The "{}" activity was started'.format(task_description), check_item['commit_subject'])
        self.assertEqual(check_item['author_email'], fake_author_email)
        self.assertEqual(check_item['task_description'], task_description)
        self.assertEqual(check_item['branch_name'], working_branch.name)
        self.assertEqual(constants.COMMIT_TYPE_ACTIVITY_UPDATE, check_item['commit_type'])

        # check the delete
        check_item = activity_history.pop(0)
        self.assertEqual(u'The "{}" topic (containing 1 topic and 1 article) was deleted'.format(updated_details[0][1]), check_item['commit_subject'])
        self.assertEqual(working_branch.name, check_item['branch_name'])
        self.assertEqual(json.loads(u'[{{"action": "delete", "file_path": "{cat1_path}", "display_type": "category", "title": "{cat1_title}"}}, {{"action": "delete", "file_path": "{cat2_path}", "display_type": "category", "title": "{cat2_title}"}}, {{"action": "delete", "file_path": "{art1_path}", "display_type": "article", "title": "{art1_title}"}}]'.format(cat1_path=updated_details[0][3], cat1_title=updated_details[0][1], cat2_path=updated_details[1][3], cat2_title=updated_details[1][1], art1_path=updated_details[2][3], art1_title=updated_details[2][1])), check_item['actions'])
        self.assertEqual(constants.COMMIT_TYPE_EDIT, check_item['commit_type'])

        # check the comments
        check_item = activity_history.pop(0)
        self.assertEqual(u'Provided feedback.', check_item['commit_subject'])
        self.assertEqual(newline_comment, check_item['message'])
        self.assertEqual(constants.COMMIT_TYPE_COMMENT, check_item['commit_type'])

        check_item = activity_history.pop(0)
        self.assertEqual(u'Provided feedback.', check_item['commit_subject'])
        self.assertEqual(funny_comment, check_item['message'])
        self.assertEqual(constants.COMMIT_TYPE_COMMENT, check_item['commit_type'])

        # check the category & article creations
        for pos, check_item in list(enumerate(activity_history)):
            check_detail = updated_details[len(updated_details) - (pos + 1)]
            self.assertEqual(u'The "{}" {} was created'.format(check_detail[1], view_functions.file_display_name(check_detail[2])), check_item['commit_subject'])
            self.assertEqual(working_branch.name, check_item['branch_name'])
            self.assertEqual(json.loads(u'[{{"action": "create", "file_path": "{file_path}", "display_type": "{display_type}", "title": "{title}"}}]'.format(file_path=check_detail[3], display_type=check_detail[2], title=check_detail[1])), check_item['actions'])
            self.assertEqual(constants.COMMIT_TYPE_EDIT, check_item['commit_type'])

    # in TestRepo
    def test_newlines_in_commit_message_body(self):
        ''' Newlines in the commit message body are preserved.
        '''
        # start a new branch
        fake_author_email = u'erica@example.com'
        task_description = u'cling to a rock and scrape bacteria and algae off of it with a radula for mollusks'

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

        working_branch = repo_functions.get_start_branch(new_clone, 'master', task_description, fake_author_email)
        self.assertTrue(working_branch.name in new_clone.branches)
        self.assertTrue(working_branch.name in self.origin.branches)
        working_branch.checkout()

        # add some comments with newlines
        striking_comment = u'A striking feature of molluscs is the use of the same organ for multiple functions.\n(و ˃̵ᴗ˂̵)و\n\nFor example, the heart and nephridia ("kidneys") are important parts of the reproductive system, as well as the circulatory and excretory systems\nᶘ ᵒᴥᵒᶅ'
        repo_functions.provide_feedback(new_clone, working_branch.name, striking_comment)

        universal_comment = u'The three most universal features defining modern molluscs are:\n\n1. A mantle with a significant cavity used for breathing and excretion,\n\n2. the presence of a radula, and\n\n3. the structure of the nervous system.'
        repo_functions.provide_feedback(new_clone, working_branch.name, universal_comment)

        # checkout
        working_branch.checkout()

        _, universal_body = repo_functions.get_commit_message_subject_and_body(working_branch.commit)
        _, striking_body = repo_functions.get_commit_message_subject_and_body(working_branch.commit.parents[0])

        universal_message = json.loads(universal_body)['message']
        striking_message = json.loads(striking_body)['message']

        self.assertEqual(universal_comment, universal_message)
        self.assertEqual(striking_comment, striking_message)

    # in TestRepo
    def test_delete_full_folders(self):
        ''' Make sure that full folders can be deleted, and that what's reported as deleted matches what's expected.
        '''
        # build some nested categories
        view_functions.add_article_or_category(self.clone1, None, '', 'quick', constants.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, None, 'quick', 'brown', constants.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, None, 'quick/brown', 'fox', constants.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, None, 'quick', 'red', constants.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, None, 'quick', 'yellow', constants.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, None, 'quick/yellow', 'banana', constants.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, None, 'quick', 'orange', constants.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, None, 'quick/brown', 'potato', constants.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, None, 'quick/yellow', 'lemon', constants.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, None, 'quick/red', 'tomato', constants.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, None, 'quick/red', 'balloon', constants.CATEGORY_LAYOUT)
        view_functions.add_article_or_category(self.clone1, None, 'quick/orange', 'peanut', constants.CATEGORY_LAYOUT)
        # add in some articles
        view_functions.add_article_or_category(self.clone1, None, 'quick/brown/fox', 'fur', constants.ARTICLE_LAYOUT)
        view_functions.add_article_or_category(self.clone1, None, 'quick/brown/fox', 'ears', constants.ARTICLE_LAYOUT)
        view_functions.add_article_or_category(self.clone1, None, 'quick/yellow/lemon', 'rind', constants.ARTICLE_LAYOUT)
        view_functions.add_article_or_category(self.clone1, None, 'quick/yellow/lemon', 'pulp', constants.ARTICLE_LAYOUT)
        view_functions.add_article_or_category(self.clone1, None, 'quick/orange/peanut', 'shell', constants.ARTICLE_LAYOUT)
        view_functions.add_article_or_category(self.clone1, None, 'quick/red/balloon', 'string', constants.ARTICLE_LAYOUT)

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
        task_description = str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, fake_author_email)
        branch1_name = branch1.name
        branch1.checkout()

        # verify that the most recent commit on the new branch is for starting the activity
        self.assertTrue(repo_functions.ACTIVITY_CREATED_MESSAGE in branch1.commit.message)

        # validate the existence of the task metadata file
        task_metadata = repo_functions.get_task_metadata_for_branch(self.clone1, branch1_name)
        self.assertEqual(type(task_metadata), dict)
        self.assertTrue(len(task_metadata) > 0)

        # validate the contents of the task metadata file
        self.assertEqual(task_metadata['author_email'], fake_author_email)
        self.assertEqual(task_metadata['task_description'], task_description)

    # in TestRepo
    def test_task_metadata_creation_with_unicode(self):
        ''' The task metadata file is created when a branch is started, and contains the expected information.
        '''
        fake_author_email = u'¯\_(ツ)_/¯@快速狐狸.com'
        task_description = u'(╯°□°）╯︵ ┻━┻ for ૮(꒦ິ ˙̫̮ ꒦ິ)ა'
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, fake_author_email)
        branch1_name = branch1.name
        branch1.checkout()

        # verify that the most recent commit on the new branch is for starting the activity
        self.assertTrue(repo_functions.ACTIVITY_CREATED_MESSAGE in branch1.commit.message)

        # validate the existence of the task metadata file
        task_metadata = repo_functions.get_task_metadata_for_branch(self.clone1, branch1_name)
        self.assertEqual(type(task_metadata), dict)
        self.assertTrue(len(task_metadata) > 0)

        # validate the contents of the task metadata file
        self.assertEqual(task_metadata['author_email'], fake_author_email)
        self.assertEqual(task_metadata['task_description'], task_description)

    # in TestRepo
    def test_task_metadata_update(self):
        ''' The task metadata file can be updated
        '''
        fake_author_email = u'erica@example.com'
        task_description = str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, fake_author_email)
        branch1_name = branch1.name
        branch1.checkout()

        # verify that the most recent commit on the new branch is for starting the activity
        self.assertTrue(repo_functions.ACTIVITY_CREATED_MESSAGE in branch1.commit.message)

        # validate the existence of the task metadata file
        task_metadata = repo_functions.get_task_metadata_for_branch(self.clone1, branch1_name)
        self.assertEqual(type(task_metadata), dict)
        self.assertTrue(len(task_metadata) > 0)

        # validate the contents of the task metadata file
        self.assertEqual(task_metadata['author_email'], fake_author_email)
        self.assertEqual(task_metadata['task_description'], task_description)

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
        task_description = str(uuid4())
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description, fake_author_email)
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
        task_description = u'Attract Insects With Anthocyanin Pigments To The Cavity Formed By A Cupped Leaf for Nepenthes'
        clone1_branch = repo_functions.get_start_branch(self.clone1, 'master', task_description, erica_email)
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
        branch1 = repo_functions.get_start_branch(self.clone1, 'master', task_description1, fake_author_email1)
        branch2 = repo_functions.get_start_branch(self.clone2, 'master', task_description2, fake_author_email2)
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

if __name__ == '__main__':
    main()
