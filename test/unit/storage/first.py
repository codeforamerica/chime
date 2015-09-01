from subprocess import check_call
from tempfile import mkdtemp
from shutil import rmtree
from os.path import join
from os import mkdir

from storage.user_task import get_usertask
from unit.test_logs import TestCase


class TestFirst(TestCase):
    def setUp(self):
        self.working_dirname = mkdtemp(prefix='storage-test-')

        #
        # Make a mostly-empty repo with parking.md file,
        # one master commit, and one branch called task-xyz.
        #
        git_kwargs = dict(stderr=open('/dev/null', 'w'), stdout=open('/dev/null', 'w'))

        self.origin_dirname = join(self.working_dirname, 'origin')
        mkdir(self.origin_dirname)
        check_call('git --bare init'.split(), cwd=self.origin_dirname, **git_kwargs)

        clone_dirname = join(self.working_dirname, 'clone')
        check_call(('git', 'clone', self.origin_dirname, clone_dirname), **git_kwargs)

        git_kwargs.update(dict(cwd=clone_dirname))

        check_call('git commit -m First --allow-empty'.split(), **git_kwargs)
        check_call('git push origin master'.split(), **git_kwargs)
        check_call('git checkout -b task-xyz'.split(), **git_kwargs)

        with open(join(clone_dirname, 'parking.md'), 'w') as file:
            file.write('---\nold stuff')

        check_call('git add parking.md'.split(), **git_kwargs)
        check_call('git commit -m Second'.split(), **git_kwargs)
        check_call('git push origin task-xyz'.split(), **git_kwargs)
        rmtree(clone_dirname)

    def tearDown(self):
        rmtree(self.working_dirname)

    def testReadsExistingRepo(self):
        with get_usertask("erica", "task-xyz", self.origin_dirname) as usertask:
            with usertask.open('parking.md') as file:
                self.assertEqual(file.read(3), '---')

    def testWrite(self):
        with get_usertask("erica", "task-xyz", self.origin_dirname) as usertask:
            with usertask.open('parking.md', 'w') as file:
                file.write("---\nnew stuff")
            with usertask.open('parking.md') as file:
                self.assertEqual(file.read(), '---\nnew stuff')

    def testIsAlwaysClean(self):
        with get_usertask("erica", "task-xyz", self.origin_dirname) as usertask:
            with usertask.open('parking.md', 'w') as file:
                file.write("---\nnew stuff")
        with get_usertask("erica", "task-xyz", self.origin_dirname) as usertask:
            with usertask.open('parking.md') as file:
                self.assertEqual(file.read(), '---\nold stuff')
