from contextlib import contextmanager
from tempfile import mkdtemp
from os.path import join
from os import environ

from git import Repo, Actor


@contextmanager
def get_usertask(*args):
    task = UserTask(*args)
    yield task
    task.cleanup()


class UserTask():
    actor = None
    commit_sha = None

    def __init__(self, actor, start_point, origin_dirname):
        '''
        
            start_point: task ID or commit SHA.
        '''
        self.actor = actor

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
        self._set_author_env()
        self.repo.git.commit(m=message, a=True)
        
        #
        # See if we are behind the origin branch, for example because we are
        # using the back button for editing, and starting from an older commit.
        #
        branch = self.repo.refs['origin/{}'.format(task_id)]
        origin_sha = branch.commit.hexsha
        
        # Rebase if necessary.
        if origin_sha != self.commit_sha:
            if self._is_interloped(origin_sha):
                # Do a timid rebase since someone else has been here.
                self.repo.git.rebase(origin_sha)
            else:
                # Do an aggressive rebase since no one else has been here.
                self.repo.git.rebase(origin_sha, X='theirs')
        
        # Push to origin; we think this is safe to do.
        self.repo.git.push('origin', 'master:{}'.format(task_id))
        
        # Re-point self.commit_sha to the new one.
        self.commit_sha = branch.commit.hexsha
    
    def _set_author_env(self):
        '''
        '''
        environ['GIT_AUTHOR_NAME'] = self.actor.name
        environ['GIT_COMMITTER_NAME'] = self.actor.name
        environ['GIT_AUTHOR_EMAIL'] = self.actor.email
        environ['GIT_COMMITTER_EMAIL'] = self.actor.email
    
    def _is_interloped(self, ending_sha):
        '''
        '''
        rev_list = '{}..{}'.format(self.commit_sha, ending_sha)
        actors = [commit.author for commit in self.repo.iter_commits(rev_list)]
        
        for commit in self.repo.iter_commits(rev_list):
            if commit.author != self.actor:
                return True

        return False

    def cleanup(self):
        # once we have locking, we will unlock here
        pass

    def __del__(self):
        self.cleanup()
