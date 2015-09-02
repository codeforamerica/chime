from subprocess import check_call
from tempfile import mkdtemp
from shutil import rmtree
from os.path import join
from os import mkdir

from ...storage.user_task import get_usertask
from unittest import TestCase


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
        with get_usertask("erica", "task-xyz", self.origin_dirname) as usertask:
            self.assertEqual(usertask.read('parking.md'), '---\nold stuff')

    def testWriteWithImmediateRead(self):
        with get_usertask("erica", "task-xyz", self.origin_dirname) as usertask:
            usertask.write('parking.md', "---\nnew stuff")
            self.assertEqual(usertask.read('parking.md'), '---\nnew stuff')

    def testIsAlwaysClean(self):
        with get_usertask("erica", "task-xyz", self.origin_dirname) as usertask:
            usertask.write('parking.md', "---\nnew stuff")
        with get_usertask("erica", "task-xyz", self.origin_dirname) as usertask:
            self.assertEqual(usertask.read('parking.md'), '---\nold stuff')

    def testCommitWrite(self):
        with get_usertask("erica", "task-xyz", self.origin_dirname) as usertask:
            usertask.write('parking.md', "---\nnew stuff")
            usertask.commit('I wrote new things')
        with get_usertask("frances", "task-xyz", self.origin_dirname) as usertask:
            self.assertEqual(usertask.read('parking.md'), '---\nnew stuff')

    def testCommitNewFile(self):
        with get_usertask("erica", "task-xyz", self.origin_dirname) as usertask:
            usertask.write('jobs.md', "---\nnew stuff")
            usertask.commit('I wrote new things')
        with get_usertask("frances", "task-xyz", self.origin_dirname) as usertask:
            self.assertEqual(usertask.read('jobs.md'), '---\nnew stuff')


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
