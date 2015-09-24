from contextlib import contextmanager
from os.path import join, exists, dirname, relpath
from os import environ, makedirs
from tempfile import mkdtemp

from git import Repo, Actor, GitCommandError

from ..repo_functions import MergeConflict
from ..constants import WORKING_STATE_PUBLISHED, WORKING_STATE_DELETED


@contextmanager
def get_usertask(*args):
    task = UserTask(*args)
    yield task
    task.cleanup()


class UserTask():
    actor = None
    commit_sha = None
    committed = False
    published = False

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
    
    def __repr__(self):
        return '<UserTask {} in {}>'.format(self.actor.email, self.repo.working_dir)

    def _open(self, path, *args, **kwargs):
        return open(join(self.repo.working_dir, path), *args, **kwargs)

    def read(self, filename):
        with self._open(filename, 'r') as file:
            return file.read()

    def write(self, filename, content):
        assert not (self.committed or self.published)
    
        with self._open(filename, 'w') as file:
            file.write(content)
        self.repo.git.add(filename)

    def move(self, old_path, new_path):
        assert not (self.committed or self.published)
        
        dir_path = join(self.repo.working_dir, dirname(new_path))
        
        #
        # Make sure we're not trying to move a directory inside itself.
        # This behavior is pretty old, and it's unclear if we want to
        # keep it but for now we just wants the existings test to pass.
        # 
        old_dirname, new_dirname = dirname(old_path), dirname(new_path)
        
        if old_dirname:
            if not relpath(new_dirname, old_dirname).startswith('..'):
                raise ValueError(u'I cannot move a directory inside itself!', u'warning')

        if not exists(dir_path):
            makedirs(dir_path)
        
        self.repo.git.mv(old_path, new_path)

    def commit(self, message):
        assert not (self.committed or self.published)
        self.committed = True
    
        # Commit to local master, push to origin task ID.
        self._set_author_env()
        self.repo.git.commit(m=message, a=True)
    
    def is_publishable(self, task_id):
        ''' Return publishable status: True, False, or a working state constant.
        '''
        if self.published:
            return False

        if not self.committed:
            return False
        
        if task_id in self.repo.tags:
            return WORKING_STATE_PUBLISHED

        if 'origin/{}'.format(task_id) not in self.repo.refs:
            return WORKING_STATE_DELETED

        return True
    
    def publish(self, task_id):
        assert self.committed and not self.published
        self.published = True

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
    
    def ref_info(self, ref=None):
        ''' Return dict with author email and a relative date for a given reference.
        '''
        if ref is None:
            ref = self.commit_sha
        
        elif ref in self.repo.tags:
            # De-reference the tag. Sometimes showing a tag shows more than
            # just the commit, prefixing output with "tag <tag name>" if
            # there are notes attached.
            ref = self.repo.tags[ref].commit.hexsha
        
        raw = self.repo.git.show('--format=%ae %ad', '--date=relative', ref)
        email, date = raw.split('\n')[0].split(' ', 1)

        return dict(published_date=date, published_by=email)
    
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
