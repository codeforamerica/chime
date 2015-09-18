from subprocess import check_call
from tempfile import mkdtemp
from shutil import rmtree
from os.path import join
from os import mkdir

from git import Actor

from ...repo_functions import MergeConflict
from ...storage.user_task import get_usertask
from unittest import TestCase


Erica = Actor('Erica', 'erica@example.com')
Frances = Actor('Frances', 'frances@example.com')


class TestFirst(TestCase):
    def setUp(self):
        self.working_dirname = mkdtemp(prefix='storage-test-')

        # Make a mostly-empty repo with parking.md file,
        # one master commit, and one branch called task-xyz.

        self.origin_dirname = join(self.working_dirname, 'origin')
        clone_dirname = join(self.working_dirname, 'clone')

        mkdir(self.origin_dirname)
        call_git('--bare init', self.origin_dirname)

        call_git(['clone', self.origin_dirname, clone_dirname])

        call_git('commit -m First --allow-empty', clone_dirname)
        call_git('push origin master', clone_dirname)
        call_git('checkout -b task-xyz', clone_dirname)

        with open(join(clone_dirname, 'parking.md'), 'w') as file:
            file.write('---\nold stuff')

        call_git('add parking.md', clone_dirname)
        call_git('commit -m Second', clone_dirname)
        call_git('push origin task-xyz', clone_dirname)
        rmtree(clone_dirname)

    def tearDown(self):
        pass # rmtree(self.working_dirname)

    def testReadsExistingRepo(self):
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            self.assertEqual(usertask.read('parking.md'), '---\nold stuff')

    def testWriteWithImmediateRead(self):
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            usertask.write('parking.md', "---\nnew stuff")
            self.assertEqual(usertask.read('parking.md'), '---\nnew stuff')

    def testIsAlwaysClean(self):
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            usertask.write('parking.md', "---\nnew stuff")
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            self.assertEqual(usertask.read('parking.md'), '---\nold stuff')

    def testCommitWrite(self):
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            usertask.write('parking.md', "---\nnew stuff")
            usertask.commit("task-xyz", 'I wrote new things')
        with get_usertask(Frances, "task-xyz", self.origin_dirname) as usertask:
            self.assertEqual(usertask.read('parking.md'), '---\nnew stuff')

    def testCommitNewFile(self):
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff")
            usertask.commit("task-xyz", 'I wrote new things')
        with get_usertask(Frances, "task-xyz", self.origin_dirname) as usertask:
            self.assertEqual(usertask.read('jobs.md'), '---\nnew stuff')

    def testResubmitFileEdits(self):
        ''' Simulate a single user's preview, back-button, and re-save.
        '''
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            start_sha = usertask.commit_sha
            usertask.write('jobs.md', "---\nnew stuff")
            usertask.commit("task-xyz", 'I wrote new things')

        with get_usertask(Erica, start_sha, self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff")
            usertask.commit("task-xyz", 'I wrote the same things')

    def testResubmitFileEdits(self):
        ''' Simulate a single user's preview, back-button, and conflicting re-save.
        '''
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n")
            usertask.commit("task-xyz", 'I wrote new things')
            start_sha = usertask.commit_sha

        with get_usertask(Erica, start_sha, self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n\nmore stuff\n")
            usertask.commit("task-xyz", 'I wrote more things')

        with get_usertask(Erica, start_sha, self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n\nmore stuff\n\nfinal stuff\n")
            usertask.commit("task-xyz", 'I wrote final things')

    def testResubmitFileEditsWithInterloper(self):
        ''' Simulate two users' previews, back-buttons, and conflicting re-saves.
        '''
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n")
            usertask.commit("task-xyz", 'I wrote new things')
            start_sha = usertask.commit_sha

        with get_usertask(Frances, start_sha, self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n\nmore stuff\n")
            usertask.commit("task-xyz", 'I wrote more things')

        with get_usertask(Erica, start_sha, self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n\nmore stuff\n\nfinal stuff\n")
            
            # Don't let Erica possibly clobber Frances's changes.
            # Kick this conflict upstairs.
            with self.assertRaises(MergeConflict) as conflict:
                usertask.commit("task-xyz", 'I wrote final things')
            
            self.assertEqual(conflict.exception.local_commit.author, Erica)
            self.assertEqual(conflict.exception.remote_commit.author, Frances)


def call_git(command, working_dir=None):
    if type(command) is list:
        command = ['git'] + command
    elif type(command) is str:
        command = ['git'] + command.split()
    else:
        raise ValueError("unknown type for {}".format(command))

    check_call(command, cwd=working_dir,
               stderr=open('/dev/null', 'w'), stdout=open('/dev/null', 'w'))

# test empty commit
# test create new files
# still needs locking
# merge conflicts
# task deletion
#
