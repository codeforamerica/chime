from contextlib import contextmanager
from os.path import join, exists, dirname, relpath, isdir, realpath
from os import environ, makedirs
from tempfile import mkdtemp
from time import sleep, time
import fcntl, errno

from git import Repo, Actor, GitCommandError
from slugify import slugify

from ..repo_functions import MergeConflict
from ..constants import WORKING_STATE_PUBLISHED, WORKING_STATE_DELETED, USERTASK_DIRECTORY_PATTERN

def _calculate_dirname(actor, origin):
    ''' Prepare a consistent directory for this user and this repository.
    '''
    first_commit = list(origin.iter_commits())[-1].hexsha
    return USERTASK_DIRECTORY_PATTERN.format(sha=first_commit[:8], email=slugify(actor.email))

@contextmanager
def get_usertask(*args, **kwargs):
    task = UserTask(*args, **kwargs)
    yield task
    task.cleanup()


class UserTaskPublished(RuntimeError): pass
class UserTaskDeleted(RuntimeError): pass
class UserTaskUnpushable(RuntimeError): pass

class UserTask():
    actor = None
    commit_sha = None
    _writeable = True
    _committed = False
    _pushed = False

    def __init__(self, actor, task_id, origin_dirname, working_dirname, start_point=None):
        '''
        
            start_point: task ID or commit SHA.
        '''
        self.actor = actor
        self.task_id = task_id

        # Prepare a clone directory.
        origin = Repo(origin_dirname)
        user_dirname = _calculate_dirname(self.actor, origin)
        clone_dirname = join(realpath(working_dirname), user_dirname)
        
        self._lock(clone_dirname)
        
        if isdir(clone_dirname):
            self.repo = Repo(clone_dirname)
            self.repo.git.checkout('zelig')
            self.repo.git.reset('origin/master', hard=True)
        else:
            # Clone origin to local checkout.
            self.repo = origin.clone(clone_dirname)
            self.repo.git.checkout('zelig', orphan=True)
            self.repo.git.reset('origin/master', hard=True)
        
        # Fetch all branches from origin.
        self.repo.git.fetch('origin')
        
        # Determine if a start-point was passed or needs to be inferred.
        if start_point is None:
            start_point = task_id
            self._writeable = False
        
        # Figure out what start_point is.
        if 'origin/{}'.format(start_point) in self.repo.refs:
            branch = self.repo.refs['origin/{}'.format(start_point)]
            self.commit_sha = branch.commit.hexsha
        else:
            self.commit_sha = start_point
        
        # Point local zelig to start_point.
        self.repo.git.reset(self.commit_sha, hard=True)
    
    def __repr__(self):
        return '<UserTask {} in {}>'.format(self.actor.email, self.repo.working_dir)
    
    def _lock(self, clone_dirname):
        self._lockfile = open('{}.lock'.format(clone_dirname), 'a')
        timeout = time() + 1.
        
        while True:
            try:
                fcntl.flock(self._lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Lock acquired!
                return
            except IOError, ex:
                if ex.errno != errno.EAGAIN:  # Resource temporarily unavailable
                    raise
                elif time() > timeout:
                    # Exceeded the timeout.
                    raise

            sleep(.01)
    
    def _unlock(self):
        fcntl.flock(self._lockfile, fcntl.LOCK_UN)
    
    def _open(self, path, *args, **kwargs):
        return open(join(self.repo.working_dir, path), *args, **kwargs)

    def read(self, filename):
        with self._open(filename, 'r') as file:
            return file.read()

    def write(self, filename, content):
        assert self._writeable and not (self._committed or self._pushed)
    
        with self._open(filename, 'w') as file:
            file.write(content)
        self.repo.git.add(filename)

    def move(self, old_path, new_path):
        assert self._writeable and not (self._committed or self._pushed)
        
        #
        # Make sure we're not trying to move a directory inside itself.
        # This behavior is pretty old, and it's unclear if we want to
        # keep it but for now we just wants the existings test to pass.
        # 
        old_dirname, new_dirname = dirname(old_path), dirname(new_path)
        
        if old_dirname:
            if not relpath(new_dirname, old_dirname).startswith('..'):
                raise ValueError(u'I cannot move a directory inside itself!', u'warning')
        
        dir_path = join(self.repo.working_dir, dirname(new_path))

        if not exists(dir_path):
            makedirs(dir_path)
        
        self.repo.git.mv(old_path, new_path)

    def commit(self, message):
        assert self._writeable and not (self._committed or self._pushed)
        self._committed = True

        # Commit to local zelig, push to origin task ID.
        self._set_author_env()
        dirty = self.repo.is_dirty()
        if dirty:
            self.repo.git.commit(m=message, a=True)
        return dirty

    def is_pushable(self):
        ''' Return pushable status: True, False, or a working state constant.
        '''
        if not self._writeable:
            return False
        
        if self._pushed:
            return False

        if not self._committed:
            return False
        
        if self.task_id in self.repo.tags:
            return WORKING_STATE_PUBLISHED

        if 'origin/{}'.format(self.task_id) not in self.repo.refs:
            return WORKING_STATE_DELETED

        return True
    
    def push(self):
        assert self._committed and not self._pushed
        pushable = self.is_pushable()
        
        if pushable is True:
            self._pushed = True
        if pushable is WORKING_STATE_PUBLISHED:
            raise UserTaskPublished()
        elif pushable is WORKING_STATE_DELETED:
            raise UserTaskDeleted()
        elif pushable is False:
            raise UserTaskUnpushable()

        # See if we are behind the origin branch, for example because we are
        # using the back button for editing, and starting from an older commit.
        task_sha = self._get_task_sha()
        
        # Rebase if necessary.
        if task_sha != self.commit_sha:
            self._rebase_with_author_check(task_sha)
        
        try:
            # Push to origin; we think this is safe to do.
            self.repo.git.push('origin', 'zelig:{}'.format(self.task_id))

        except GitCommandError:
            # Push failed, possibly because origin has
            # been modified due to rapid concurrent editing.
            self.repo.git.fetch('origin')
            self._rebase_with_author_check(self._get_task_sha())
        
        # Re-point self.commit_sha to the new one.
        self.commit_sha = self._get_task_sha()
    
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
        
        raw = self.repo.git.show('--format=%ae %ar', ref)
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
    
    def _get_task_sha(self):
        ''' Get local commit SHA for a given task ID.
        '''
        branch = self.repo.refs['origin/{}'.format(self.task_id)]
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
        self._unlock()

    def __del__(self):
        self.cleanup()
