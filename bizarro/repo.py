import os, logging
from os import environ
from os.path import join, split, exists

class MergeConflict (Exception):
    def __init__(self, remote_commit, local_commit):
        self.remote_commit = remote_commit
        self.local_commit = local_commit
    
    def __str__(self):
        return 'MergeConflict(%s, %s)' % (self.remote_commit, self.local_commit)

def _origin(branch_name):
    return 'origin/' + branch_name

def start_branch(clone, default_branch_name, new_branch_name):
    ''' Start a new repository branch, push it to origin and return it.
    
        Don't touch the working directory. If an existing branch is found
        with the same name, use it instead of creating a fresh branch.
    '''
    clone.git.fetch('origin')
    
    if _origin(new_branch_name) in clone.refs:
        start_point = clone.refs[_origin(new_branch_name)].commit
    else:
        start_point = clone.branches[default_branch_name].commit
    
    # Start or update the branch, letting origin override the local repo.
    logging.debug('start_branch() start_point is %s' % repr(start_point))

    # See if it already matches start_point
    if new_branch_name in clone.branches:
        if clone.branches[new_branch_name].commit == start_point:
            return clone.branches[new_branch_name]

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
    
    clone.branches[default_branch_name].checkout()
    clone.git.pull('origin', default_branch_name)
    clone.git.merge(working_branch_name, '--no-ff', s='ours', m=msg) # "ours" = default
    clone.git.push('origin', default_branch_name)
    
    #
    # Delete the working branch.
    #
    clone.remotes.origin.push(':' + working_branch_name)
    clone.delete_head([working_branch_name])

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
    stuff = []
    
    for i in range(len(dirs)):
        dir_path = join(clone.working_dir, os.sep.join(dirs[:i+1]))
        
        if not isdir(dir_path):
            mkdir(dir_path)
    
    return repo_path, real_path

def save_working_file(clone, path, message, base_sha, default_branch_name):
    ''' Save a file in the working dir, push it to origin, return the commit.
    
        Rely on Git environment variables for author emails and names.
        
        After committing the new file, attempts to rebase the working branch
        on the default branch and the origin working branch in turn, to
        surface possible merge problems early. Might raise a MergeConflict.
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
        try:
            # sync: pull --rebase followed by push.
            clone.git.pull('origin', sync_branch_name, rebase=True)

        except:
            # raise the two commits in conflict.
            clone.git.fetch('origin')
            remote_commit = clone.refs[_origin(sync_branch_name)].commit

            clone.git.rebase(abort=True)
            clone.git.reset(hard=True)
            raise MergeConflict(remote_commit, clone.commit())

        else:
            clone.git.push('origin', sync_branch_name)
    
    return clone.active_branch.commit
