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
    commit_sha = None

    def __init__(self, username, start_point, origin_dirname):
        '''
        
            start_point: task ID or commit SHA.
        '''
        origin = Repo(origin_dirname)

        # Clone origin to local checkout.
        self.repo = origin.clone(mkdtemp())

        # Fetch all branches from origin.
        self.repo.git.fetch('origin')
        
        # Figure out what start_point is.
        if 'origin/{}'.format(start_point) in self.repo.refs:
            branch = self.repo.refs['origin/{}'.format(start_point)]
            self.commit_sha = branch.commit.hexsha
        else:
            self.commit_sha = start_point
        
        # Point local master to start_point.
        self.repo.git.reset(self.commit_sha, hard=True)

    def _open(self, path, *args, **kwargs):
        return open(join(self.repo.working_dir, path), *args, **kwargs)

    def read(self, filename):
        with self._open(filename, 'r') as file:
            return file.read()

    def write(self, filename, content):
        with self._open(filename, 'w') as file:
            file.write(content)
        self.repo.git.add(filename)

    def commit(self, task_id, message):
        # Commit to local master, push to origin task ID.
        self.repo.git.commit(m=message, a=True)
        
        #
        # See if we are behind the origin branch, for example because we are
        # using the back button for editing, and starting from an older commit.
        #
        branch = self.repo.refs['origin/{}'.format(task_id)]
        origin_sha = branch.commit.hexsha
        
        # Rebase if necessary.
        if origin_sha != self.commit_sha:
            self.repo.git.rebase(origin_sha)
        
        # Push to origin; we think this is safe to do.
        self.repo.git.push('origin', 'master:{}'.format(task_id))
        
        # Re-point self.commit_sha to the new one.
        self.commit_sha = branch.commit.hexsha

    def cleanup(self):
        # once we have locking, we will unlock here
        pass

    def __del__(self):
        self.cleanup()
