import os
import logging
from os import mkdir
from os.path import join, split, exists, isdir
from itertools import chain
from git.cmd import GitCommandError

class MergeConflict (Exception):
    def __init__(self, remote_commit, local_commit):
        self.remote_commit = remote_commit
        self.local_commit = local_commit

    def files(self):
        diffs = self.remote_commit.diff(self.local_commit)

        new_files = [d.b_blob.name for d in diffs if d.new_file]
        gone_files = [d.a_blob.name for d in diffs if d.deleted_file]
        changed_files = [d.a_blob.name for d in diffs if not (d.deleted_file or d.new_file)]

        return new_files, gone_files, changed_files

    def __str__(self):
        return 'MergeConflict(%s, %s)' % (self.remote_commit, self.local_commit)

def _origin(branch_name):
    ''' Format the branch name into a origin path and return it.
    '''
    return 'origin/' + branch_name

def get_branch_start_point(clone, default_branch_name, new_branch_name):
    ''' Return the last commit on the branch
    '''
    if _origin(new_branch_name) in clone.refs:
        return clone.refs[_origin(new_branch_name)].commit

    if _origin(default_branch_name) in clone.refs:
        return clone.refs[_origin(default_branch_name)].commit

    return clone.branches[default_branch_name].commit

def get_existing_branch(clone, default_branch_name, new_branch_name):
    ''' Return an existing branch with the passed name, if it exists.
    '''
    clone.git.fetch('origin')

    start_point = get_branch_start_point(clone, default_branch_name, new_branch_name)

    logging.debug('get_existing_branch() start_point is %s' % repr(start_point))

    # See if it already matches start_point
    if new_branch_name in clone.branches:
        if clone.branches[new_branch_name].commit == start_point:
            return clone.branches[new_branch_name]

    # See if the branch exists at the origin
    try:
        # pull the branch but keep the active branch checked out
        active_branch = clone.active_branch
        clone.git.checkout(new_branch_name)
        clone.git.pull('origin', new_branch_name)
        clone.git.checkout(active_branch.name)
        return clone.branches[new_branch_name]

    except GitCommandError:
        return None

    return None

def get_start_branch(clone, default_branch_name, new_branch_name):
    ''' Start a new repository branch, push it to origin and return it.

        Don't touch the working directory. If an existing branch is found
        with the same name, use it instead of creating a fresh branch.
    '''
    existing_branch = get_existing_branch(clone, default_branch_name, new_branch_name)
    if existing_branch:
        return existing_branch

    # create and return a brand new branch
    start_point = get_branch_start_point(clone, default_branch_name, new_branch_name)
    branch = clone.create_head(new_branch_name, commit=start_point, force=True)
    clone.git.push('origin', new_branch_name)

    return branch

def complete_branch(clone, default_branch_name, working_branch_name):
    ''' Complete a branch merging, deleting it, and returning the merge commit.

        Checks out the default branch, merges the working branch in.
        Deletes the working branch in the clone and the origin, and leaves
        the working directory checked out to the merged default branch.

        In case of merge error, leaves the working directory checked out
        to the original working branch.

        Old behavior:

        Checks out the working branch, merges the default branch in, then
        switches to the default branch and merges the working branch back.
        Deletes the working branch in the clone and the origin, and leaves
        the working directory checked out to the merged default branch.
    '''
    message = 'Merged work from "%s"' % working_branch_name

    clone.git.checkout(default_branch_name)
    clone.git.pull('origin', default_branch_name)

    #
    # Merge the working branch back to the default branch.
    #
    try:
        clone.git.merge(working_branch_name, '--no-ff', m=message)

    except:
        # raise the two commits in conflict.
        remote_commit = clone.refs[_origin(default_branch_name)].commit

        clone.git.reset(default_branch_name, hard=True)
        clone.git.checkout(working_branch_name)
        raise MergeConflict(remote_commit, clone.commit())

    else:
        clone.git.push('origin', default_branch_name)

    #
    # Delete the working branch.
    #
    clone.remotes.origin.push(':' + working_branch_name)
    clone.delete_head([working_branch_name])

    return clone.commit()

    # #
    # # First, merge the default branch to the working branch.
    # #
    # try:
    #     # sync: pull --rebase followed by push.
    #     clone.git.pull('origin', default_branch_name, rebase=True)
    #
    # except:
    #     # raise the two commits in conflict.
    #     clone.git.fetch('origin')
    #     remote_commit = clone.refs[_origin(default_branch_name)].commit
    #
    #     clone.git.rebase(abort=True)
    #     clone.git.reset(hard=True)
    #     raise MergeConflict(remote_commit, clone.commit())
    #
    # else:
    #     clone.git.push('origin', working_branch_name)
    #
    # #
    # # Merge the working branch back to the default branch.
    # #
    # clone.git.checkout(default_branch_name)
    # clone.git.merge(working_branch_name)
    # clone.git.push('origin', default_branch_name)
    #
    # #
    # # Delete the working branch.
    # #
    # clone.remotes.origin.push(':' + working_branch_name)
    # clone.delete_head([working_branch_name])

def abandon_branch(clone, default_branch_name, working_branch_name):
    ''' Complete work on a branch by abandoning and deleting it.
    '''
    msg = 'Abandoned work from "%s"' % working_branch_name

    #
    # Add an empty commit with abandonment note.
    #
    clone.branches[default_branch_name].checkout()
    clone.index.commit(msg)

    #
    # Delete the old branch.
    #
    clone.remotes.origin.push(':' + working_branch_name)

    if working_branch_name in clone.branches:
        clone.git.branch('-D', working_branch_name)

def clobber_default_branch(clone, default_branch_name, working_branch_name):
    ''' Complete work on a branch by clobbering master and deleting it.
    '''
    msg = 'Clobbered with work from "%s"' % working_branch_name

    #
    # First merge default to working branch, because
    # git does not provide a "theirs" strategy.
    #
    clone.branches[working_branch_name].checkout()
    clone.git.fetch('origin', default_branch_name)
    clone.git.merge('FETCH_HEAD', '--no-ff', s='ours', m=msg) # "ours" = working

    clone.branches[default_branch_name].checkout()
    clone.git.pull('origin', default_branch_name)
    clone.git.merge(working_branch_name, '--ff-only')
    clone.git.push('origin', default_branch_name)

    #
    # Delete the working branch.
    #
    clone.remotes.origin.push(':' + working_branch_name)
    clone.delete_head([working_branch_name])

def make_working_file(clone, dir, path):
    ''' Create a new working file, return its local git and real absolute paths.

        Creates a new file under the given directory, building whatever
        intermediate directories are necessary to write the file.
    '''
    repo_path = join((dir or '').rstrip('/'), path)
    real_path = join(clone.working_dir, repo_path)

    #
    # Build a full directory path.
    #
    head, dirs = split(repo_path)[0], []

    while head:
        head, dir = split(head)
        dirs.insert(0, dir)

    if '..' in dirs:
        raise Exception('None of that now')

    #
    # Create directory tree.
    #
    for i in range(len(dirs)):
        dir_path = join(clone.working_dir, os.sep.join(dirs[:i + 1]))

        if not isdir(dir_path):
            mkdir(dir_path)

    return repo_path, real_path

def save_working_file(clone, path, message, base_sha, default_branch_name):
    ''' Save a file in the working dir, push it to origin, return the commit.

        Rely on Git environment variables for author emails and names.

        After committing the new file, attempts to merge the origin working
        branch and the origin default branches in turn, to surface possible
        merge problems early. Might raise a MergeConflict.
    '''
    if clone.active_branch.commit.hexsha != base_sha:
        raise Exception('Out of date SHA: %s' % base_sha)

    if exists(join(clone.working_dir, path)):
        clone.index.add([path])
    else:
        clone.index.remove([path])

    clone.index.commit(message)
    active_branch_name = clone.active_branch.name

    #
    # Sync with the default and upstream branches in case someone made a change.
    #
    for sync_branch_name in (active_branch_name, default_branch_name):
        msg = 'Merged work from "%s"' % sync_branch_name
        clone.git.fetch('origin', sync_branch_name)

        try:
            clone.git.merge('FETCH_HEAD', '--no-ff', m=msg)

        except:
            # raise the two commits in conflict.
            remote_commit = clone.refs[_origin(sync_branch_name)].commit

            clone.git.reset(hard=True)
            raise MergeConflict(remote_commit, clone.commit())

    clone.git.push('origin', active_branch_name)

    return clone.active_branch.commit

def move_existing_file(clone, old_path, new_path, base_sha, default_branch_name):
    ''' Move a file in the working dir, push it to origin, return the commit.

        Rely on Git environment variables for author emails and names.

        After committing the new file, attempts to merge the origin working
        branch and the origin default branches in turn, to surface possible
        merge problems early. Might raise a MergeConflict.
    '''
    if clone.active_branch.commit.hexsha != base_sha:
        raise Exception('Out of date SHA: %s' % base_sha)

    new_repo_path, new_real_path = make_working_file(clone, '', new_path)
    clone.git.mv(old_path, new_path, f=True)

    clone.index.commit('Renamed "%s" to "%s"' % (old_path, new_path))
    active_branch_name = clone.active_branch.name

    #
    # Sync with the default and upstream branches in case someone made a change.
    #
    for sync_branch_name in (active_branch_name, default_branch_name):
        msg = 'Merged work from "%s"' % sync_branch_name
        clone.git.fetch('origin', sync_branch_name)

        try:
            clone.git.merge('FETCH_HEAD', '--no-ff', m=msg)

        except:
            # raise the two commits in conflict.
            remote_commit = clone.refs[_origin(sync_branch_name)].commit

            clone.git.reset(hard=True)
            raise MergeConflict(remote_commit, clone.commit())

    clone.git.push('origin', active_branch_name)

    return clone.active_branch.commit

def needs_peer_review(repo, default_branch_name, working_branch_name):
    ''' Returns true if the active branch appears to be in need of review.
    '''
    base_commit = repo.git.merge_base(default_branch_name, working_branch_name)
    last_commit = repo.branches[working_branch_name].commit.hexsha

    if base_commit == last_commit:
        return False

    return not is_peer_approved(repo, default_branch_name, working_branch_name) \
        and not is_peer_rejected(repo, default_branch_name, working_branch_name)

def ineligible_peer(repo, default_branch_name, working_branch_name):
    ''' Returns the email address of a peer who shouldn't review this branch.
    '''
    if needs_peer_review(repo, default_branch_name, working_branch_name):
        return repo.branches[working_branch_name].commit.author.email

    return None

def is_peer_approved(repo, default_branch_name, working_branch_name):
    ''' Returns true if the active branch appears peer-reviewed.
    '''
    base_commit = repo.git.merge_base(default_branch_name, working_branch_name)
    last_commit = repo.branches[working_branch_name].commit

    if 'Approved changes.' not in last_commit.message:
        # To do: why does "commit: " get prefixed to the message?
        return False

    reviewer_email = last_commit.author.email
    commit_log = last_commit.iter_parents() # reversed(repo.branches[working_branch_name].log())

    for commit in commit_log:
        if commit == base_commit:
            break

        if reviewer_email and commit.author.email != reviewer_email:
            return True

    return False

def is_peer_rejected(repo, default_branch_name, working_branch_name):
    ''' Returns true if the active branch appears to have suggestion from a peer.
    '''
    base_commit = repo.git.merge_base(default_branch_name, working_branch_name)
    last_commit = repo.branches[working_branch_name].commit

    if 'Provided feedback.' not in last_commit.message:
        # To do: why does "commit: " get prefixed to the message?
        return False

    reviewer_email = last_commit.author.email
    commit_log = last_commit.iter_parents() # reversed(repo.branches[working_branch_name].log())

    for commit in commit_log:
        if commit == base_commit:
            break

        if reviewer_email and commit.author.email != reviewer_email:
            return True

    return False

def mark_as_reviewed(clone):
    ''' Adds a new empty commit with the message "Approved changes."
    '''
    clone.index.commit('Approved changes.')
    active_branch_name = clone.active_branch.name

    #
    # Sync with the default and upstream branches in case someone made a change.
    #
    for sync_branch_name in (active_branch_name, ):
        msg = 'Merged work from "%s"' % sync_branch_name
        clone.git.fetch('origin', sync_branch_name)

        try:
            clone.git.merge('FETCH_HEAD', '--no-ff', m=msg)

        except:
            # raise the two commits in conflict.
            remote_commit = clone.refs[_origin(sync_branch_name)].commit

            clone.git.reset(hard=True)
            raise MergeConflict(remote_commit, clone.commit())

    clone.git.push('origin', active_branch_name)

    return clone.active_branch.commit

def provide_feedback(clone, comments):
    ''' Adds a new empty commit with the message "Provided feedback."
    '''
    clone.index.commit('Provided feedback.\n\n' + comments)
    active_branch_name = clone.active_branch.name

    #
    # Sync with the default and upstream branches in case someone made a change.
    #
    for sync_branch_name in (active_branch_name, ):
        msg = 'Merged work from "%s"' % sync_branch_name
        clone.git.fetch('origin', sync_branch_name)

        try:
            clone.git.merge('FETCH_HEAD', '--no-ff', m=msg)

        except:
            # raise the two commits in conflict.
            remote_commit = clone.refs[_origin(sync_branch_name)].commit

            clone.git.reset(hard=True)
            raise MergeConflict(remote_commit, clone.commit())

    clone.git.push('origin', active_branch_name)

    return clone.active_branch.commit

def get_rejection_messages(repo, default_branch_name, working_branch_name):
    '''
    '''
    messages = []

    base_commit = repo.git.merge_base(default_branch_name, working_branch_name)
    last_commit = repo.branches[working_branch_name].commit
    commit_log = chain([last_commit], last_commit.iter_parents())

    for commit in commit_log:
        if commit.hexsha == base_commit:
            break

        if 'Provided feedback.' in commit.message:
            email = commit.author.email
            message = commit.message[commit.message.index('Provided feedback.'):][len('Provided feedback.'):]
            yield (email, message)
