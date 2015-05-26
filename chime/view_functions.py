from __future__ import absolute_import
from logging import getLogger
Logger = getLogger('chime.view_functions')

from os.path import join, isdir, realpath, basename, exists, split, sep
from datetime import datetime
from os import listdir, environ
from urllib import quote, unquote
from urlparse import urljoin, urlparse, urlunparse
from mimetypes import guess_type
from functools import wraps
from io import BytesIO
import csv
import re

from git import Repo
from dateutil import parser, tz
from dateutil.relativedelta import relativedelta
from flask import request, session, current_app, redirect, flash
from requests import get

from .repo_functions import get_existing_branch, ignore_task_metadata_on_merge
from .jekyll_functions import load_jekyll_doc
from .href import needs_redirect, get_redirect

from fcntl import flock, LOCK_EX, LOCK_UN, LOCK_SH

# files that match these regex patterns will not be shown in the file explorer
CONTENT_FILE_EXTENSION = u'markdown'
CATEGORY_LAYOUT = 'category'
ARTICLE_LAYOUT = 'article'
FILE_FILTERS = [
    r'^\.',
    r'^_',
    r'\.lock$',
    r'Gemfile',
    r'LICENSE',
    r'index\.{}'.format(CONTENT_FILE_EXTENSION)
]
FILE_FILTERS_COMPILED = re.compile('(' + '|'.join(FILE_FILTERS) + ')')

class WriteLocked:
    ''' Context manager for a locked file open in a+ mode, seek(0).
    '''
    def __init__(self, fname):
        self.fname = fname
        self.file = None

    def __enter__(self):
        self.file = open(self.fname, 'a+')
        flock(self.file, LOCK_EX)
        self.file.seek(0)
        return self.file

    def __exit__(self, *args):
        flock(self.file, LOCK_UN)
        self.file.close()

class ReadLocked:
    ''' Context manager for a locked file open in r mode, seek(0).
    '''
    def __init__(self, fname):
        self.fname = fname
        self.file = None

    def __enter__(self):
        self.file = open(self.fname, 'r')
        flock(self.file, LOCK_SH)
        return self.file

    def __exit__(self, *args):
        flock(self.file, LOCK_UN)
        self.file.close()

def dos2unix(string):
    ''' Returns a copy of the strings with line-endings corrected.
    '''
    return string.replace('\r\n', '\n').replace('\r', '\n') if string else string

def get_repo(flask_app):
    ''' Gets repository for the current user, cloned from the origin.

        Uses the first-ever commit in the origin repository to name
        the cloned directory, to reduce history conflicts when tweaking
        the repository during development.
    '''
    source_repo = Repo(flask_app.config['REPO_PATH'])
    first_commit = list(source_repo.iter_commits())[-1].hexsha
    dir_name = 'repo-{}-{}'.format(first_commit[:8], session.get('email', 'nobody'))
    user_dir = realpath(join(flask_app.config['WORK_PATH'], quote(dir_name)))

    if isdir(user_dir):
        user_repo = Repo(user_dir)
        user_repo.git.reset(hard=True)
        user_repo.remotes.origin.fetch()
    else:
        user_repo = source_repo.clone(user_dir, bare=False)

    # tell git to ignore merge conflicts on the task metadata file
    ignore_task_metadata_on_merge(user_repo)

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
    ''' Returns the type of file at the passed path
    '''
    if isdir(file_path):
        return 'folder'

    if str(guess_type(file_path)[0]).startswith('image/'):
        return 'image'

    return 'file'

def path_display_type(file_path):
    ''' Returns a type matching how the file at the passed path should be displayed
    '''
    if is_article_dir(file_path):
        return 'article'

    if is_category_dir(file_path):
        return 'category'

    return path_type(file_path)

# ONLY CALLED FROM sorted_paths()
def is_display_editable(file_path):
    ''' Returns True if the file at the passed path is either an editable file,
        or a directory containing only an editable index file.
    '''
    return (is_editable(file_path) or is_article_dir(file_path))

def is_article_dir(file_path):
    ''' Returns True if the file at the passed path is a directory containing only an index file with an article jekyll layout.
    '''
    return is_dir_with_layout(file_path, ARTICLE_LAYOUT, True)

def is_category_dir(file_path):
    ''' Returns True if the file at the passed path is a directory containing only an index file with a category jekyll layout.
    '''
    return is_dir_with_layout(file_path, CATEGORY_LAYOUT, False)

# ONLY CALLED FROM THE TWO FUNCTIONS ABOVE
def is_editable(file_path, layout=None):
    ''' Returns True if the file at the passed path is not a directory, and has jekyll
        front matter with the passed layout.
    '''
    try:
        # directories aren't editable
        if isdir(file_path):
            return False

        # files with the passed layout are editable
        if layout:
            with open(file_path) as file:
                front_matter, _ = load_jekyll_doc(file)
            return ('layout' in front_matter and front_matter['layout'] == layout)

        # if no layout was passed, files with front matter are editable
        if open(file_path).read(4).startswith('---'):
            return True

    except:
        pass

    return False

def is_dir_with_layout(file_path, layout, only=True):
    ''' Returns True if the file at the passed path is a directory containing a index file with the passed jekyll layout variable.
        When only is True, it's required that there be no 'visible' files or directories in the directory.
    '''
    if isdir(file_path):
        # it's a directory
        index_path = join(file_path or u'', u'index.{}'.format(CONTENT_FILE_EXTENSION))
        if not exists(index_path) or not is_editable(index_path, layout):
            # there's no index file in the directory or it's not editable
            return False

        visible_file_count = len([name for name in listdir(file_path) if not FILE_FILTERS_COMPILED.search(name)])
        if visible_file_count == 0 or not only:
            # there's only an index file in the directory or multiple files are okay
            return True

    # it's not a directory
    return False

def relative_datetime_string(datetime_string):
    ''' Get a relative date for a string.
    '''
    # the date is naive by default; explicitly set the timezone as UTC
    now_utc = datetime.utcnow()
    now_utc = now_utc.replace(tzinfo=tz.tzutc())

    return get_relative_date_string(parser.parse(datetime_string), now_utc)

def get_relative_date_string(file_datetime, now_utc):
    ''' Get a natural-language representation of a period of time.
    '''
    default = "just now"

    # if there's no passed date, or if the passed date is in the future, return the default
    if not file_datetime or now_utc < file_datetime:
        return default

    time_ago = relativedelta(now_utc, file_datetime)

    periods = (
        (time_ago.years, "year", "years"),
        (time_ago.months, "month", "months"),
        (time_ago.days / 7, "week", "weeks"),
        (time_ago.days, "day", "days"),
        (time_ago.hours, "hour", "hours"),
        (time_ago.minutes, "minute", "minutes")
    )

    for period, singular, plural in periods:
        if period:
            return "%d %s ago" % (period, singular if period == 1 else plural)

    return default

def get_epoch(dt):
    ''' Get an accurate epoch seconds value for the passed datetime object.
    '''
    epoch = datetime.utcfromtimestamp(0)
    delta = dt - epoch
    return delta.total_seconds()

def get_auth_data_file(data_href):
    ''' Get a file-like object for authentication CSV data.
    '''
    csv_url = get_auth_csv_url(data_href)

    url_base = 'file://{}'.format(realpath(__file__))
    real_url = urljoin(url_base, csv_url)

    if urlparse(real_url).scheme in ('file', ''):
        file_path = urlparse(real_url).path
        Logger.debug('Opening {} as auth CSV file'.format(file_path))
        return open(file_path, 'r')

    Logger.debug('Opening {} as auth CSV file'.format(real_url))
    return BytesIO(get(real_url).content)

def get_auth_csv_url(data_href):
    ''' Optionally convert link to GDocs spreadsheet to CSV format.
    '''
    _, host, path, _, _, _ = urlparse(data_href)

    gdocs_pat = re.compile(r'/spreadsheets/d/(?P<id>[\w\-]+)')
    path_match = gdocs_pat.match(path)

    if host == 'docs.google.com' and path_match:
        auth_path = '/spreadsheets/d/{}/export'.format(path_match.group('id'))
        return 'https://{host}{auth_path}?format=csv'.format(**locals())

    return data_href

def is_allowed_email(file, email):
    ''' Return true if given email address is allowed in given CSV file.

        First argument is a file-like object.
    '''
    domain_index, address_index = None, None
    domain_pat = re.compile(r'^(.*@)?(?P<domain>.+)$')
    email_domain = domain_pat.match(email).group('domain')
    rows = csv.reader(file)

    #
    # Look for a header row.
    #
    for row in rows:
        row = [val.lower() for val in row]
        starts_right = row[:2] == ['email domain', 'organization']
        ends_right = row[-3:] == ['email address', 'organization', 'name']
        if starts_right or ends_right:
            domain_index = 0 if starts_right else None
            address_index = -3 if ends_right else None
            break

    #
    # Look for possible matching data row.
    #
    for row in rows:
        if domain_index is not None:
            if domain_pat.match(row[domain_index]):
                domain = domain_pat.match(row[domain_index]).group('domain')
                if email_domain == domain:
                    return True

        if address_index is not None:
            if email == row[address_index]:
                return True

    return False

def common_template_args(app_config, session):
    ''' Return dictionary of template arguments common to most pages.
    '''
    return {
        'email': session.get('email', None),
        'live_site_url': app_config['LIVE_SITE_URL']
    }

def log_application_errors(route_function):
    ''' Error-logging decorator for route functions.
    
        Don't do much, but get an error out to the logger.
    '''
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        try:
            return route_function(*args, **kwargs)
        except Exception as e:
            Logger.error(e, exc_info=True)
            raise

    return decorated_function

def login_required(route_function):
    ''' Login decorator for route functions.

        Adapts http://flask.pocoo.org/docs/patterns/viewdecorators/
    '''
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        email = session.get('email', None)

        if not email:
            redirect_url = '/not-allowed'
            Logger.info("No email; redirecting to %s", redirect_url)
            return redirect(redirect_url)

        auth_data_href = current_app.config['AUTH_DATA_HREF']
        if not is_allowed_email(get_auth_data_file(auth_data_href), email):
            redirect_url = '/not-allowed'
            Logger.info("Email not allowed; redirecting to %s", redirect_url)
            return redirect(redirect_url)

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

def browserid_hostname_required(route_function):
    ''' Decorator for routes that enforces the hostname set in the BROWSERID_URL config variable
    '''
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        browserid_netloc = urlparse(current_app.config['BROWSERID_URL']).netloc
        request_parsed = urlparse(request.url)
        if request_parsed.netloc != browserid_netloc:
            Logger.info("Redirecting because request_parsed.netloc != browserid_netloc: %s != %s",request_parsed.netloc,browserid_netloc)
            redirect_url = urlunparse((request_parsed.scheme, browserid_netloc, request_parsed.path, request_parsed.params, request_parsed.query, request_parsed.fragment))
            Logger.info("Redirecting to %s", redirect_url)
            return redirect(redirect_url)

        response = route_function(*args, **kwargs)
        return response

    return decorated_function

def synch_required(route_function):
    ''' Decorator for routes needing a repository synched to upstream.

        Syncs with upstream origin before and after. Use below @login_required.
    '''
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        Logger.debug('<' * 40 + '-' * 40)

        repo = Repo(current_app.config['REPO_PATH'])

        if _remote_exists(repo, 'origin'):
            Logger.debug('  fetching origin {}'.format(repo))
            repo.git.fetch('origin', with_exceptions=True)

        Logger.debug('- ' * 40)

        response = route_function(*args, **kwargs)

        # Push to origin only if the request method indicates a change.
        if request.method in ('PUT', 'POST', 'DELETE'):
            Logger.debug('- ' * 40)

            if _remote_exists(repo, 'origin'):
                Logger.debug('  pushing origin {}'.format(repo))
                repo.git.push('origin', all=True, with_exceptions=True)

        Logger.debug('-' * 40 + '>' * 40)

        return response

    return decorated_function

def synched_checkout_required(route_function):
    ''' Decorator for routes needing a repository checked out to a branch.

        Syncs with upstream origin before and after. Use below @login_required.
    '''
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        Logger.debug('<' * 40 + '-' * 40)

        repo = Repo(current_app.config['REPO_PATH'])

        if _remote_exists(repo, 'origin'):
            Logger.debug('  fetching origin {}'.format(repo))
            repo.git.fetch('origin', with_exceptions=True)

        checkout = get_repo(current_app)
        branch_name = branch_var2name(kwargs['branch'])
        master_name = current_app.config['default_branch']
        branch = get_existing_branch(checkout, master_name, branch_name)

        if not branch:
            # redirect and flash an error
            Logger.debug('  branch {} does not exist, redirecting'.format(kwargs['branch']))
            flash(u'There is no {} branch!'.format(kwargs['branch']), u'warning')
            return redirect('/')

        branch.checkout()

        Logger.debug('  checked out to {}'.format(branch))
        Logger.debug('- ' * 40)

        response = route_function(*args, **kwargs)

        # Push to origin only if the request method indicates a change.
        if request.method in ('PUT', 'POST', 'DELETE'):
            Logger.debug('- ' * 40)

            if _remote_exists(repo, 'origin'):
                Logger.debug('  pushing origin {}'.format(repo))
                repo.git.push('origin', all=True, with_exceptions=True)

        Logger.debug('-' * 40 + '>' * 40)

        return response

    return decorated_function

def get_relative_date(repo, file_path):
    ''' Return the relative modified date for the passed path in the passed repo
    '''
    return repo.git.log('-1', '--format=%ad', '--date=relative', '--', file_path)

def sorted_paths(repo, branch_name, path=None, showallfiles=False):
    full_path = join(repo.working_dir, path or '.').rstrip('/')
    all_sorted_files_dirs = sorted(listdir(full_path))

    file_names = [filename for filename in all_sorted_files_dirs if not FILE_FILTERS_COMPILED.search(filename)]
    if showallfiles:
        file_names = all_sorted_files_dirs

    view_paths = [join('/tree/%s/view' % branch_name2path(branch_name), join(path or '', fn))
                  for fn in file_names]

    full_paths = [join(full_path, name) for name in file_names]
    path_pairs = zip(full_paths, view_paths)

    # filename, path, type, editable, modified date
    list_paths = [(basename(edit_path), view_path, path_display_type(edit_path), is_display_editable(edit_path), get_relative_date(repo, edit_path))
                  for (edit_path, view_path) in path_pairs if realpath(edit_path) != repo.git_dir]

    return list_paths

def directory_paths(branch_name, path=None):
    ''' Get a list of tuples (directory name, edit path) for the passed path
        example: passing 'hello/world' will return something like:
            [
                ('hello', '/tree/8bf27f6/edit/hello'), ('world', '/tree/8bf27f6/edit/hello/world')
            ]
    '''
    root_dir_with_path = [('root', '/tree/{}/edit'.format(branch_name2path(branch_name)))]
    if path is None:
        return root_dir_with_path
    directory_list = [dir_name for dir_name in path.split('/')
                      if dir_name and not dir_name.startswith('.')]

    dirs_with_paths = [(dir_name, get_directory_path(branch_name, path, dir_name))
                       for dir_name in directory_list]
    return root_dir_with_path + dirs_with_paths

def directory_columns(clone, branch_name, repo_path=None):
    ''' Get a list of lists of dicts for the passed path, with file listings for each level.
        example: passing 'hello/world' will return something like:
            [
                [
                    {'name': 'hello', 'edit_path': '/tree/8bf27f6/edit/hello', 'display_type': 'category', 'selected': True},
                    {'name': 'goodbye', 'edit_path': '/tree/8bf27f6/edit/goodbye', 'display_type': 'category', 'selected': False}
                ],
                [
                    {'name': 'world', 'edit_path': '/tree/8bf27f6/edit/hello/world', 'display_type': 'category', 'selected': True},
                    {'name': 'moon', 'edit_path': '/tree/8bf27f6/edit/hello/moon', 'display_type': 'category', 'selected': False}
                ]
            ]
    '''
    repo_path = repo_path or u''

    # Build a full directory path.
    head, dirs = split(repo_path)[0], []

    while head:
        head, dir = split(head)
        dirs.insert(0, dir)

    if '..' in dirs:
        raise Exception('Invalid path component.')

    # make sure we get the root dir
    dirs.insert(0, u'')

    # Create the listings
    edit_path_root = u'/tree/{}/edit'.format(branch_name)
    dir_listings = []
    for i in range(len(dirs) - 1):
        current_dir = dirs[i + 1]
        current_path = sep.join(dirs[1:i + 1])
        current_edit_path = join(edit_path_root, current_path)
        files = sorted_paths(clone, branch_name, current_path)
        listing = [{'name': item[0], 'edit_path': join(current_edit_path, item[0]), 'display_type': item[2], 'selected': (current_dir == item[0])} for item in files]
        dir_listings.append(listing)

    return dir_listings

def get_directory_path(branch, path, dir_name):
    dir_index = path.find(dir_name + '/')
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
