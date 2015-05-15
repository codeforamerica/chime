# -- coding: utf-8 --
import os
import logging
from os import mkdir
from os.path import join, split, exists, isdir
from itertools import chain
from git.cmd import GitCommandError
import hashlib
import yaml
import edit_functions

TASK_METADATA_FILENAME = u'_task.yml'
BRANCH_NAME_LENGTH = 7
DESCRIPTION_MAX_LENGTH = 15

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
        active_branch_name = clone.active_branch.name
        clone.git.checkout(new_branch_name)
        clone.git.pull('origin', new_branch_name)
        clone.git.checkout(active_branch_name)
        return clone.branches[new_branch_name]

    except GitCommandError:
        return None

    return None

def get_start_branch(clone, default_branch_name, task_description, task_beneficiary, author_email):
    ''' Start a new repository branch, push it to origin and return it.

        Don't touch the working directory. If an existing branch is found
        with the same name, use it instead of creating a fresh branch.
    '''

    # make a branch name based on unique details
    new_branch_name = make_branch_name(task_description, task_beneficiary, author_email)

    existing_branch = get_existing_branch(clone, default_branch_name, new_branch_name)
    if existing_branch:
        return existing_branch

    # create a brand new branch
    start_point = get_branch_start_point(clone, default_branch_name, new_branch_name)
    branch = clone.create_head(new_branch_name, commit=start_point, force=True)
    clone.git.push('origin', new_branch_name)

    # create the task metadata file in the new branch
    active_branch_name = clone.active_branch.name
    clone.git.checkout(new_branch_name)
    metadata_values = {"author_email": author_email, "task_description": task_description, "task_beneficiary": task_beneficiary}
    save_task_metadata_for_branch(clone, default_branch_name, metadata_values)
    clone.git.checkout(active_branch_name)

    return branch

def ignore_task_metadata_on_merge(clone):
    ''' Tell this repo to ignore merge conflicts on the task metadata file
    '''
    # create the .git/info/attributes file if it doesn't exist
    attributes_path = join(clone.git_dir, 'info/attributes')
    if not exists(attributes_path):
        content = u'{} merge=ignored'.format(TASK_METADATA_FILENAME)
        with open(attributes_path, 'w') as file:
            file.write(content.encode('utf8'))

    # set the config (it's okay to set redundantly)
    c_writer = clone.config_writer()
    c_writer.set_value('merge "ignored"', 'driver', 'true')
    c_writer = None

def save_task_metadata_for_branch(clone, default_branch_name, values={}):
    ''' Save the passed values to the branch's task metadata file, preserving values that aren't overwritten.
    '''
    # Get the current task metadata (if any)
    task_metadata = get_task_metadata_for_branch(clone)
    check_metadata = dict(task_metadata)
    # :NOTE: changing the commit message may break tests
    verbed = u'Created' if task_metadata == {} else u'Updated'
    message = u'{} task metadata file "{}"'.format(verbed, TASK_METADATA_FILENAME)
    # update with the new values
    try:
        task_metadata.update(values)
    except ValueError:
        raise Exception(u'Unable to save task metadata for branch.', u'error')

    # Don't write if there haven't been any changes
    if check_metadata == task_metadata:
        return

    # Dump the updated task metadata to disk
    # Use newline-preserving block literal form.
    # yaml.SafeDumper ensures best unicode output.
    dump_kwargs = dict(Dumper=yaml.SafeDumper, default_flow_style=False,
                       canonical=False, default_style='|', indent=2,
                       allow_unicode=True)

    task_file_path = join(clone.working_dir, TASK_METADATA_FILENAME)
    with open(task_file_path, 'w') as file:
        file.seek(0)
        file.truncate()
        yaml.dump(task_metadata, file, **dump_kwargs)

    # add & commit the file to the branch
    return save_working_file(clone, TASK_METADATA_FILENAME, message, clone.commit().hexsha, default_branch_name)

def delete_task_metadata_for_branch(clone, default_branch_name):
    ''' Delete the task metadata file and return its contents
    '''
    task_metadata = get_task_metadata_for_branch(clone)
    file_path, do_save = edit_functions.delete_file(clone, None, TASK_METADATA_FILENAME)
    if do_save:
        message = u'Deleted task metadata file "{}"'.format(TASK_METADATA_FILENAME)
        save_working_file(clone, TASK_METADATA_FILENAME, message, clone.commit().hexsha, default_branch_name)
    return task_metadata

def get_task_metadata_for_branch(clone, working_branch_name=None):
    ''' Retrieve task metadata from the file
    '''
    task_metadata = {}
    task_file_contents = get_file_contents_from_branch(clone, TASK_METADATA_FILENAME, working_branch_name)
    if task_file_contents:
        task_metadata = yaml.safe_load(task_file_contents)
        if type(task_metadata) is not dict:
            raise ValueError()

    return task_metadata

def get_file_contents_from_branch(clone, file_path, working_branch_name=None):
    ''' Return the contents of the file in the passed branch without checking it out.
    '''
    # use the active branch if no branch name was passed
    branch_name = working_branch_name if working_branch_name else clone.active_branch.name
    if branch_name in clone.heads:
        try:
            blob = (clone.heads[branch_name].commit.tree / file_path)
        except KeyError:
            return None

        return blob.data_stream.read().decode('utf-8')

    return None

def verify_file_exists_in_branch(clone, file_path, working_branch_name=None):
    ''' Check whether the indicated file exists.
    '''
    # use the active branch if no branch name was passed
    branch_name = working_branch_name if working_branch_name else clone.active_branch.name
    if branch_name in clone.heads:
        try:
            (clone.heads[branch_name].commit.tree / file_path)
        except KeyError:
            return False

        return True

    return False

def make_shortened_task_description(task_description):
    ''' Shorten the passed description, cutting on a word boundary if possible
    '''
    if len(task_description) <= DESCRIPTION_MAX_LENGTH:
        return task_description

    if u' ' not in task_description[:DESCRIPTION_MAX_LENGTH]:
        return task_description[:DESCRIPTION_MAX_LENGTH]

    # crop to the nearest word boundary
    suggested = u' '.join(task_description[:DESCRIPTION_MAX_LENGTH + 1].split(' ')[:-1])
    # if the cropped text is too short, just cut at the max length
    if len(suggested) < DESCRIPTION_MAX_LENGTH * .66:
        return task_description[:DESCRIPTION_MAX_LENGTH]

    return suggested

def make_branch_sha(task_description, task_beneficiary, author_email):
    ''' use details about a branch to generate a 'unique' name
    '''
    # get epoch seconds as a string
    seed = u'{}{}{}'.format(unicode(task_description), unicode(task_beneficiary), unicode(author_email))
    return hashlib.sha1(seed.encode('utf-8')).hexdigest()

def make_branch_name(task_description, task_beneficiary, author_email):
    ''' Return a short, URL- and Git-compatible name for a branch
    '''
    short_sha = make_branch_sha(task_description, task_beneficiary, author_email)[0:BRANCH_NAME_LENGTH]
    return short_sha

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
    # get the task metadata
    task_metadata = get_task_metadata_for_branch(clone)

    try:
        kwargs = dict(task_metadata)
        kwargs.update({"working_branch_name": working_branch_name})
        message = 'Merged work by {author_email} for the task {task_description} (for {task_beneficiary}) from branch {working_branch_name}'.format(**kwargs)
    except KeyError:
        message = 'Merged work from "{}"'.format(working_branch_name)

    clone.git.checkout(default_branch_name)
    clone.git.pull('origin', default_branch_name)

    #
    # Merge the working branch back to the default branch.
    #
    try:
        clone.git.merge(working_branch_name, '--no-ff', m=message)

    except GitCommandError:
        # raise the two commits in conflict.
        remote_commit = clone.refs[_origin(default_branch_name)].commit
        clone.git.reset(default_branch_name, hard=True)
        clone.git.checkout(working_branch_name)
        raise MergeConflict(remote_commit, clone.commit())

    else:
        # remove the task metadata file if it exists
        _, do_save = edit_functions.delete_file(clone, None, TASK_METADATA_FILENAME)
        if do_save:
            clone.index.remove([TASK_METADATA_FILENAME])
            # amend the merge commit to include the deletion and push it
            clone.git.commit('--amend', '--no-edit', '--reset-author')

    # now push the changes to origin
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
    ''' Determine the relative and absolute location of a new file, create
        any directories in its path that don't already exist, and return
        its local git and real absolute paths. Does not create the actual
        file.

        `dir` is the existing directory the file is being created in

        `path` is the path that was entered to create the file, which may
               include existing or new directories
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

def sync_with_default_and_upstream_branches(clone, sync_branch_name):
    ''' Sync the passed branch with default and upstream branches.
    '''
    msg = 'Merged work from "%s"' % sync_branch_name
    clone.git.fetch('origin', sync_branch_name)

    try:
        clone.git.merge('FETCH_HEAD', '--no-ff', m=msg)

    except GitCommandError:
        # raise the two commits in conflict.
        remote_commit = clone.refs[_origin(sync_branch_name)].commit

        clone.git.reset(hard=True)
        raise MergeConflict(remote_commit, clone.commit())

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
        try:
            sync_with_default_and_upstream_branches(clone, sync_branch_name)
        except MergeConflict as conflict:
            raise conflict

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
        try:
            sync_with_default_and_upstream_branches(clone, sync_branch_name)
        except MergeConflict as conflict:
            raise conflict

    clone.git.push('origin', active_branch_name)

    return clone.active_branch.commit

def needs_peer_review(repo, default_branch_name, working_branch_name):
    ''' Returns true if the active branch appears to be in need of review.
    '''
    base_commit_hexsha = repo.git.merge_base(default_branch_name, working_branch_name)
    last_commit = repo.branches[working_branch_name].commit
    # we don't need peer review if the only change is
    # the commit of the task metadata file
    if TASK_METADATA_FILENAME in last_commit.message:
        last_commit = last_commit.parents[0]

    if base_commit_hexsha == last_commit.hexsha:
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
        # TODO: why does "commit: " get prefixed to the message?
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
        # TODO: why does "commit: " get prefixed to the message?
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
        try:
            sync_with_default_and_upstream_branches(clone, sync_branch_name)
        except MergeConflict as conflict:
            raise conflict

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
        try:
            sync_with_default_and_upstream_branches(clone, sync_branch_name)
        except MergeConflict as conflict:
            raise conflict

    clone.git.push('origin', active_branch_name)

    return clone.active_branch.commit

def get_rejection_messages(repo, default_branch_name, working_branch_name):
    '''
    '''
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
