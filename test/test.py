# -- coding: utf-8 --
from flask import Flask, session
from unittest import main, TestCase

from tempfile import mkdtemp
from StringIO import StringIO
from subprocess import Popen, PIPE
from os.path import join, exists
from os import environ, unlink
from shutil import rmtree, copytree
from uuid import uuid4
from re import search
import random
from json import loads
from datetime import date, timedelta

import sys, os
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(here)

from git import Repo
from box.util.rotunicode import RotUnicode
from httmock import response, HTTMock
from mock import MagicMock

from bizarro import app, jekyll_functions, repo_functions, edit_functions, google_api_functions, view_functions

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
        self.assertEqual(dirs_and_paths, [('root', '/tree/my-branch/edit'), ('blah', '/tree/my-branch/edit/blah/'), ('foo', '/tree/my-branch/edit/blah/foo/')])

    def tearDown(self):
        rmtree(self.origin.git_dir)
        rmtree(self.clone.working_dir)


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

    def tearDown(self):
        rmtree(self.origin.git_dir)
        rmtree(self.clone1.working_dir)
        rmtree(self.clone2.working_dir)

''' Test functions that are called outside of the google authing/analytics data fetching via the UI
'''
class TestGoogleApiFunctions (TestCase):

    def setUp(self):
        environ['CLIENT_ID'] = 'client_id'
        environ['CLIENT_SECRET'] = 'meow_secret'

    def mock_successful_get_new_access_token(self, url, request):
        if 'https://accounts.google.com/o/oauth2/token' in url.geturl():
            content = {'access_token': 'meowser_token', 'token_type': 'meowser_type', 'expires_in': 3920,}
            return response(200, content)

        else:
            raise Exception('Asked for unknown URL ' + url.geturl())

    def mock_failed_get_new_access_token(self, url, request):
        if 'https://accounts.google.com/o/oauth2/token' in url.geturl():
            return response(500)

        else:
            raise Exception('Asked for unknown URL ' + url.geturl())

    def test_successful_get_new_access_token(self):
        with app.test_request_context():
            with HTTMock(self.mock_successful_get_new_access_token):
                google_api_functions.get_new_access_token('meowsers')
                self.assertEqual(session['access_token'], 'meowser_token')

    def test_failure_to_get_new_access_token(self):
        with app.test_request_context():
            with HTTMock(self.mock_failed_get_new_access_token):
                with self.assertRaises(Exception):
                    google_api_functions.get_new_access_token('meowsers')

class TestApp (TestCase):

    def setUp(self):
        work_path = mkdtemp(prefix='bizarro-repo-clones-')

        repo_path = os.path.dirname(os.path.abspath(__file__)) + '/test-app.git'
        temp_repo_dir = mkdtemp(prefix='bizarro-root')
        temp_repo_path = temp_repo_dir + '/test-app.git'
        copytree(repo_path, temp_repo_path)

        app.config['WORK_PATH'] = work_path
        app.config['REPO_PATH'] = temp_repo_path
        environ['PROFILE_ID'] = '12345678'
        environ['CLIENT_ID'] = 'client_id'
        environ['CLIENT_SECRET'] = 'meow_secret'

        random.choice = MagicMock(return_value="P")

        self.app = app.test_client()

    def tearDown(self):
        rmtree(app.config['WORK_PATH'])
        rmtree(app.config['REPO_PATH'])


    def persona_verify(self, url, request):
        if url.geturl() == 'https://verifier.login.persona.org/verify':
            return response(200, '''{"status": "okay", "email": "user@example.com"}''', headers=dict(Link='<https://api.github.com/user/337792/repos?page=1>; rel="prev", <https://api.github.com/user/337792/repos?page=1>; rel="first"'))

        else:
            raise Exception('Asked for unknown URL ' + url.geturl())

    def mock_google_authorization(self, url, request):
        if 'https://accounts.google.com/o/oauth2/auth' in url.geturl():
            content = {'access_token': 'meowser_token', 'token_type': 'meowser_type', 'refresh_token': 'refresh_meows', 'expires_in': 3920,}
            return response(200, content)

        else:
            raise Exception('Asked for unknown URL ' + url.geturl())

    def mock_successful_google_callback(self, url, request):
        if 'https://accounts.google.com/o/oauth2/token' in url.geturl():
            content = {'access_token': 'meowser_token', 'token_type': 'meowser_type', 'refresh_token': 'refresh_meows', 'expires_in': 3920,}
            return response(200, content)

        else:
            raise Exception('Asked for unknown URL ' + url.geturl())

    def mock_failed_google_callback(self, url, request):
        if 'https://accounts.google.com/o/oauth2/token' in url.geturl():
            return response(500)

        else:
            raise Exception('Asked for unknown URL ' + url.geturl())

    def mock_google_analytics(self, url, request):
        start_date = (date.today() - timedelta(days=7)).isoformat()
        end_date = date.today().isoformat()
        url_string = url.geturl()

        if 'ids=ga%3A12345678' in url_string and 'end-date='+end_date in url_string and 'start-date='+start_date in url_string and 'filters=ga%3ApagePathhello.html' in url_string:
            return response(200, '''{"ga:previousPagePath": "/about/", "ga:pagePath": "/lib/", "ga:pageViews": "12", "ga:avgTimeOnPage": "56.17", "ga:exiteRate": "43.75"}''')

        else:
            raise Exception('Asked for unknown URL ' + url.geturl())

    def test_login(self):
        ''' Check basic log in / log out flow without talking to Persona.
        '''
        response = self.app.get('/')
        self.assertFalse('user@example.com' in response.data)

        with HTTMock(self.persona_verify):
            response = self.app.post('/sign-in', data={'email': 'user@example.com'})
            self.assertEquals(response.status_code, 200)

        response = self.app.get('/')
        self.assertTrue('user@example.com' in response.data)

        response = self.app.post('/sign-out')
        self.assertEquals(response.status_code, 200)

        response = self.app.get('/')
        self.assertFalse('user@example.com' in response.data)

    def test_branches(self):
        ''' Check basic branching functionality.
        '''
        with HTTMock(self.persona_verify):
            self.app.post('/sign-in', data={'email': 'user@example.com'})

        response = self.app.post('/start', data={'branch': 'do things'},
                                 follow_redirects=True)
        self.assertTrue('user@example.com/do-things' in response.data)

        with HTTMock(self.mock_google_analytics):
            response = self.app.post('/tree/user@example.com%252Fdo-things/edit/',
                                     data={'action': 'add', 'path': 'hello.html'},
                                     follow_redirects=True)

            self.assertEquals(response.status_code, 200)

            response = self.app.get('/tree/user@example.com%252Fdo-things/edit/')

            self.assertTrue('hello.html' in response.data)

            response = self.app.get('/tree/user@example.com%252Fdo-things/edit/hello.html')
            hexsha = search(r'<input name="hexsha" value="(\w+)"', response.data).group(1)

            response = self.app.post('/tree/user@example.com%252Fdo-things/save/hello.html',
                                     data={'layout': 'multi', 'hexsha': hexsha,
                                           'en-title': 'Greetings', 'en-body': 'Hello world.\n',
                                           'es-title': '', 'zh-cn-title': '',
                                           'es-body': '', 'zh-cn-body': '',
                                           'url-slug': 'hello'},
                                     follow_redirects=True)

            self.assertEquals(response.status_code, 200)

    def test_google_callback_is_successful(self):
        ''' Ensure we are redirected to the authorize-complete page
            when we successfully auth with google
        '''
        with HTTMock(self.persona_verify):
            self.app.post('/sign-in', data={'email': 'erica@example.com'})

        with HTTMock(self.mock_google_authorization):
            self.app.post('/authorize')

        with HTTMock(self.mock_successful_google_callback):
            response = self.app.get('/callback?state=PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP&code=code')

        self.assertTrue('authorization-complete' in response.location)

    def test_google_callback_fails(self):
        ''' Ensure we are redirected to the authorize-failed page
            when we fail to auth with google
        '''
        with HTTMock(self.persona_verify):
            self.app.post('/sign-in', data={'email': 'erica@example.com'})

        with HTTMock(self.mock_google_authorization):
            self.app.post('/authorize')

        with HTTMock(self.mock_failed_google_callback):
            response = self.app.get('/callback?state=PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP&code=code')

        self.assertTrue('authorization-failed' in response.location)

if __name__ == '__main__':
    main()
