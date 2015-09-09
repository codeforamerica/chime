from contextlib import contextmanager
from os import mkdir
from tempfile import mkdtemp
from os.path import join, isdir

from git import Repo


@contextmanager
def get_usertask(*args):
    task = UserTask(*args)
    yield task
    task.cleanup()


class UserTask():
    def __init__(self, username, task_id, origin_dirname, working_dir=None):
        # TODO: actual dir shouldn't be made up
        if not working_dir:
            working_dir = mkdtemp()

        origin = Repo(origin_dirname)

        # Clone origin to local checkout.
        user_dir_path = join(working_dir, 'usertask-{}'.format(username))
        if not isdir(user_dir_path):
            mkdir(user_dir_path)
            self.repo = origin.clone(user_dir_path)
        else:
            self.repo = Repo(user_dir_path)

        # Fetch all branches from origin.
        self.repo.git.fetch('origin')

        # Point local master to origin taskname.
        self.repo.git.reset('origin/{}'.format(task_id), hard=True)
        self.task_id = task_id

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
        self.repo.git.push('origin', 'master:{}'.format(self.task_id))

    def cleanup(self):
        # once we have locking, we will unlock here
        pass

    def __del__(self):
        self.cleanup()
