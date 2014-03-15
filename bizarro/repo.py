def start_branch(clone, default_branch_name, new_branch_name):
    ''' Start a new repository branch, push it to origin and return it.
    '''
    clone.remotes.origin.fetch()
    
    if 'origin/' + new_branch_name in clone.refs:
        start_point = clone.refs['origin/' + new_branch_name]
    else:
        start_point = clone.branches[default_branch_name]
    
    branch = clone.create_head(new_branch_name, commit=start_point)
    clone.remotes.origin.push(new_branch_name)
    
    return branch

def save_working_file(clone, path, message, base_sha):
    ''' Save a file in the working dir and push it to origin.
    '''
    if clone.active_branch.commit.hexsha != base_sha:
        raise Exception('Out of date SHA: %s' % base_sha)
    
    clone.index.add([path])
    clone.index.commit(message)
    clone.remotes.origin.push(clone.active_branch.name)
