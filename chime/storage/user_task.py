from os import mkdir
from tempfile import mkdtemp
from os.path import join, isdir

from git import Repo

from ..simple_flock import SimpleFlock


class UserTask():
    def __init__(self, username, task_id, origin_dirname, working_dir=None):
        self.task_id = task_id
        self.origin_dirname = origin_dirname
        # TODO: actual dir shouldn't be made up
        if not working_dir:
            working_dir = mkdtemp()

        self.working_dir = working_dir
        self.user_dir_path = join(self.working_dir, 'usertask-{}'.format(username))
        # make sure our working directory exists
        if not isdir(self.user_dir_path):
            mkdir(self.user_dir_path)

    def _initialize_git(self):
        origin = Repo(self.origin_dirname)
        if not isdir(join(self.user_dir_path, '.git')):
            self.repo = origin.clone(self.user_dir_path)
        else:
            self.repo = Repo(self.user_dir_path)

        # Fetch all branches from origin.
        self.repo.git.fetch('origin')
        # Point local master to origin taskname.
        self.repo.git.reset('origin/{}'.format(self.task_id), hard=True)

    def __enter__(self):
        self.lock = SimpleFlock(join(self.user_dir_path + '-lock'), 10)
        self.lock.__enter__()
        self._initialize_git()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.lock.__exit__(exc_type, exc_val, exc_tb)
        self.lock = None

    def _open(self, path, *args, **kwargs):
        return open(join(self.repo.working_dir, path), *args, **kwargs)

    def read(self, filename):
        with self._open(filename, 'r') as file:
            return file.read()

    def write(self, filename, content):
        with self._open(filename, 'w') as file:
            file.write(content)
        self.repo.git.add(filename)

    def commit(self, message=None):
        # Commit to local master, push to origin taskname.
        self.repo.git.commit(m=message, a=True)
        self.repo.git.push('origin', 'master:{}'.format(self.task_id))

    def cleanup(self):
        # once we have locking, we will unlock here
        pass

    def __del__(self):
        self.cleanup()
