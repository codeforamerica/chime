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

        # Point local master to origin taskname.
        self.repo.git.reset('origin/{}'.format(taskname), hard=True)
        self.taskname = taskname

    def _open(self, path, *args, **kwargs):
        return open(join(self.repo.working_dir, path), *args, **kwargs)

    def read(self, filename):
        with self._open(filename, 'r') as file:
            return file.read()

    def write(self, filename, content):
        with self._open(filename, 'w') as file:
            file.write(content)
        self.repo.git.add(filename)

    def commit(self, message):
        # Commit to local master, push to origin taskname.
        self.repo.git.commit(m=message, a=True)
        self.repo.git.push('origin', 'master:{}'.format(self.taskname))

    def cleanup(self):
        # once we have locking, we will unlock here
        pass

    def __del__(self):
        self.cleanup()
