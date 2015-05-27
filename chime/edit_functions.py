
from os.path import exists, isdir, join, split, sep
from os import rmdir, remove

import repo_functions
from .jekyll_functions import dump_jekyll_doc

def update_page(clone, file_path, front, body):
    ''' Update existing Jekyll page in the working directory.
    '''
    full_path = join(clone.working_dir, file_path)

    if not exists(full_path):
        raise Exception()

    with open(full_path, 'w') as file:
        dump_jekyll_doc(front, body, file)

def create_path_to_page(clone, dir_path, file_path, front, body, index_filename):
    ''' Build non-existing directories in file_path as category directories.
    '''
    # Build a full directory path.
    head, dirs = split(file_path)[0], []

    while head:
        head, check_dir = split(head)
        dirs.insert(0, check_dir)

    if '..' in dirs:
        raise Exception('Invalid path component.')

    # Build the category directory tree.
    for i in range(len(dirs)):
        create_new_page(clone, dir_path, join(sep.join(dirs[:i + 1]), index_filename), front, body)

def create_new_page(clone, dir_path, file_path, front, body):
    ''' Create a new Jekyll page in the working directory, return its path.
    '''
    file_path, full_path = repo_functions.make_working_file(clone, dir_path, file_path)

    if exists(full_path):
        raise Exception(u'create_new_page: path already exists!')

    with open(full_path, 'w') as file:
        dump_jekyll_doc(front, body, file)

    return file_path

def upload_new_file(clone, path, upload):
    ''' Upload a new file in the working directory, return its path.
    '''
    file_path, full_path = repo_functions.make_working_file(clone, path, upload.filename)

    if not exists(full_path):
        with open(full_path, 'w') as file:
            upload.save(file)

    return file_path

def delete_file(clone, path, file_name):
    ''' Delete a file from the working directory, return its path.
    '''
    file_path = join(path or '', file_name)
    full_path = join(clone.working_dir, file_path)
    do_save = False

    if isdir(full_path):
        rmdir(full_path)
    elif exists(full_path):
        remove(full_path)
        do_save = True

    return (file_path, do_save)
