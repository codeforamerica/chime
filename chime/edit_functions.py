
from os import walk
from os.path import exists, join, split, sep
from slugify import slugify
from .jekyll_functions import dump_jekyll_doc
from re import search, sub

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

    return file_paths, dirs

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

def delete_file(clone, file_path):
    ''' Delete files from the working directory, return their paths.
    '''
    full_path = join(clone.working_dir, file_path)
    do_save = False

    # pre-find all the files that're going to be deleted
    doomed_files = []
    for (dirpath, dirnames, filenames) in walk(full_path):
        doomed_files.extend([sub('{}/'.format(clone.working_dir), '', join(dirpath, item)) for item in filenames])

    removed_paths = []
    if exists(full_path):
        removed_path_notes = clone.git.rm('-r', full_path).splitlines()
        # paths are returned by git rm in the format: "rm 'path/goes/here'"; extract the paths
        for note in removed_path_notes:
            removed_paths.append(search(r"rm '(.+?)'", note).group(1))
        do_save = len(removed_paths) > 0

    return (removed_paths, do_save)
