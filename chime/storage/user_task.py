from contextlib import contextmanager
from tempfile import mkdtemp
from os.path import join

from git import Repo


@contextmanager
def get_usertask(*args):
    task = UserTask(*args)
    yield task
    task.cleanup()


class UserTask():
    def __init__(self, username, taskname, origin_dirname):
        '''
        '''
        origin = Repo(origin_dirname)

        # Clone origin to local checkout.
        self.repo = origin.clone(mkdtemp())

        # Fetch all branches from origin.
        self.repo.git.fetch('origin')

        # Check out local clone to origin taskname.
        self.repo.create_head(taskname, 'origin/' + taskname, force=True)
        self.repo.heads[taskname].checkout()

    def open(self, path, *args, **kwargs):
        return open(join(self.repo.working_dir, path), *args, **kwargs)

    def cleanup(self):
        pass

    def __del__(self):
        self.cleanup()
