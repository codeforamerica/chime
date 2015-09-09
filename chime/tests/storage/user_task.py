from subprocess import check_call
from tempfile import mkdtemp
from shutil import rmtree
from os.path import join
from os import mkdir

# from ...storage.user_task import get_usertask
from storage.user_task import get_usertask
from unittest import TestCase


class TestFirst(TestCase):
    def setUp(self):
        self.working_dirname = mkdtemp(prefix='storage-test-')

        # Make a mostly-empty repo with parking.md file,
        # one master commit, and one branch called task-xyz.

        self.origin_dirname = join(self.working_dirname, 'origin')
        self.clone_dirname = join(self.working_dirname, 'clone')
        mkdir(self.origin_dirname)
        call_git('--bare init', self.origin_dirname)

        call_git(['clone', self.origin_dirname, (self.clone_dirname)])

        call_git('commit -m First --allow-empty', self.clone_dirname)
        call_git('push origin master', self.clone_dirname)
        self.setup_task("task-xyz", self.clone_dirname)

    def setup_task(self, branch_name, clone_dirname, contents='old stuff'):
        call_git('checkout -b {}'.format(branch_name), clone_dirname)
        with open(join(clone_dirname, 'parking.md'), 'w') as file:
            file.write('---\n' + contents)
        call_git('add parking.md', clone_dirname)
        call_git('commit -m Second', clone_dirname)
        call_git('push origin {}'.format(branch_name), clone_dirname)

    def make_test_usertask(self, user, task):
        return get_usertask(user, task, self.origin_dirname, self.working_dirname)

    def tearDown(self):
        rmtree(self.working_dirname)

    def testReadsExistingRepo(self):
        with self.make_test_usertask("erica", "task-xyz") as usertask:
            self.assertEqual(usertask.read('parking.md'), '---\nold stuff')

    def testWriteWithImmediateRead(self):
        with self.make_test_usertask("erica", "task-xyz") as usertask:
            usertask.write('parking.md', "---\nnew stuff")
            self.assertEqual(usertask.read('parking.md'), '---\nnew stuff')

    def testIsAlwaysClean(self):
        with self.make_test_usertask("erica", "task-xyz") as usertask:
            usertask.write('parking.md', "---\nnew stuff")
        with get_usertask("erica", "task-xyz", self.origin_dirname) as usertask:
            self.assertEqual(usertask.read('parking.md'), '---\nold stuff')

    def testCommitWrite(self):
        with self.make_test_usertask("erica", "task-xyz") as usertask:
            usertask.write('parking.md', "---\nnew stuff")
            usertask.commit('I wrote new things')
        with self.make_test_usertask("frances", "task-xyz") as usertask:
            self.assertEqual(usertask.read('parking.md'), '---\nnew stuff')

    def testCommitNewFile(self):
        with self.make_test_usertask("erica", "task-xyz") as usertask:
            usertask.write('jobs.md', "---\nnew stuff")
            usertask.commit('I wrote new things')
        with self.make_test_usertask("frances", "task-xyz") as usertask:
            self.assertEqual(usertask.read('jobs.md'), '---\nnew stuff')

    def testSameUserAndTaskHasSameWorkspace(self):
        with self.make_test_usertask("erica", "task-xyz") as erica1:
            with self.make_test_usertask("erica", "task-xyz") as erica2:
                erica1.write('myfile.md', "erica's contents")

                self.assertEqual("erica's contents", erica1.read('myfile.md'))
                self.assertEqual("erica's contents", erica2.read('myfile.md'))

    def testDifferentUsersHaveSeparateWorkspaces(self):
        with self.make_test_usertask("erica", "task-xyz") as erica:
            with self.make_test_usertask("frances", "task-xyz") as frances:
                erica.write('myfile.md', "erica's contents")
                frances.write('myfile.md', "frances's contents")

                self.assertEqual("erica's contents", erica.read('myfile.md'))
                self.assertEqual("frances's contents", frances.read('myfile.md'))

    def testUserCanSwitchBetweenDifferentTasks(self):
        with self.make_test_usertask("erica", "task-xyz") as ericaxyz:
            ericaxyz.write('myfile.md', "erica's xyz contents")
            ericaxyz.commit('committing my stuff')
            self.assertEqual("erica's xyz contents", ericaxyz.read('myfile.md'))

        self.setup_task("task-abc", self.clone_dirname, 'new stuff')
        with self.make_test_usertask("erica", "task-abc") as ericaabc:
            ericaabc.write('myfile.md', "erica's abc contents")
            ericaabc.commit('me too')
            self.assertEqual("erica's abc contents", ericaabc.read('myfile.md'))


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
# still needs locking
# merge conflicts
# task deletion
# test frances has access to task that erica created before commit
