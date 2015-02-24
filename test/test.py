# -- coding: utf-8 --
from unittest import main, TestCase

from tempfile import mkdtemp
from StringIO import StringIO
from os.path import join, exists
from os import environ
from shutil import rmtree, copytree
from uuid import uuid4
from re import search
import random
import json
from datetime import date, timedelta

import sys
import os
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(here)

from git import Repo
from box.util.rotunicode import RotUnicode
from httmock import response, HTTMock
from mock import MagicMock

from bizarro import create_app, jekyll_functions, repo_functions, edit_functions, google_api_functions, view_functions

import codecs
codecs.register(RotUnicode.search_function)

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

    def test_bad_files(self):
        file = StringIO('Missing front matter')

        with self.assertRaises(Exception):
            jekyll_functions.load_jekyll_doc(file)

class TestViewFunctions (TestCase):

    def setUp(self):
        repo_path = os.path.dirname(os.path.abspath(__file__)) + '/test-app.git'
        temp_repo_dir = mkdtemp(prefix='bizarro-root')
        temp_repo_path = temp_repo_dir + '/test-app.git'
        copytree(repo_path, temp_repo_path)
        self.origin = Repo(temp_repo_path)
        self.clone = self.origin.clone(mkdtemp(prefix='bizarro-'))

        self.session = dict(email=str(uuid4()))

        environ['GIT_AUTHOR_NAME'] = ' '
        environ['GIT_COMMITTER_NAME'] = ' '
        environ['GIT_AUTHOR_EMAIL'] = self.session['email']
        environ['GIT_COMMITTER_EMAIL'] = self.session['email']

    def tearDown(self):
        rmtree(self.origin.git_dir)
        rmtree(self.clone.working_dir)

    def test_sorted_paths(self):
        ''' Ensure files/directories are sorted in alphabetical order
        '''
        sorted_list = view_functions.sorted_paths(self.clone, 'master')
        expected_list = [('index.md', '/tree/master/view/index.md', 'file', True),
                         ('other', '/tree/master/view/other', 'folder', False),
                         ('other.md', '/tree/master/view/other.md', 'file', True),
                         ('sub', '/tree/master/view/sub', 'folder', False)]
        self.assertEqual(sorted_list, expected_list)

    def test_directory_paths_with_no_relative_path(self):
        ''' Ensure that a list with pairs of a sub-directory and the absolute path
            to that directory is returned for all sub-directories in a path
        '''
        dirs_and_paths = view_functions.directory_paths('my-branch')
        self.assertEqual(dirs_and_paths, [('root', '/tree/my-branch/edit')])

    def test_directory_paths_with_relative_path(self):
        ''' Ensure that a list with pairs of a sub-directory and the absolute path
            to that directory is returned for all sub-directories in a path
        '''
        dirs_and_paths = view_functions.directory_paths('my-branch', 'blah/foo/')
        self.assertEqual(dirs_and_paths, [('root', '/tree/my-branch/edit'),
                                          ('blah', '/tree/my-branch/edit/blah/'),
                                          ('foo', '/tree/my-branch/edit/blah/foo/')])

class TestRepo (TestCase):

    def setUp(self):
        repo_path = os.path.dirname(os.path.abspath(__file__)) + '/test-app.git'
        temp_repo_dir = mkdtemp(prefix='bizarro-root')
        temp_repo_path = temp_repo_dir + '/test-app.git'
        copytree(repo_path, temp_repo_path)
        self.origin = Repo(temp_repo_path)

        self.clone1 = self.origin.clone(mkdtemp(prefix='bizarro-'))
        self.clone2 = self.origin.clone(mkdtemp(prefix='bizarro-'))

        self.session = dict(email=str(uuid4()))

        environ['GIT_AUTHOR_NAME'] = ' '
        environ['GIT_COMMITTER_NAME'] = ' '
        environ['GIT_AUTHOR_EMAIL'] = self.session['email']
        environ['GIT_COMMITTER_EMAIL'] = self.session['email']

    def tearDown(self):
        rmtree(self.origin.git_dir)
        rmtree(self.clone1.working_dir)
        rmtree(self.clone2.working_dir)

    def test_repo_features(self):
        self.assertTrue(self.origin.bare)

        branch_names = [b.name for b in self.origin.branches]
        self.assertEqual(set(branch_names), set(['master', 'title', 'body']))

    def test_start_branch(self):
        ''' Make a simple edit in a clone, verify that it appears in the other.
        '''
        name = str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', name)

        self.assertTrue(name in self.clone1.branches)
        self.assertTrue(name in self.origin.branches)

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
        branch2 = repo_functions.start_branch(self.clone2, 'master', name)

        self.assertTrue(name in self.clone2.branches)
        self.assertEquals(branch2.commit.hexsha, branch1.commit.hexsha)
        self.assertEquals(branch2.commit.message, message)

    def test_start_branch_2(self):
        ''' Make a simple edit in a clone, verify that it appears in the other.
        '''
        name = str(uuid4())

        #
        # Check out both clones.
        #
        self.clone1.branches.master.checkout()
        self.clone2.branches.master.checkout()

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
        self.assertEquals(self.clone1.refs['master'].commit.hexsha, self.origin.refs['master'].commit.hexsha)
        self.assertNotEquals(self.clone1.refs['master'].commit.hexsha, self.clone2.refs['master'].commit.hexsha)

        #
        # Now start a branch from the second clone, and look for the new master commit.
        #
        branch2 = repo_functions.start_branch(self.clone2, 'master', name)

        self.assertTrue(name in self.clone2.branches)
        self.assertEquals(branch2.commit.hexsha, self.origin.refs['master'].commit.hexsha)

    def test_delete_missing_branch(self):
        ''' Delete a branch in a clone that's still in origin, see if it can be deleted anyway.
        '''
        name = str(uuid4())

        branch1 = repo_functions.start_branch(self.clone1, 'master', name)

        self.assertTrue(name in self.origin.branches)

        self.clone2.git.fetch()

        repo_functions.abandon_branch(self.clone2, 'master', name)

        self.assertFalse(name in self.origin.branches)
        self.assertFalse(name in self.clone2.branches)
        self.assertFalse('origin/' + name in self.clone2.refs)

    def test_new_file(self):
        ''' Make a new file and delete an old file in a clone, verify that it appears in the other.
        '''
        name = str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', name)

        self.assertTrue(name in self.clone1.branches)
        self.assertTrue(name in self.origin.branches)

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

        edit_functions.delete_file(self.clone1, '', 'index.md')

        args = self.clone1, 'index.md', message, branch1.commit.hexsha, 'master'
        repo_functions.save_working_file(*args)

        #
        # See if the branch made it to clone 2
        #
        branch2 = repo_functions.start_branch(self.clone2, 'master', name)

        self.assertTrue(name in self.clone2.branches)
        self.assertEquals(branch2.commit.hexsha, branch1.commit.hexsha)
        self.assertEquals(branch2.commit.message, message)
        self.assertEquals(branch2.commit.author.email, self.session['email'])
        self.assertEquals(branch2.commit.committer.email, self.session['email'])

        branch2.checkout()

        with open(join(self.clone2.working_dir, 'hello.md')) as file:
            front, body = jekyll_functions.load_jekyll_doc(file)

            self.assertEquals(front['title'], 'Hello')
            self.assertEquals(body, 'Hello hello.')

        self.assertFalse(exists(join(self.clone2.working_dir, 'index.md')))

    def test_delete_directory(self):
        ''' Make a new file and directory and delete them.
        '''
        name = str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', name)

        self.assertTrue(name in self.clone1.branches)
        self.assertTrue(name in self.origin.branches)

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

        edit_functions.delete_file(self.clone1, 'hello/', 'hello.md')

        args = self.clone1, 'hello/hello.md', message, branch1.commit.hexsha, 'master'
        repo_functions.save_working_file(*args)

        self.assertFalse(exists(join(self.clone1.working_dir, 'hello/hello.md')))

        edit_functions.delete_file(self.clone1, 'hello/', '')

        self.assertFalse(exists(join(self.clone1.working_dir, 'hello/')))

    def test_move_file(self):
        ''' Change the path of a file.
        '''
        name = str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', name)

        self.assertTrue(name in self.clone1.branches)
        self.assertTrue(name in self.origin.branches)

        #
        # Rename a file in the branch.
        #
        branch1.checkout()

        args = self.clone1, 'index.md', 'hello/world.md', branch1.commit.hexsha, 'master'
        repo_functions.move_existing_file(*args)

        #
        # See if the new file made it to clone 2
        #
        branch2 = repo_functions.start_branch(self.clone2, 'master', name)
        branch2.checkout()

        self.assertTrue(exists(join(self.clone2.working_dir, 'hello/world.md')))
        self.assertFalse(exists(join(self.clone2.working_dir, 'index.md')))

    def test_content_merge(self):
        ''' Test that non-conflicting changes on the same file merge cleanly.
        '''
        branch1 = repo_functions.start_branch(self.clone1, 'master', 'title')
        branch2 = repo_functions.start_branch(self.clone2, 'master', 'body')

        branch1.checkout()
        branch2.checkout()

        with open(self.clone1.working_dir + '/index.md') as file:
            front1, _ = jekyll_functions.load_jekyll_doc(file)

        with open(self.clone2.working_dir + '/index.md') as file:
            _, body2 = jekyll_functions.load_jekyll_doc(file)

        #
        # Show that only the title branch title is now present on master.
        #
        repo_functions.complete_branch(self.clone1, 'master', 'title')

        with open(self.clone1.working_dir + '/index.md') as file:
            front1b, body1b = jekyll_functions.load_jekyll_doc(file)

        self.assertEqual(front1b['title'], front1['title'])
        self.assertNotEqual(body1b, body2)

        #
        # Show that the body branch body is also now present on master.
        #
        repo_functions.complete_branch(self.clone2, 'master', 'body')

        with open(self.clone2.working_dir + '/index.md') as file:
            front2b, body2b = jekyll_functions.load_jekyll_doc(file)

        self.assertEqual(front2b['title'], front1['title'])
        self.assertEqual(body2b, body2)
        self.assertTrue(self.clone2.commit().message.startswith('Merged work from'))

    def test_content_merge_extra_change(self):
        ''' Test that non-conflicting changes on the same file merge cleanly.
        '''
        branch1 = repo_functions.start_branch(self.clone1, 'master', 'title')
        branch2 = repo_functions.start_branch(self.clone2, 'master', 'body')

        branch1.checkout()
        branch2.checkout()

        with open(self.clone1.working_dir + '/index.md') as file:
            front1, _ = jekyll_functions.load_jekyll_doc(file)

        with open(self.clone2.working_dir + '/index.md') as file:
            front2, body2 = jekyll_functions.load_jekyll_doc(file)

        #
        # Show that only the title branch title is now present on master.
        #
        repo_functions.complete_branch(self.clone1, 'master', 'title')

        with open(self.clone1.working_dir + '/index.md') as file:
            front1b, body1b = jekyll_functions.load_jekyll_doc(file)

        self.assertEqual(front1b['title'], front1['title'])
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

        self.assertEqual(front2b['title'], front1['title'])
        self.assertEqual(body2b.strip(), 'Another change to the body')
        self.assertTrue(self.clone2.commit().message.startswith('Merged work from'))

    def test_multifile_merge(self):
        ''' Test that two non-conflicting new files merge cleanly.
        '''
        name = str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', name)
        branch2 = repo_functions.start_branch(self.clone2, 'master', name)

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

        self.assertEquals(self.origin.branches[name].commit, commit1)
        self.assertEquals(self.origin.branches[name].commit.author.email, self.session['email'])
        self.assertEquals(self.origin.branches[name].commit.committer.email, self.session['email'])
        self.assertEquals(commit1, branch1.commit)

        #
        # Show that the changes from the second branch also made it to origin.
        #
        args2 = self.clone2, 'file2.md', '...', branch2.commit.hexsha, 'master'
        commit2 = repo_functions.save_working_file(*args2)

        self.assertEquals(self.origin.branches[name].commit, commit2)
        self.assertEquals(self.origin.branches[name].commit.author.email, self.session['email'])
        self.assertEquals(self.origin.branches[name].commit.committer.email, self.session['email'])
        self.assertEquals(commit2, branch2.commit)

        #
        # Show that the merge from the second branch made it back to the first.
        #
        branch1b = repo_functions.start_branch(self.clone1, 'master', name)

        self.assertEquals(branch1b.commit, branch2.commit)
        self.assertEquals(branch1b.commit.author.email, self.session['email'])
        self.assertEquals(branch1b.commit.committer.email, self.session['email'])

    def test_same_branch_conflict(self):
        ''' Test that a conflict in two branches appears at the right spot.
        '''
        name = str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', name)
        branch2 = repo_functions.start_branch(self.clone2, 'master', name)

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

        self.assertEquals(self.origin.branches[name].commit, commit1)
        self.assertEquals(commit1, branch1.commit)

        #
        # Show that the changes from the second branch conflict with the first.
        #
        with self.assertRaises(repo_functions.MergeConflict) as conflict:
            args2 = self.clone2, 'conflict.md', '...', branch2.commit.hexsha, 'master'
            commit2 = repo_functions.save_working_file(*args2)

        self.assertEqual(conflict.exception.remote_commit, commit1)

        diffs = conflict.exception.remote_commit.diff(conflict.exception.local_commit)

        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].a_blob.name, 'conflict.md')
        self.assertEqual(diffs[0].b_blob.name, 'conflict.md')

    def test_upstream_pull_conflict(self):
        ''' Test that a conflict in two branches appears at the right spot.
        '''
        name1, name2 = str(uuid4()), str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', name1)
        branch2 = repo_functions.start_branch(self.clone2, 'master', name2)

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

        self.assertEquals(self.origin.branches[name1].commit, commit1)
        self.assertEquals(commit1, branch1.commit)

        #
        # Merge the first branch to master.
        #
        commit2 = repo_functions.complete_branch(self.clone1, 'master', name1)
        self.assertFalse(name1 in self.origin.branches)

        #
        # Show that the changes from the second branch conflict with the first.
        #
        with self.assertRaises(repo_functions.MergeConflict) as conflict:
            args2 = self.clone2, 'conflict.md', '...', branch2.commit.hexsha, 'master'
            repo_functions.save_working_file(*args2)

        self.assertEqual(conflict.exception.remote_commit, commit2)

        diffs = conflict.exception.remote_commit.diff(conflict.exception.local_commit)

        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].a_blob.name, 'conflict.md')
        self.assertEqual(diffs[0].b_blob.name, 'conflict.md')

    def test_upstream_push_conflict(self):
        ''' Test that a conflict in two branches appears at the right spot.
        '''
        name1, name2 = str(uuid4()), str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', name1)
        branch2 = repo_functions.start_branch(self.clone2, 'master', name2)

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
        commit1 = repo_functions.save_working_file(*args1)

        args2 = self.clone2, 'conflict.md', '...', branch2.commit.hexsha, 'master'
        commit2 = repo_functions.save_working_file(*args2)

        #
        # Merge the two branches to master; show that second merge will fail.
        #
        repo_functions.complete_branch(self.clone1, 'master', name1)
        self.assertFalse(name1 in self.origin.branches)

        with self.assertRaises(repo_functions.MergeConflict) as conflict:
            repo_functions.complete_branch(self.clone2, 'master', name2)

        self.assertEqual(conflict.exception.remote_commit, self.origin.commit())
        self.assertEqual(conflict.exception.local_commit, self.clone2.commit())

        diffs = conflict.exception.remote_commit.diff(conflict.exception.local_commit)

        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].a_blob.name, 'conflict.md')
        self.assertEqual(diffs[0].b_blob.name, 'conflict.md')

    def test_conflict_resolution_clobber(self):
        ''' Test that a conflict in two branches can be clobbered.
        '''
        name = str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', 'title')
        branch2 = repo_functions.start_branch(self.clone2, 'master', name)

        #
        # Add goner.md in branch1.
        #
        branch1.checkout()

        edit_functions.create_new_page(self.clone1, '', 'goner.md',
                                       dict(title=name), 'Woooo woooo.')

        args = self.clone1, 'goner.md', '...', branch1.commit.hexsha, 'master'
        commit = repo_functions.save_working_file(*args)

        #
        # Change index.md in branch2 so it conflicts with title branch.
        #
        branch2.checkout()

        edit_functions.update_page(self.clone2, 'index.md',
                                   dict(title=name), 'Hello hello.')

        args = self.clone2, 'index.md', '...', branch2.commit.hexsha, 'master'
        commit = repo_functions.save_working_file(*args)

        #
        # Merge the original title branch, fail to merge our conflicting branch.
        #
        repo_functions.complete_branch(self.clone1, 'master', 'title')

        with self.assertRaises(repo_functions.MergeConflict) as conflict:
            repo_functions.complete_branch(self.clone2, 'master', name)

        self.assertEqual(conflict.exception.local_commit, commit)

        diffs = conflict.exception.remote_commit.diff(conflict.exception.local_commit)

        self.assertEqual(len(diffs), 2)
        self.assertTrue(diffs[0].a_blob.name in ('index.md', 'goner.md'))
        self.assertTrue(diffs[1].a_blob.name in ('index.md', 'goner.md'))

        #
        # Merge our conflicting branch and clobber the default branch.
        #
        repo_functions.clobber_default_branch(self.clone2, 'master', name)

        with open(join(self.clone2.working_dir, 'index.md')) as file:
            front, body = jekyll_functions.load_jekyll_doc(file)

        self.assertEqual(front['title'], name)
        self.assertFalse(name in self.origin.branches)

        # If goner.md is still around, then master wasn't fully clobbered.
        self.clone1.branches['master'].checkout()
        self.clone1.git.pull('origin', 'master')
        self.assertFalse(exists(join(self.clone2.working_dir, 'goner.md')))
        self.assertTrue(self.clone2.commit().message.startswith('Clobbered with work from'))

    def test_conflict_resolution_abandon(self):
        ''' Test that a conflict in two branches can be abandoned.
        '''
        name = str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', 'title')
        branch2 = repo_functions.start_branch(self.clone2, 'master', name)

        #
        # Change index.md in branch2 so it conflicts with title branch.
        # Also add goner.md, which we'll later want to disappear.
        #
        branch2.checkout()

        edit_functions.update_page(self.clone2, 'index.md',
                                   dict(title=name), 'Hello hello.')

        edit_functions.create_new_page(self.clone2, '', 'goner.md',
                                       dict(title=name), 'Woooo woooo.')

        args = self.clone2, 'index.md', '...', branch2.commit.hexsha, 'master'
        commit = repo_functions.save_working_file(*args)

        args = self.clone2, 'goner.md', '...', branch2.commit.hexsha, 'master'
        commit = repo_functions.save_working_file(*args)

        #
        # Merge the original title branch, fail to merge our conflicting branch.
        #
        repo_functions.complete_branch(self.clone1, 'master', 'title')

        with self.assertRaises(repo_functions.MergeConflict) as conflict:
            repo_functions.complete_branch(self.clone2, 'master', name)

        self.assertEqual(conflict.exception.local_commit, commit)

        diffs = conflict.exception.remote_commit.diff(conflict.exception.local_commit)

        self.assertEqual(len(diffs), 2)
        self.assertTrue(diffs[0].b_blob.name in ('index.md', 'goner.md'))
        self.assertTrue(diffs[1].b_blob.name in ('index.md', 'goner.md'))

        #
        # Merge our conflicting branch and abandon it to the default branch.
        #
        repo_functions.abandon_branch(self.clone2, 'master', name)

        with open(join(self.clone2.working_dir, 'index.md')) as file:
            front, body = jekyll_functions.load_jekyll_doc(file)

        self.assertNotEqual(front['title'], name)
        self.assertFalse(name in self.origin.branches)

        # If goner.md is still around, then the branch wasn't fully abandoned.
        self.assertFalse(exists(join(self.clone2.working_dir, 'goner.md')))
        self.assertTrue(self.clone2.commit().message.startswith('Abandoned work from'))

    def test_peer_review(self):
        ''' Change the path of a file.
        '''
        name = str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', name)

        #
        # Make a commit.
        #
        environ['GIT_AUTHOR_NAME'] = 'Jim Content Creator'
        environ['GIT_COMMITTER_NAME'] = 'Jim Content Creator'
        environ['GIT_AUTHOR_EMAIL'] = 'creator@example.com'
        environ['GIT_COMMITTER_EMAIL'] = 'creator@example.com'

        branch1.checkout()
        self.assertFalse(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_approved(self.clone1, 'master', name))

        edit_functions.update_page(self.clone1, 'index.md',
                                   dict(title=name), 'Hello you-all.')

        repo_functions.save_working_file(self.clone1, 'index.md', 'I made a change',
                                         self.clone1.commit().hexsha, 'master')

        self.assertTrue(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_approved(self.clone1, 'master', name))
        self.assertEqual(repo_functions.ineligible_peer(self.clone1, 'master', name), 'creator@example.com')

        #
        # Approve the work as someone else.
        #
        environ['GIT_AUTHOR_NAME'] = 'Joe Reviewer'
        environ['GIT_COMMITTER_NAME'] = 'Joe Reviewer'
        environ['GIT_AUTHOR_EMAIL'] = 'reviewer@example.com'
        environ['GIT_COMMITTER_EMAIL'] = 'reviewer@example.com'

        repo_functions.mark_as_reviewed(self.clone1)

        self.assertFalse(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertTrue(repo_functions.is_peer_approved(self.clone1, 'master', name))
        self.assertEqual(repo_functions.ineligible_peer(self.clone1, 'master', name), None)

        #
        # Make another commit.
        #
        edit_functions.update_page(self.clone1, 'index.md',
                                   dict(title=name), 'Hello you there.')

        repo_functions.save_working_file(self.clone1, 'index.md', 'I made a change',
                                         self.clone1.commit().hexsha, 'master')

        self.assertTrue(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_approved(self.clone1, 'master', name))
        self.assertEqual(repo_functions.ineligible_peer(self.clone1, 'master', name), 'reviewer@example.com')

        #
        # Approve the work as someone else.
        #
        environ['GIT_AUTHOR_NAME'] = 'Jane Reviewer'
        environ['GIT_COMMITTER_NAME'] = 'Jane Reviewer'
        environ['GIT_AUTHOR_EMAIL'] = 'reviewer@example.org'
        environ['GIT_COMMITTER_EMAIL'] = 'reviewer@example.org'

        repo_functions.mark_as_reviewed(self.clone1)

        self.assertFalse(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertTrue(repo_functions.is_peer_approved(self.clone1, 'master', name))
        self.assertEqual(repo_functions.ineligible_peer(self.clone1, 'master', name), None)

    def test_peer_rejected(self):
        '''
        '''
        name = str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', name)

        #
        # Make a commit.
        #
        environ['GIT_AUTHOR_NAME'] = 'Jim Content Creator'
        environ['GIT_COMMITTER_NAME'] = 'Jim Content Creator'
        environ['GIT_AUTHOR_EMAIL'] = 'creator@example.com'
        environ['GIT_COMMITTER_EMAIL'] = 'creator@example.com'

        branch1.checkout()
        self.assertFalse(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_approved(self.clone1, 'master', name))

        edit_functions.update_page(self.clone1, 'index.md',
                                   dict(title=name), 'Hello you-all.')

        repo_functions.save_working_file(self.clone1, 'index.md', 'I made a change',
                                         self.clone1.commit().hexsha, 'master')

        self.assertTrue(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_approved(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_rejected(self.clone1, 'master', name))
        self.assertEqual(repo_functions.ineligible_peer(self.clone1, 'master', name), 'creator@example.com')

        #
        # Approve the work as someone else.
        #
        environ['GIT_AUTHOR_NAME'] = 'Joe Reviewer'
        environ['GIT_COMMITTER_NAME'] = 'Joe Reviewer'
        environ['GIT_AUTHOR_EMAIL'] = 'reviewer@example.com'
        environ['GIT_COMMITTER_EMAIL'] = 'reviewer@example.com'

        repo_functions.provide_feedback(self.clone1, 'This sucks.')

        self.assertFalse(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_approved(self.clone1, 'master', name))
        self.assertTrue(repo_functions.is_peer_rejected(self.clone1, 'master', name))
        self.assertEqual(repo_functions.ineligible_peer(self.clone1, 'master', name), None)

        #
        # Make another commit.
        #
        edit_functions.update_page(self.clone1, 'index.md',
                                   dict(title=name), 'Hello you there.')

        repo_functions.save_working_file(self.clone1, 'index.md', 'I made a change',
                                         self.clone1.commit().hexsha, 'master')

        self.assertTrue(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_approved(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_rejected(self.clone1, 'master', name))
        self.assertEqual(repo_functions.ineligible_peer(self.clone1, 'master', name), 'reviewer@example.com')

        #
        # Approve the work as someone else.
        #
        environ['GIT_AUTHOR_NAME'] = 'Jane Reviewer'
        environ['GIT_COMMITTER_NAME'] = 'Jane Reviewer'
        environ['GIT_AUTHOR_EMAIL'] = 'reviewer@example.org'
        environ['GIT_COMMITTER_EMAIL'] = 'reviewer@example.org'

        repo_functions.provide_feedback(self.clone1, 'This still sucks.')

        self.assertFalse(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_approved(self.clone1, 'master', name))
        self.assertTrue(repo_functions.is_peer_rejected(self.clone1, 'master', name))
        self.assertEqual(repo_functions.ineligible_peer(self.clone1, 'master', name), None)

        #

        (email2, message2), (email1, message1) = repo_functions.get_rejection_messages(self.clone1, 'master', name)

        self.assertEqual(email1, 'reviewer@example.com')
        self.assertTrue('This sucks.' in message1)
        self.assertEqual(email2, 'reviewer@example.org')
        self.assertTrue('This still sucks.' in message2)

''' Test functions that are called outside of the google authing/analytics data fetching via the UI
'''
class TestGoogleApiFunctions (TestCase):

    def setUp(self):
        app_args = {}
        app_args['GA_CLIENT_ID'] = 'client_id'
        app_args['GA_CLIENT_SECRET'] = 'meow_secret'

        self.ga_config_dir = mkdtemp(prefix='bizarro-config-')
        app_args['RUNNING_STATE_DIR'] = self.ga_config_dir
        app_args['CONFIG_PATH'] = self.ga_config_dir

        self.app = create_app(app_args)

        ga_config_path = join(self.ga_config_dir, google_api_functions.GA_CONFIG_FILENAME)

        # write a tmp config file
        ga_config = {
            "access_token": "meowser_token",
            "refresh_token": "refresh_meows",
            "profile_id": "12345678",
            "project_domain": ""
        }
        with view_functions.WriteLocked(ga_config_path) as outfile:
            outfile.truncate(0)
            json.dump(ga_config, outfile, indent=2, ensure_ascii=False)

    def tearDown(self):
        rmtree(self.ga_config_dir)

    def mock_successful_request_new_google_access_token(self, url, request):
        if 'https://accounts.google.com/o/oauth2/token' in url.geturl():
            content = {'access_token': 'meowser_access_token', 'token_type': 'meowser_type', 'expires_in': 3920,}
            return response(200, content)

        else:
            raise Exception('01 Asked for unknown URL ' + url.geturl())

    def mock_failed_request_new_google_access_token(self, url, request):
        if 'https://accounts.google.com/o/oauth2/token' in url.geturl():
            return response(500)

        else:
            raise Exception('02 Asked for unknown URL ' + url.geturl())

    def mock_google_analytics_authorized_response(self, url, request):
        if 'https://www.googleapis.com/analytics/' in url.geturl():
            content = {u'totalsForAllResults': {u'ga:pageViews': u'24', u'ga:avgTimeOnPage': u'67.36363636363636'}}
            return response(200, content)

    def mock_google_analytics_unauthorized_response(self, url, request):
        if 'https://www.googleapis.com/analytics/' in url.geturl():
            content = {u'error': {u'code': 401, u'message': u'Invalid Credentials', u'errors': [{u'locationType': u'header', u'domain': u'global', u'message': u'Invalid Credentials', u'reason': u'authError', u'location': u'Authorization'}]}}
            return response(401, content)

    def test_successful_request_new_google_access_token(self):
        with self.app.test_request_context():
            with HTTMock(self.mock_successful_request_new_google_access_token):
                google_api_functions.request_new_google_access_token('meowser_refresh_token')

                ga_config_path = os.path.join(self.app.config['RUNNING_STATE_DIR'], google_api_functions.GA_CONFIG_FILENAME)
                with view_functions.ReadLocked(ga_config_path) as infile:
                    ga_config = json.load(infile)

                self.assertEqual(ga_config['access_token'], 'meowser_access_token')

    def test_failure_to_request_new_google_access_token(self):
        with self.app.test_request_context():
            with HTTMock(self.mock_failed_request_new_google_access_token):
                with self.assertRaises(Exception):
                    google_api_functions.request_new_google_access_token('meowser_refresh_token')

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

    def test_handle_good_analytics_response(self):
        ''' Verify that an authorized analytics response is handled correctly
        '''
        with HTTMock(self.mock_google_analytics_authorized_response):
            analytics_dict = google_api_functions.fetch_google_analytics_for_page(self.app.config, u'index.html', 'meowser_token')
            self.assertEqual(analytics_dict['page_views'], u'24')
            self.assertEqual(analytics_dict['average_time_page'], u'67')

    def test_handle_bad_analytics_response(self):
        ''' Verify that an unauthorized analytics response is handled correctly
        '''
        with HTTMock(self.mock_google_analytics_unauthorized_response):
            analytics_dict = google_api_functions.fetch_google_analytics_for_page(self.app.config, u'index.html', 'meowser_token')
            self.assertEqual(analytics_dict, {})

class TestAppConfig (TestCase):

    def test_missing_values(self):
        self.assertRaises(KeyError, lambda: create_app({}))

    def test_present_values(self):
        app_config = {}
        app_config['RUNNING_STATE_DIR'] = 'Yo'
        app_config['GA_CLIENT_ID'] = 'Yo'
        app_config['GA_CLIENT_SECRET'] = 'Yo'
        create_app(app_config)

class TestApp (TestCase):

    def setUp(self):
        self.work_path = mkdtemp(prefix='bizarro-repo-clones-')

        repo_path = os.path.dirname(os.path.abspath(__file__)) + '/test-app.git'
        self.temp_repo_dir = mkdtemp(prefix='bizarro-root')
        temp_repo_path = self.temp_repo_dir + '/test-app.git'
        copytree(repo_path, temp_repo_path)

        app_args = {}

        app_args['GA_CLIENT_ID'] = 'client_id'
        app_args['GA_CLIENT_SECRET'] = 'meow_secret'

        self.ga_config_dir = mkdtemp(prefix='bizarro-config-')
        app_args['CONFIG_PATH'] = self.ga_config_dir
        app_args['RUNNING_STATE_DIR'] = self.ga_config_dir
        app_args['WORK_PATH'] = self.work_path
        app_args['REPO_PATH'] = temp_repo_path

        ga_config_path = join(self.ga_config_dir, google_api_functions.GA_CONFIG_FILENAME)

        app = create_app(app_args)

        # write a tmp config file
        ga_config = {
            "access_token": "meowser_token",
            "refresh_token": "refresh_meows",
            "profile_id": "12345678",
            "project_domain": ""
        }
        with view_functions.WriteLocked(ga_config_path) as outfile:
            outfile.truncate(0)
            json.dump(ga_config, outfile, indent=2, ensure_ascii=False)

        random.choice = MagicMock(return_value="P")

        self.server = app.test_client()
        self.app = app

    def tearDown(self):
        rmtree(self.work_path)
        rmtree(self.temp_repo_dir)
        rmtree(self.ga_config_dir)

    def mock_persona_verify(self, url, request):
        if url.geturl() == 'https://verifier.login.persona.org/verify':
            return response(200, '''{"status": "okay", "email": "user@example.com"}''', headers=dict(Link='<https://api.github.com/user/337792/repos?page=1>; rel="prev", <https://api.github.com/user/337792/repos?page=1>; rel="first"'))

        else:
            raise Exception('03 Asked for unknown URL ' + url.geturl())

    def mock_google_authorization(self, url, request):
        if 'https://accounts.google.com/o/oauth2/auth' in url.geturl():
            content = {'access_token': 'meowser_token', 'token_type': 'meowser_type', 'refresh_token': 'refresh_meows', 'expires_in': 3920,}
            return response(200, content)

        else:
            raise Exception('04 Asked for unknown URL ' + url.geturl())

    def mock_successful_google_callback(self, url, request):
        if 'https://accounts.google.com/o/oauth2/token' in url.geturl():
            content = {'access_token': 'meowser_token', 'token_type': 'meowser_type', 'refresh_token': 'refresh_meows', 'expires_in': 3920,}
            return response(200, content)

        else:
            raise Exception('05 Asked for unknown URL ' + url.geturl())

    def mock_failed_google_callback(self, url, request):
        if 'https://accounts.google.com/o/oauth2/token' in url.geturl():
            return response(500)

        else:
            raise Exception('06 Asked for unknown URL ' + url.geturl())

    def mock_google_analytics(self, url, request):
        start_date = (date.today() - timedelta(days=7)).isoformat()
        end_date = date.today().isoformat()
        url_string = url.geturl()

        if 'ids=ga%3A12345678' in url_string and 'end-date=' + end_date in url_string and 'start-date=' + start_date in url_string and 'filters=ga%3ApagePath%3D~%28hello.html%7Chello%29' in url_string:
            return response(200, '''{"ga:previousPagePath": "/about/", "ga:pagePath": "/lib/", "ga:pageViews": "12", "ga:avgTimeOnPage": "56.17", "ga:exiteRate": "43.75", "totalsForAllResults": {"ga:pageViews": "24", "ga:avgTimeOnPage": "67.36363636363636"}}''')

        else:
            raise Exception('07 Asked for unknown URL ' + url.geturl())

    def test_login(self):
        ''' Check basic log in / log out flow without talking to Persona.
        '''
        response = self.server.get('/')
        self.assertFalse('user@example.com' in response.data)

        with HTTMock(self.mock_persona_verify):
            response = self.server.post('/sign-in', data={'email': 'user@example.com'})
            self.assertEquals(response.status_code, 200)

        response = self.server.get('/')
        self.assertTrue('user@example.com' in response.data)

        response = self.server.post('/sign-out')
        self.assertEquals(response.status_code, 200)

        response = self.server.get('/')
        self.assertFalse('user@example.com' in response.data)

    def test_branches(self):
        ''' Check basic branching functionality.
        '''
        with HTTMock(self.mock_persona_verify):
            self.server.post('/sign-in', data={'email': 'user@example.com'})

        response = self.server.post('/start', data={'branch': 'do things'},
                                    follow_redirects=True)
        self.assertTrue('user@example.com/do-things' in response.data)

        with HTTMock(self.mock_google_analytics):
            response = self.server.post('/tree/user@example.com%252Fdo-things/edit/',
                                        data={'action': 'add', 'path': 'hello.html'},
                                        follow_redirects=True)

            self.assertEquals(response.status_code, 200)

            response = self.server.get('/tree/user@example.com%252Fdo-things/edit/')

            self.assertTrue('hello.html' in response.data)

            response = self.server.get('/tree/user@example.com%252Fdo-things/edit/hello.html')
            hexsha = search(r'<input name="hexsha" value="(\w+)"', response.data).group(1)

            response = self.server.post('/tree/user@example.com%252Fdo-things/save/hello.html',
                                        data={'layout': 'multi', 'hexsha': hexsha,
                                              'en-title': 'Greetings', 'en-body': 'Hello world.\n',
                                              'fr-title': '', 'fr-body': '',
                                              'url-slug': 'hello'},
                                        follow_redirects=True)

            self.assertEquals(response.status_code, 200)

        html = response.data

        # Check that English and French forms are both present.
        self.assertTrue('id="fr-nav" class="nav-tab"' in html)
        self.assertTrue('id="en-nav" class="nav-tab state-active"' in html)
        self.assertTrue('id="French-form" style="display: none"' in html)
        self.assertTrue('id="English-form" style="display: block"' in html)

        # Verify that navigation tabs are in the correct order.
        self.assertTrue(html.index('id="fr-nav"') < html.index('id="en-nav"'))

    def test_google_callback_is_successful(self):
        ''' Ensure we are redirected to the authorize-complete page
            when we successfully auth with google
        '''
        with HTTMock(self.mock_persona_verify):
            self.server.post('/sign-in', data={'email': 'erica@example.com'})

        with HTTMock(self.mock_google_authorization):
            self.server.post('/authorize')

        with HTTMock(self.mock_successful_google_callback):
            response = self.server.get('/callback?state=PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP&code=code')

        ga_config_path = os.path.join(self.app.config['RUNNING_STATE_DIR'], google_api_functions.GA_CONFIG_FILENAME)
        with view_functions.ReadLocked(ga_config_path) as infile:
            ga_config = json.load(infile)

        self.assertEqual(ga_config['access_token'], 'meowser_token')
        self.assertEqual(ga_config['refresh_token'], 'refresh_meows')

        print dir(response)
        print response.location
        print response.data
        print response.get_wsgi_response()

        self.assertTrue('authorization-complete' in response.location)

    def test_google_callback_fails(self):
        ''' Ensure we are redirected to the authorize-failed page
            when we fail to auth with google
        '''
        with HTTMock(self.mock_persona_verify):
            self.server.post('/sign-in', data={'email': 'erica@example.com'})

        with HTTMock(self.mock_google_authorization):
            self.server.post('/authorize')

        with HTTMock(self.mock_failed_google_callback):
            response = self.server.get('/callback?state=PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP&code=code')

        self.assertTrue('authorization-failed' in response.location)

if __name__ == '__main__':
    main()
