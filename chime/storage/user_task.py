from contextlib import contextmanager
from tempfile import mkdtemp
from os.path import join
from os import environ

from git import Repo, Actor, GitCommandError

from ..repo_functions import MergeConflict


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
        
        # See if we are behind the origin branch, for example because we are
        # using the back button for editing, and starting from an older commit.
        task_sha = self._get_task_sha(task_id)
        
        # Rebase if necessary.
        if task_sha != self.commit_sha:
            self._rebase_with_author_check(task_sha)
        
        try:
            # Push to origin; we think this is safe to do.
            self.repo.git.push('origin', 'master:{}'.format(task_id))

        except GitCommandError:
            # Push failed, possibly because origin has
            # been modified due to rapid concurrent editing.
            self.repo.git.fetch('origin')
            self._rebase_with_author_check(self._get_task_sha(task_id))
        
        # Re-point self.commit_sha to the new one.
        self.commit_sha = self._get_task_sha(task_id)
    
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
    
    def _get_task_sha(self, task_id):
        ''' Get local commit SHA for a given task ID.
        '''
        branch = self.repo.refs['origin/{}'.format(task_id)]
        return branch.commit.hexsha
    
    def _rebase_with_author_check(self, task_sha):
        ''' Rebase onto given SHA, checking for interloping authors.
        
            If no interlopers exist, use an aggressive merge strategy
            to clobber possible conflicts. If any interloper exists,
            use a more timid strategy and possibly raise a MergeConflict.
        '''
        if self._is_interloped(task_sha):
            try:
                # Do a timid rebase since someone else has been here.
                local_commit = self.repo.commit()
                self.repo.git.rebase(task_sha)
            except GitCommandError:
                # Raise a MergeConflict.
                remote_commit = self.repo.commit(task_sha)
                raise MergeConflict(remote_commit, local_commit)
        else:
            # Do an aggressive rebase since no one else has been here.
            self.repo.git.rebase(task_sha, X='theirs')

    def cleanup(self):
        # once we have locking, we will unlock here
        pass

    def __del__(self):
        self.cleanup()
