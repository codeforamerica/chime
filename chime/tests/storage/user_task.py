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
        rmtree(self.working_dirname)

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

    def testPublishable(self):
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            usertask.write('parking.md', "---\nnew stuff")
            self.assertIs(usertask.is_publishable("task-xyz"), False)
            usertask.commit('I wrote new things')
            self.assertIs(usertask.is_publishable("task-xyz"), True)
            usertask.publish("task-xyz")
            self.assertIs(usertask.is_publishable("task-xyz"), False)

    def testCommitWrite(self):
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            usertask.write('parking.md', "---\nnew stuff")
            usertask.commit('I wrote new things')
            usertask.publish("task-xyz")
        with get_usertask(Frances, "task-xyz", self.origin_dirname) as usertask:
            self.assertEqual(usertask.read('parking.md'), '---\nnew stuff')
            
            email, date = usertask.ref_info(usertask.commit_sha)
            self.assertEqual(email, Erica.email)
            self.assertTrue('ago' in date)

    def testCommitNewFile(self):
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff")
            usertask.commit('I wrote new things')
            usertask.publish("task-xyz")
        with get_usertask(Frances, "task-xyz", self.origin_dirname) as usertask:
            self.assertEqual(usertask.read('jobs.md'), '---\nnew stuff')
            
            email, date = usertask.ref_info(usertask.commit_sha)
            self.assertEqual(email, Erica.email)
            self.assertTrue('ago' in date)
    
    def testMoveFile(self):
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            usertask.move('parking.md', 'carholing.md')
            usertask.commit('I moved a thing')
            usertask.publish("task-xyz")
        with get_usertask(Frances, "task-xyz", self.origin_dirname) as usertask:
            self.assertEqual(usertask.read('carholing.md'), '---\nold stuff')

    def testMoveFileFurther(self):
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            usertask.move('parking.md', 'carholing/carholes/parking.md')
            usertask.commit('I moved a thing')
            usertask.publish("task-xyz")
        with get_usertask(Frances, "task-xyz", self.origin_dirname) as usertask:
            self.assertEqual(usertask.read('carholing/carholes/parking.md'), '---\nold stuff')

    def testResubmitFileEdits(self):
        ''' Simulate a single user's preview, back-button, and re-save.
        '''
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            start_sha = usertask.commit_sha
            usertask.write('jobs.md', "---\nnew stuff")
            usertask.commit('I wrote new things')
            usertask.publish("task-xyz")

        with get_usertask(Erica, start_sha, self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff")
            usertask.commit('I wrote the same things')
            usertask.publish("task-xyz")

    def testResubmitFileEdits(self):
        ''' Simulate a single user's preview, back-button, and conflicting re-save.
        '''
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n")
            usertask.commit('I wrote new things')
            usertask.publish("task-xyz")
            start_sha = usertask.commit_sha

        with get_usertask(Erica, start_sha, self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n\nmore stuff\n")
            usertask.commit('I wrote more things')
            usertask.publish("task-xyz")

        with get_usertask(Erica, start_sha, self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n\nmore stuff\n\nfinal stuff\n")
            usertask.commit('I wrote final things')
            usertask.publish("task-xyz")

    def testResubmitFileEditsWithInterloper(self):
        ''' Simulate two users' previews, back-buttons, and conflicting re-saves.
        '''
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n")
            usertask.commit('I wrote new things')
            usertask.publish("task-xyz")
            start_sha = usertask.commit_sha

        with get_usertask(Frances, start_sha, self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n\nmore stuff\n")
            usertask.commit('I wrote more things')
            usertask.publish("task-xyz")

        with get_usertask(Erica, start_sha, self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n\nmore stuff\n\nfinal stuff\n")
            
            # Don't let Erica possibly clobber Frances's changes.
            # Kick this conflict upstairs.
            with self.assertRaises(MergeConflict) as conflict:
                usertask.commit('I wrote final things')
                usertask.publish("task-xyz")
            
            self.assertEqual(conflict.exception.local_commit.author, Erica)
            self.assertEqual(conflict.exception.remote_commit.author, Frances)

    def testInterleavedFileEdits(self):
        ''' Simulate a single user editing in two browser windows.
        '''
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n")
            usertask.commit('I wrote new things')
            usertask.publish("task-xyz")
            start_sha = usertask.commit_sha

        with get_usertask(Erica, start_sha, self.origin_dirname) as usertask1, \
             get_usertask(Erica, start_sha, self.origin_dirname) as usertask2:
            usertask1.write('jobs.md', "---\nnew stuff\n\nmore stuff\n")
            usertask1.commit('I wrote more things')
            usertask1.publish("task-xyz")

            usertask2.write('jobs.md', "---\nnew stuff\n\nother stuff\n")
            usertask2.commit('I wrote different things')
            usertask2.publish("task-xyz")

    def testInterleavedFileEditsWithInterloper(self):
        ''' Simulate a two users editing in two browser windows.
        '''
        with get_usertask(Erica, "task-xyz", self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n")
            usertask.commit('I wrote new things')
            usertask.publish("task-xyz")
            start_sha = usertask.commit_sha

        with get_usertask(Frances, start_sha, self.origin_dirname) as usertaskF, \
             get_usertask(Erica, start_sha, self.origin_dirname) as usertaskE:
            usertaskF.write('jobs.md', "---\nnew stuff\n\nmore stuff\n")
            usertaskF.commit('I wrote more things')
            usertaskF.publish("task-xyz")

            usertaskE.write('jobs.md', "---\nnew stuff\n\nother stuff\n")

            # Don't let Erica possibly clobber Frances's changes.
            # Kick this conflict upstairs.
            with self.assertRaises(MergeConflict) as conflict:
                usertaskE.commit('I wrote different things')
                usertaskE.publish("task-xyz")
            
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
