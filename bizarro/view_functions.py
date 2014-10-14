from os.path import join, isdir, realpath, basename
from os import listdir, environ
from urllib import quote, unquote
from mimetypes import guess_type
from functools import wraps

from git import Repo
from flask import request, session, current_app, redirect

from .repo_functions import start_branch
from .href import needs_redirect, get_redirect

def dos2unix(string):
    ''' Returns a copy of the strings with line-endings corrected.
    '''
    return string.replace('\r\n', '\n').replace('\r', '\n')

def get_repo(flask_app):
    ''' Gets repository for the current user, cloned from the origin.
    '''
    dir_name = 'repo-' + session.get('email', 'nobody')
    user_dir = realpath(join(flask_app.config['WORK_PATH'], quote(dir_name)))
    
    if isdir(user_dir):
        user_repo = Repo(user_dir)
        user_repo.git.reset(hard=True)
        user_repo.remotes.origin.fetch()
        return user_repo
    
    source_repo = Repo(flask_app.config['REPO_PATH'])
    user_repo = source_repo.clone(user_dir, bare=False)
    
    return user_repo

def name_branch(description):
    ''' Generate a name for a branch from a description.
    
        Prepends with session.email, and replaces spaces with dashes.

        TODO: follow rules in http://git-scm.com/docs/git-check-ref-format.html
    '''
    safe_description = description.replace('.', '-').replace(' ', '-')
    return quote(session['email'], '@.-_') + '/' + quote(safe_description, '-_!')

def branch_name2path(branch_name):
    ''' Quote the branch name for safe use in URLs.
    
        Uses urllib.quote() *twice* because Flask still interprets
        '%2F' in a path as '/', so it must be double-escaped to '%252F'.
    '''
    return quote(quote(branch_name, ''), '')

def branch_var2name(branch_path):
    ''' Unquote the branch name for use by Git.
    
        Uses urllib.unquote() *once* because Flask routing already converts
        raw paths to variables before they arrive here.
    '''
    return unquote(branch_path)

def path_type(file_path):
    '''
    '''
    if isdir(file_path):
        return 'folder'
    
    if str(guess_type(file_path)[0]).startswith('image/'):
        return 'image'
    
    return 'file'

def is_editable(file_path):
    '''
    '''
    try:
        if isdir(file_path):
            return False
    
        if open(file_path).read(4).startswith('---'):
            return True
    
    except:
        pass
    
    return False

def login_required(route_function):
    ''' Login decorator for route functions.
    
        Adapts http://flask.pocoo.org/docs/patterns/viewdecorators/
    '''
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        email = session.get('email', None)
    
        if not email:
            return redirect('/')
        
        environ['GIT_AUTHOR_NAME'] = ' '
        environ['GIT_AUTHOR_EMAIL'] = email
        environ['GIT_COMMITTER_NAME'] = ' '
        environ['GIT_COMMITTER_EMAIL'] = email

        return route_function(*args, **kwargs)
    
    return decorated_function

def _remote_exists(repo, remote):
    ''' Check whether a named remote exists in a repository.
    
        This should be as simple as `remote in repo.remotes`,
        but GitPython has a bug in git.util.IterableList:

            https://github.com/gitpython-developers/GitPython/issues/11
    '''
    try:
        repo.remotes[remote]

    except IndexError:
        return False

    else:
        return True

def synch_required(route_function):
    ''' Decorator for routes needing a repository synched to upstream.
    
        Syncs with upstream origin before and after. Use below @login_required.
    '''
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        print '<' * 40 + '-' * 40

        repo = Repo(current_app.config['REPO_PATH'])
    
        if _remote_exists(repo, 'origin'):
            print '  fetching origin', repo
            repo.git.fetch('origin', with_exceptions=True)

        print '- ' * 40

        response = route_function(*args, **kwargs)
        
        # Push to origin only if the request method indicates a change.
        if request.method in ('PUT', 'POST', 'DELETE'):
            print '- ' * 40

            if _remote_exists(repo, 'origin'):
                print '  pushing origin', repo
                repo.git.push('origin', with_exceptions=True)

        print '-' * 40 + '>' * 40

        return response
    
    return decorated_function

def synched_checkout_required(route_function):
    ''' Decorator for routes needing a repository checked out to a branch.
    
        Syncs with upstream origin before and after. Use below @login_required.
    '''
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        print '<' * 40 + '-' * 40

        repo = Repo(current_app.config['REPO_PATH'])
        
        if _remote_exists(repo, 'origin'):
            print '  fetching origin', repo
            repo.git.fetch('origin', with_exceptions=True)

        checkout = get_repo(current_app)
        branch_name = branch_var2name(kwargs['branch'])
        master_name = current_app.config['default_branch']
        branch = start_branch(checkout, master_name, branch_name)
        branch.checkout()

        print '  checked out to', branch
        print '- ' * 40

        response = route_function(*args, **kwargs)
        
        # Push to origin only if the request method indicates a change.
        if request.method in ('PUT', 'POST', 'DELETE'):
            print '- ' * 40

            if _remote_exists(repo, 'origin'):
                print '  pushing origin', repo
                repo.git.push('origin', with_exceptions=True)

        print '-' * 40 + '>' * 40

        return response
    
    return decorated_function

def sorted_paths(repo, branch, path=None):
    full_path = join(repo.working_dir, path or '.').rstrip('/')
    all_sorted_files_dirs = sorted(listdir(full_path))

    filtered_sorted_files_dirs = [i for i in all_sorted_files_dirs if not i.startswith('.') ]
    file_names = [n for n in filtered_sorted_files_dirs if not n.startswith('_')]
    view_paths = [join('/tree/%s/view' % branch_name2path(branch), join(path or '', fn))
                  for fn in file_names]

    full_paths = [join(full_path, name) for name in file_names]
    path_pairs = zip(full_paths, view_paths)

    list_paths = [(basename(fp), vp, path_type(fp), is_editable(fp))
                  for (fp, vp) in path_pairs if realpath(fp) != repo.git_dir]
    return list_paths

def directory_paths(branch, path=None):
    root_dir_with_path = [('root', '/tree/%s/edit' % branch_name2path(branch))]
    if path is None:
        return root_dir_with_path
    directory_list = [dir_name for dir_name in path.split('/')
                      if dir_name and not dir_name.startswith('.')]

    dirs_with_paths = [(dir_name, get_directory_path(branch, path, dir_name))
                       for dir_name in directory_list]
    return root_dir_with_path + dirs_with_paths

def get_directory_path(branch, path, dir_name):
    dir_index = path.find(dir_name+'/')
    current_path = path[:dir_index] + dir_name + '/'
    return join('/tree/%s/edit' % branch_name2path(branch), current_path)

def should_redirect():
    ''' Return True if the current flask.request should redirect.
    '''
    if request.args.get('go') == u'\U0001f44c':
        return False
    
    referer_url = request.headers.get('Referer')
    
    if not referer_url:
        return False
    
    return needs_redirect(request.host, request.path, referer_url)

def make_redirect():
    ''' Return a flask.redirect for the current flask.request.
    '''
    referer_url = request.headers.get('Referer')

    other = redirect(get_redirect(request.path, referer_url), 302)
    other.headers['Cache-Control'] = 'no-store private'
    other.headers['Vary'] = 'Referer'

    return other
