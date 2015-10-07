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
        self.task_id = 'task-xyz'
        self.working_dirname = mkdtemp(prefix='storage-test-')

        # Make a mostly-empty repo with parking.md file,
        # one master commit, and one branch called task-xyz.

        self.origin_dirname = join(self.working_dirname, 'origin')
        self.get_usertask_args = self.origin_dirname, self.working_dirname
        clone_dirname = join(self.working_dirname, 'clone')

        mkdir(self.origin_dirname)
        call_git('--bare init', self.origin_dirname)

        call_git(['clone', self.origin_dirname, clone_dirname])

        call_git('commit -m First --allow-empty', clone_dirname)
        call_git('push origin master', clone_dirname)
        call_git('checkout -b {}'.format(self.task_id), clone_dirname)

        with open(join(clone_dirname, 'parking.md'), 'w') as file:
            file.write('---\nold stuff')

        call_git('add parking.md', clone_dirname)
        call_git('commit -m Second', clone_dirname)
        call_git('push origin {}'.format(self.task_id), clone_dirname)
        rmtree(clone_dirname)

    def tearDown(self):
        rmtree(self.working_dirname)

    def testReadsExistingRepo(self):
        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=self.task_id) as usertask:
            self.assertEqual(usertask.read('parking.md'), '---\nold stuff')

    def testWriteNotAllowed(self):
        with get_usertask(Erica, self.task_id, *self.get_usertask_args) as usertask:
            with self.assertRaises(Exception):
                usertask.write('parking.md', "---\nnew stuff")

    def testWriteWithImmediateRead(self):
        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=self.task_id) as usertask:
            usertask.write('parking.md', "---\nnew stuff")
            self.assertEqual(usertask.read('parking.md'), '---\nnew stuff')

    def testIsAlwaysClean(self):
        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=self.task_id) as usertask:
            usertask.write('parking.md', "---\nnew stuff")
        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=self.task_id) as usertask:
            self.assertEqual(usertask.read('parking.md'), '---\nold stuff')

    def testPublishable(self):
        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=self.task_id) as usertask:
            usertask.write('parking.md', "---\nnew stuff")
            self.assertIs(usertask.is_pushable(), False)
            usertask.commit('I wrote new things')
            self.assertIs(usertask.is_pushable(), True)
            usertask.push()
            self.assertIs(usertask.is_pushable(), False)

    def testCommitWrite(self):
        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=self.task_id) as usertask:
            usertask.write('parking.md', "---\nnew stuff")
            usertask.commit('I wrote new things')
            usertask.push()
        with get_usertask(Frances, self.task_id, *self.get_usertask_args, start_point=self.task_id) as usertask:
            self.assertEqual(usertask.read('parking.md'), '---\nnew stuff')
            
            info = usertask.ref_info()
            self.assertEqual(info['published_by'], Erica.email)
            self.assertTrue('ago' in info['published_date'])

    def testCommitNewFile(self):
        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=self.task_id) as usertask:
            usertask.write('jobs.md', "---\nnew stuff")
            usertask.commit('I wrote new things')
            usertask.push()
        with get_usertask(Frances, self.task_id, *self.get_usertask_args, start_point=self.task_id) as usertask:
            self.assertEqual(usertask.read('jobs.md'), '---\nnew stuff')
            
            info = usertask.ref_info()
            self.assertEqual(info['published_by'], Erica.email)
            self.assertTrue('ago' in info['published_date'])
    
    def testMoveFile(self):
        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=self.task_id) as usertask:
            usertask.move('parking.md', 'carholing.md')
            usertask.commit('I moved a thing')
            usertask.push()
        with get_usertask(Frances, self.task_id, *self.get_usertask_args, start_point=self.task_id) as usertask:
            self.assertEqual(usertask.read('carholing.md'), '---\nold stuff')

    def testMoveFileFurther(self):
        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=self.task_id) as usertask:
            usertask.move('parking.md', 'carholing/carholes/parking.md')
            usertask.commit('I moved a thing')
            usertask.push()
        with get_usertask(Frances, self.task_id, *self.get_usertask_args, start_point=self.task_id) as usertask:
            self.assertEqual(usertask.read('carholing/carholes/parking.md'), '---\nold stuff')

    def testResubmitFileEdits(self):
        ''' Simulate a single user's preview, back-button, and re-save.
        '''
        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=self.task_id) as usertask:
            start_sha = usertask.commit_sha
            usertask.write('jobs.md', "---\nnew stuff")
            usertask.commit('I wrote new things')
            usertask.push()

        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=start_sha) as usertask:
            usertask.write('jobs.md', "---\nnew stuff")
            usertask.commit('I wrote the same things')
            usertask.push()

    def testResubmitFileEdits(self):
        ''' Simulate a single user's preview, back-button, and conflicting re-save.
        '''
        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=self.task_id) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n")
            usertask.commit('I wrote new things')
            usertask.push()
            start_sha = usertask.commit_sha

        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=start_sha) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n\nmore stuff\n")
            usertask.commit('I wrote more things')
            usertask.push()

        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=start_sha) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n\nmore stuff\n\nfinal stuff\n")
            usertask.commit('I wrote final things')
            usertask.push()

    def testResubmitFileEditsWithInterloper(self):
        ''' Simulate two users' previews, back-buttons, and conflicting re-saves.
        '''
        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=self.task_id) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n")
            usertask.commit('I wrote new things')
            usertask.push()
            start_sha = usertask.commit_sha

        with get_usertask(Frances, self.task_id, *self.get_usertask_args, start_point=start_sha) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n\nmore stuff\n")
            usertask.commit('I wrote more things')
            usertask.push()

        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=start_sha) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n\nmore stuff\n\nfinal stuff\n")
            
            # Don't let Erica possibly clobber Frances's changes.
            # Kick this conflict upstairs.
            with self.assertRaises(MergeConflict) as conflict:
                usertask.commit('I wrote final things')
                usertask.push()
            
            self.assertEqual(conflict.exception.local_commit.author, Erica)
            self.assertEqual(conflict.exception.remote_commit.author, Frances)

    def testInterleavedFileEdits(self):
        ''' Simulate a single user editing in two browser windows.
        '''
        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=self.task_id) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n")
            usertask.commit('I wrote new things')
            usertask.push()
            start_sha = usertask.commit_sha

        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=start_sha) as usertask1:
            # Lock contention will bubble up as an IOError.
            with self.assertRaises(IOError) as error:
                with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=start_sha) as usertask2:
                    pass

    def testInterleavedFileEditsWithInterloper(self):
        ''' Simulate a two users editing in two browser windows.
        '''
        with get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=self.task_id) as usertask:
            usertask.write('jobs.md', "---\nnew stuff\n")
            usertask.commit('I wrote new things')
            usertask.push()
            start_sha = usertask.commit_sha

        with get_usertask(Frances, self.task_id, *self.get_usertask_args, start_point=start_sha) as usertaskF, \
             get_usertask(Erica, self.task_id, *self.get_usertask_args, start_point=start_sha) as usertaskE:
            usertaskF.write('jobs.md', "---\nnew stuff\n\nmore stuff\n")
            usertaskF.commit('I wrote more things')
            usertaskF.push()

            usertaskE.write('jobs.md', "---\nnew stuff\n\nother stuff\n")

            # Don't let Erica possibly clobber Frances's changes.
            # Kick this conflict upstairs.
            with self.assertRaises(MergeConflict) as conflict:
                usertaskE.commit('I wrote different things')
                usertaskE.push()
            
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
