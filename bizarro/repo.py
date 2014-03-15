import os, logging
from os.path import join, split

def start_branch(clone, default_branch_name, new_branch_name):
    ''' Start a new repository branch, push it to origin and return it.
    '''
    clone.remotes.origin.fetch()
    
    if 'origin/' + new_branch_name in clone.refs:
        start_point = clone.refs['origin/' + new_branch_name].commit
    else:
        start_point = clone.branches[default_branch_name].commit
    
    logging.debug('start_branch() start_point is %s' % repr(start_point))
    branch = clone.create_head(new_branch_name, commit=start_point)
    clone.remotes.origin.push(new_branch_name)
    
    return branch

def make_working_file(clone, dir, path):
    ''' Create a new working file, return its local git and real absolute paths.
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

def save_working_file(clone, path, message, base_sha):
    ''' Save a file in the working dir and push it to origin.
    '''
    if clone.active_branch.commit.hexsha != base_sha:
        raise Exception('Out of date SHA: %s' % base_sha)
    
    clone.index.add([path])
    clone.index.commit(message)
    clone.remotes.origin.push(clone.active_branch.name)
