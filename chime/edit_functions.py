
from os.path import exists, isdir, join, split, sep
from os import rmdir, remove
from slugify import slugify
from .jekyll_functions import dump_jekyll_doc

def update_page(clone, file_path, front, body):
    ''' Update existing Jekyll page in the working directory.
    '''
    full_path = join(clone.working_dir, file_path)

    if not exists(full_path):
        raise Exception()

    with open(full_path, 'w') as file:
        dump_jekyll_doc(front, body, file)

def make_slug_path(path):
    ''' Slugify and return the passed path, splitting by / if necessary.
    '''
    slugified_segments = []
    for segment in path.split('/'):
        slugified_segments.append(slugify(segment))
    return '/'.join(slugified_segments)

def create_path_to_page(clone, dir_path, request_path, front, body, filename):
    ''' Build non-existing directories in request_path as category directories.
    '''
    # Build a full directory path.
    dirs = clone.dirs_for_path(request_path)

    # Build the category directory tree.
    file_paths = []
    for i in range(len(dirs)):
        file_path = create_new_page(clone, dir_path, join(sep.join(dirs[:i + 1]), filename), front, body)
        file_paths.append(file_path)

    return file_paths

def create_new_page(clone, dir_path, request_path, front, body):
    ''' Create a new Jekyll page in the working directory, return its path.
    '''
    split_path = split(request_path)
    slug_path = join(make_slug_path(split_path[0]), split_path[1])
    front_copy = dict(front)
    if not front_copy['title']:
        front_copy['title'] = request_path.split('/')[-2]
    file_path = clone.repo_path(dir_path, slug_path)
    clone.create_directories_if_necessary(file_path)

    if clone.exists(file_path):
        raise Exception(u'create_new_page: path already exists!')

    with open(clone.full_path(file_path), 'w') as file:
        dump_jekyll_doc(front_copy, body, file)

    return file_path

def upload_new_file(clone, dir_path, upload):
    ''' Upload a new file in the working directory, return its path.
    '''

    file_path = clone.repo_path(dir_path, upload.filename)

    if not clone.exists(file_path):
        with open(clone.full_path(file_path), 'w') as file:
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
