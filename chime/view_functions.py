from __future__ import absolute_import
from logging import getLogger
Logger = getLogger('chime.view_functions')

from os.path import join, isdir, realpath, basename, exists, sep, split, splitext
from datetime import datetime
from os import listdir, environ, walk
from urllib import quote, unquote
from urlparse import urljoin, urlparse, urlunparse
from mimetypes import guess_type
from functools import wraps
from io import BytesIO
from slugify import slugify
import csv
import re
import json

from git import Repo
from dateutil import parser, tz
from dateutil.relativedelta import relativedelta
from flask import request, session, current_app, redirect, flash, render_template
from requests import get

from . import publish, NEEDS_PUSH_FILE
from .edit_functions import create_new_page, delete_file, update_page
from .jekyll_functions import load_jekyll_doc, load_languages
from .google_api_functions import read_ga_config, fetch_google_analytics_for_page, WriteLocked
from .repo_functions import (
    get_existing_branch, ignore_task_metadata_on_merge,
    get_message_classification, ChimeRepo, ACTIVITY_CREATED_MESSAGE,
    get_task_metadata_for_branch, complete_branch, abandon_branch,
    clobber_default_branch, MergeConflict, get_review_state_and_authorized,
    save_working_file, update_review_state, provide_feedback,
    move_existing_file, TASK_METADATA_FILENAME, REVIEW_STATE_EDITED,
    REVIEW_STATE_FEEDBACK, REVIEW_STATE_ENDORSED, REVIEW_STATE_PUBLISHED
    )

from .href import needs_redirect, get_redirect

# when creating a content file, what extension should it have?
CONTENT_FILE_EXTENSION = u'markdown'

# the names of layouts, used in jekyll front matter and also in interface text
CATEGORY_LAYOUT = 'category'
ARTICLE_LAYOUT = 'article'
FOLDER_FILE_TYPE = 'folder'
FILE_FILE_TYPE = 'file'
IMAGE_FILE_TYPE = 'image'
LAYOUT_PLURAL_LOOKUP = {
    CATEGORY_LAYOUT: 'categories',
    ARTICLE_LAYOUT: 'articles',
    FOLDER_FILE_TYPE: 'folders',
    FILE_FILE_TYPE: 'files',
    IMAGE_FILE_TYPE: 'images'
}

# files that match these regex patterns will not be shown in the file explorer
FILE_FILTERS = [
    r'^\.',
    r'^_',
    r'\.lock$',
    r'Gemfile',
    r'LICENSE',
    r'index\.{}'.format(CONTENT_FILE_EXTENSION),
    # below filters were added by norris to focus bootcamp UI on articles
    r'^css',
    r'\.xml',
    r'README\.markdown',
    r'^js',
    r'^media',
    r'^styleguide',
    r'^about\.markdown',
]
FILE_FILTERS_COMPILED = re.compile('(' + '|'.join(FILE_FILTERS) + ')')

def dos2unix(string):
    ''' Returns a copy of the strings with line-endings corrected.
    '''
    return string.replace('\r\n', '\n').replace('\r', '\n') if string else string

def get_repo(flask_app=None, repo_path=None, work_path=None, email=None):
    ''' Gets repository for the current user, cloned from the origin.

        Uses the first-ever commit in the origin repository to name
        the cloned directory, to reduce history conflicts when tweaking
        the repository during development.
    '''
    # If a flask_app is passed use it, otherwise use the passed params.
    if flask_app:
        repo_path = flask_app.config['REPO_PATH']
        work_path = flask_app.config['WORK_PATH']

    # if no email was passed, get it from the session
    if not email:
        email = session.get('email', 'nobody')

    source_repo = ChimeRepo(repo_path)
    first_commit = list(source_repo.iter_commits())[-1].hexsha
    dir_name = 'repo-{}-{}'.format(first_commit[:8], slugify(email))
    user_dir = realpath(join(work_path, quote(dir_name)))

    if isdir(user_dir):
        user_repo = ChimeRepo(user_dir)
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
        return FOLDER_FILE_TYPE

    if str(guess_type(file_path)[0]).startswith('image/'):
        return IMAGE_FILE_TYPE

    return FILE_FILE_TYPE

def path_display_type(file_path):
    ''' Returns a type matching how the file at the passed path should be displayed
    '''
    if is_article_dir(file_path):
        return ARTICLE_LAYOUT

    if is_category_dir(file_path):
        return CATEGORY_LAYOUT

    return path_type(file_path)

def index_path_display_type_and_title(file_path):
    ''' Works like path_display_type except that when the path is to an index file,
        it checks the containing directory. Also returns an article or category title if
        appropriate.
    '''
    index_filename = u'index.{}'.format(CONTENT_FILE_EXTENSION)
    path_split = split(file_path)
    if path_split[1] == index_filename:
        folder_type = path_display_type(path_split[0])
        # if the enclosing folder is just a folder (and not an article or category)
        # return the type of the index file instead
        if folder_type == FOLDER_FILE_TYPE:
            return FILE_FILE_TYPE, u''

        # the enclosing folder is an article or category
        return folder_type, get_value_from_front_matter('title', file_path)

    # the path was to something other than an index file
    path_type = path_display_type(file_path)
    if path_type in (ARTICLE_LAYOUT, CATEGORY_LAYOUT):
        return path_type, get_value_from_front_matter('title', join(file_path, index_filename))

    return path_type, u''

def file_type_plural(file_type):
    ''' Get the plural of the passed file type
    '''
    if file_type in LAYOUT_PLURAL_LOOKUP:
        return LAYOUT_PLURAL_LOOKUP[file_type]

    return file_type

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
    ''' Returns True if the file at the passed path is a directory containing an index file with a category jekyll layout.
    '''
    return is_dir_with_layout(file_path, CATEGORY_LAYOUT, False)

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

def describe_directory_contents(clone, file_path):
    ''' Return a description of the contents of the passed path
    '''
    full_path = join(clone.working_dir, file_path)
    described_files = []
    for (dir_path, dir_names, file_names) in walk(full_path):
        for check_name in file_names:
            check_path = join(dir_path, check_name)
            display_type, title = index_path_display_type_and_title(check_path)
            short_path = re.sub('{}/'.format(clone.working_dir), '', check_path)
            is_root = file_path == short_path or file_path == split(short_path)[0]
            described_files.append({"display_type": display_type, "title": title, "file_path": short_path, "is_root": is_root})

    return described_files

def get_front_matter(file_path):
    ''' Get the front matter for the file at the passed path if it exists.
    '''
    if isdir(file_path) or not exists(file_path):
        return None

    with open(file_path) as file:
        front_matter, _ = load_jekyll_doc(file)

    return front_matter

def get_value_from_front_matter(key, file_path):
    ''' Get the value for the passed key in the front matter
    '''
    try:
        return get_front_matter(file_path)[key]
    except:
        return None

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

        if not only:
            # it doesn't matter how many files are in the directory
            return True

        visible_file_count = len([name for name in listdir(file_path) if not FILE_FILTERS_COMPILED.search(name)])
        if visible_file_count == 0:
            # there's only an index file in the directory
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
            Logger.error(e, exc_info=True, extra={'request': request})
            raise

    return decorated_function

def login_required(route_function):
    ''' Login decorator for route functions.

        Adapts http://flask.pocoo.org/docs/patterns/viewdecorators/
    '''
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        email = session.get('email', '').decode('utf-8')

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
        environ['GIT_AUTHOR_EMAIL'] = email.encode('utf-8')
        environ['GIT_COMMITTER_NAME'] = ' '
        environ['GIT_COMMITTER_EMAIL'] = email.encode('utf-8')

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
            Logger.info("Redirecting because request_parsed.netloc != browserid_netloc: %s != %s", request_parsed.netloc, browserid_netloc)
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

            needs_push_file = join(current_app.config['RUNNING_STATE_DIR'], NEEDS_PUSH_FILE)
            
            with WriteLocked(needs_push_file) as file:
                file.truncate()
                file.write('Yes')

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

        checkout = get_repo(flask_app=current_app)
        # get the branch name from request.form if it's not in kwargs
        branch_name_raw = kwargs['branch_name'] if 'branch_name' in kwargs else None
        if not branch_name_raw:
            branch_name_raw = request.form.get('branch', None)

        branch_name = branch_var2name(branch_name_raw)
        master_name = current_app.config['default_branch']
        branch = get_existing_branch(checkout, master_name, branch_name)

        if not branch:
            # redirect and flash an error
            Logger.debug('  branch {} does not exist, redirecting'.format(branch_name_raw))
            flash(u'There is no {} branch!'.format(branch_name_raw), u'warning')
            return redirect('/')

        branch.checkout()

        Logger.debug('  checked out to {}'.format(branch))
        Logger.debug('- ' * 40)

        response = route_function(*args, **kwargs)

        # Push to origin only if the request method indicates a change.
        if request.method in ('PUT', 'POST', 'DELETE'):
            Logger.debug('- ' * 40)

            needs_push_file = join(current_app.config['RUNNING_STATE_DIR'], NEEDS_PUSH_FILE)
            
            with WriteLocked(needs_push_file) as file:
                file.truncate()
                file.write('Yes')

        Logger.debug('-' * 40 + '>' * 40)

        return response

    return decorated_function

def get_relative_date(repo, file_path):
    ''' Return the relative modified date for the passed path in the passed repo
    '''
    return repo.git.log('-1', '--format=%ad', '--date=relative', '--', file_path)

def make_delete_display_commit_message(repo, request_path):
    ''' Build a commit message about file deletion for display in the activity history
    '''
    # construct the commit message
    targeted_files = describe_directory_contents(repo, request_path)
    message_details = {}
    root_file = {}
    for file_details in targeted_files:
        # don't include the root file in the count
        if file_details['is_root']:
            root_file = file_details
        else:
            display_type = file_details['display_type']
            if display_type not in message_details:
                message_details[display_type] = {}
                message_details[display_type]['noun'] = display_type
                message_details[display_type]['files'] = []
            else:
                message_details[display_type]['noun'] = file_type_plural(display_type)
            message_details[display_type]['files'].append(file_details)
    commit_message = u'The "{}" {}'.format(root_file['title'], root_file['display_type'])
    if len(targeted_files) > 1:
        message_counts = []
        for detail_key in message_details:
            detail = message_details[detail_key]
            message_counts.append(u'{} {}'.format(len(detail['files']), detail['noun']))
        commit_message = commit_message + u' (containing {})'.format(u', '.join(message_counts[:-2] + [u' and '.join(message_counts[-2:])]))

    commit_message = commit_message + u' was deleted'

    # alter targeted_files and dump it to the message body as json
    altered_files = []
    for file_description in targeted_files:
        del file_description['is_root']
        file_description['action'] = u'delete'
        altered_files.append(file_description)
    commit_message = commit_message + u'\n\n' + json.dumps(altered_files, ensure_ascii=False)

    return commit_message

def make_activity_history(repo):
    ''' Make an easily-parsable history of an activity since it was created.
    '''
    # see <http://git-scm.com/docs/git-log> for placeholders
    log_format = '%x00Name: %an\tEmail: %ae\tDate: %ad\tSubject: %s\tBody: %b%x00'
    log = repo.git.log('--format={}'.format(log_format), '--date=relative')

    history = []
    pattern = re.compile(r'\x00Name: (.*?)\tEmail: (.*?)\tDate: (.*?)\tSubject: (.*?)\tBody: (.*?)\x00', re.DOTALL)
    for log_details in pattern.findall(log):
        name, email, date, subject, body = tuple([item.decode('utf-8') for item in log_details])
        commit_category, commit_type, commit_action = get_message_classification(subject, body)
        log_item = dict(author_name=name, author_email=email, commit_date=date, commit_subject=subject,
                        commit_body=body, commit_category=commit_category, commit_type=commit_type,
                        commit_action=commit_action)
        history.append(log_item)
        # don't get any history beyond the creation of the task metadata file, which is the beginning of the activity
        if re.search(r'{}$'.format(ACTIVITY_CREATED_MESSAGE), subject):
            break

    return history

def sorted_paths(repo, branch_name, path=None, showallfiles=False):
    ''' Returns a list of files and their attributes in the passed directory.
    '''
    full_path = join(repo.working_dir, path or '.').rstrip('/')
    all_sorted_files_dirs = sorted(listdir(full_path))

    file_names = [filename for filename in all_sorted_files_dirs if not FILE_FILTERS_COMPILED.search(filename)]
    if showallfiles:
        file_names = all_sorted_files_dirs

    view_paths = [join('/tree/%s/view' % branch_name2path(branch_name), join(path or '', fn))
                  for fn in file_names]

    full_paths = [join(full_path, name) for name in file_names]
    path_pairs = zip(full_paths, view_paths)

    # name, title, view_path, display_type, is_editable, modified_date
    path_details = []
    for (edit_path, view_path) in path_pairs:
        if realpath(edit_path) != repo.git_dir:
            info = {}
            info['name'] = basename(edit_path)
            info['display_type'] = path_display_type(edit_path)
            file_title = get_value_from_front_matter('title', join(edit_path, u'index.{}'.format(CONTENT_FILE_EXTENSION)))
            if not file_title:
                if info['display_type'] in (FOLDER_FILE_TYPE, IMAGE_FILE_TYPE, FILE_FILE_TYPE):
                    file_title = info['name']
                else:
                    file_title = re.sub('-', ' ', info['name']).title()
            info['title'] = file_title
            info['view_path'] = view_path
            info['is_editable'] = is_display_editable(edit_path)
            info['modified_date'] = get_relative_date(repo, edit_path)
            path_details.append(info)

    return path_details

def make_breadcrumb_paths(branch_name, path=None):
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

    dirs_with_paths = [(dir_name, make_edit_path(branch_name, path, dir_name))
                       for dir_name in directory_list]
    return root_dir_with_path + dirs_with_paths

def make_edit_path(branch, path, dir_name):
    ''' Return the path to edit the object at the passed location
    '''
    dir_index = path.find(dir_name + '/')
    base_path = path[:dir_index] + dir_name + '/'
    return join('/tree/{}/edit'.format(branch_name2path(branch)), base_path)

def make_directory_columns(clone, branch_name, repo_path=None, showallfiles=False):
    ''' Get a list of lists of dicts for the passed path, with file listings for each level.
        example: passing 'hello/world/wide' will return something like:
            [
                {'base_path': '',
                 'files':
                    [
                        {'name': 'hello', 'title': 'Hello', 'base_path': '', 'file_path': 'hello', 'edit_path': '/tree/8bf27f6/edit/hello', 'view_path': '/tree/dfffcd8/view/hello', 'display_type': 'category', 'is_editable': False, 'modified_date': '75 minutes ago', 'selected': True},
                        {'name': 'goodbye', 'title': 'Goodbye', 'base_path': '', 'file_path': 'goodbye', 'edit_path': '/tree/8bf27f6/edit/goodbye', 'view_path': '/tree/dfffcd8/view/goodbye', 'display_type': 'category', 'is_editable': False, 'modified_date': '2 days ago', 'selected': False}
                    ]
                },
                {'base_path': 'hello',
                 'files':
                    [
                        {'name': 'world', 'title': 'World', 'base_path': 'hello', 'file_path': 'hello/world', 'edit_path': '/tree/8bf27f6/edit/hello/world', 'view_path': '/tree/dfffcd8/view/hello/world', 'display_type': 'category', 'is_editable': False, 'modified_date': '75 minutes ago', 'selected': True},
                        {'name': 'moon', 'title': 'Moon', 'base_path': 'hello', 'file_path': 'hello/moon', 'edit_path': '/tree/8bf27f6/edit/hello/moon', 'view_path': '/tree/dfffcd8/view/hello/moon', 'display_type': 'category', 'is_editable': False, 'modified_date': '4 days ago', 'selected': False}
                    ]
                }
            ]
    '''
    # Build a full directory path.
    repo_path = repo_path or u''
    dirs = clone.dirs_for_path(repo_path)
    # make sure we get the root dir
    dirs.insert(0, u'')

    # Create the listings
    edit_path_root = u'/tree/{}/edit'.format(branch_name)
    modify_path_root = u'/tree/{}/modify'.format(branch_name)
    dir_listings = []
    for i in range(len(dirs)):
        try:
            current_dir = dirs[i + 1]
        except IndexError:
            current_dir = dirs[-1]

        base_path = sep.join(dirs[1:i + 1])
        current_edit_path = join(edit_path_root, base_path)
        current_modify_path = join(modify_path_root, base_path)
        files = sorted_paths(clone, branch_name, base_path, showallfiles)
        # name, title, base_path, file_path, edit_path, view_path, display_type, is_editable, modified_date, selected
        listing = [{'name': item['name'], 'title': item['title'], 'base_path': base_path, 'file_path': join(base_path, item['name']), 'edit_path': join(current_edit_path, item['name']), 'modify_path': join(current_modify_path, item['name']), 'view_path': item['view_path'], 'display_type': item['display_type'], 'is_editable': item['is_editable'], 'modified_date': item['modified_date'], 'selected': (current_dir == item['name'])} for item in files]
        dir_listings.append({'base_path': base_path, 'files': listing})

    return dir_listings

def publish_or_destroy_activity(branch_name, action):
    ''' Publish, abandon, or clobber the activity defined by the passed branch name.
    '''
    repo = get_repo(flask_app=current_app)
    master_name = current_app.config['default_branch']

    # contains 'author_email', 'task_description', 'task_beneficiary'
    activity = get_task_metadata_for_branch(repo, branch_name)
    activity['author_email'] = activity['author_email'] if 'author_email' in activity else u''
    activity['task_description'] = activity['task_description'] if 'task_description' in activity else u''
    activity['task_beneficiary'] = activity['task_beneficiary'] if 'task_beneficiary' in activity else u''

    try:
        args = repo, master_name, branch_name

        if action == 'merge':
            complete_branch(*args)
        elif action == 'abandon':
            abandon_branch(*args)
        elif action == 'clobber':
            clobber_default_branch(*args)
        else:
            raise Exception(u'Tried to {} an activity, and I don\'t know how to do that.'.format(action))

        if current_app.config['PUBLISH_SERVICE_URL']:
            publish.announce_commit(current_app.config['BROWSERID_URL'], repo, repo.commit().hexsha)

        else:
            publish.release_commit(current_app.config['RUNNING_STATE_DIR'], repo, repo.commit().hexsha)

    except MergeConflict as conflict:
        raise conflict

    else:
        activity_blurb = u'the "{task_description}" activity for {task_beneficiary}'.format(task_description=activity['task_description'], task_beneficiary=activity['task_beneficiary'])
        if action == 'merge':
            flash(u'You published the {activity_blurb}!'.format(activity_blurb=activity_blurb), u'notice')
        elif action == 'abandon':
            flash(u'You deleted the {activity_blurb}!'.format(activity_blurb=activity_blurb), u'notice')
        elif action == 'clobber':
            flash(u'You clobbered the {activity_blurb}!'.format(activity_blurb=activity_blurb), u'notice')

        return redirect('/', code=303)

def make_kwargs_for_activity_files_page(repo, branch_name, path):
    ''' Assemble the kwargs for a page that shows an activity's files.
    '''
    # :NOTE: temporarily turning off filtering if 'showallfiles=true' is in the request
    showallfiles = request.args.get('showallfiles') == u'true'

    # contains 'author_email', 'task_description', 'task_beneficiary'
    activity = get_task_metadata_for_branch(repo, branch_name)
    activity['author_email'] = activity['author_email'] if 'author_email' in activity else u''
    activity['task_description'] = activity['task_description'] if 'task_description' in activity else u''
    activity['task_beneficiary'] = activity['task_beneficiary'] if 'task_beneficiary' in activity else u''

    # get created and modified dates via git logs (relative dates for now)
    date_created = repo.git.log('--format=%ad', '--date=relative', '--', TASK_METADATA_FILENAME).split('\n')[-1]
    date_updated = repo.git.log('--format=%ad', '--date=relative').split('\n')[0]

    # get the current review state and authorized status
    review_state, review_authorized = get_review_state_and_authorized(
        repo=repo, default_branch_name=current_app.config['default_branch'],
        working_branch_name=branch_name, actor_email=session.get('email', None)
    )

    activity.update(date_created=date_created, date_updated=date_updated,
                    edit_path=u'/tree/{}/edit/'.format(branch_name2path(branch_name)),
                    overview_path=u'/tree/{}/'.format(branch_name2path(branch_name)),
                    review_state=review_state, review_authorized=review_authorized)

    kwargs = common_template_args(current_app.config, session)
    kwargs.update(branch=branch_name, safe_branch=branch_name2path(branch_name),
                  breadcrumb_paths=make_breadcrumb_paths(branch_name, path),
                  dir_columns=make_directory_columns(repo, branch_name, path, showallfiles),
                  activity=activity)

    return kwargs

def render_list_dir(repo, branch_name, path):
    ''' Render a page showing an activity's files
    '''
    kwargs = make_kwargs_for_activity_files_page(repo, branch_name, path)
    return render_template('articles-list.html', **kwargs)

def render_modify_dir(repo, branch_name, path):
    ''' Render a page showing an activity's files with an edit form for the selected category directory.
    '''
    path = path or '.'
    full_path = join(repo.working_dir, path).rstrip('/')
    full_index_path = join(full_path, u'index.{}'.format(CONTENT_FILE_EXTENSION))
    # init a category object with the contents of the category's front matter
    category = get_front_matter(full_index_path)

    if 'layout' not in category:
        raise Exception(u'No layout found for {}.'.format(full_path))
    if category['layout'] != CATEGORY_LAYOUT:
        raise Exception(u'Can\'t modify {}s, only categories.'.format(category['layout']))

    languages = load_languages(repo.working_dir)

    kwargs = make_kwargs_for_activity_files_page(repo, branch_name, path)
    # cancel redirects to the edit page for that category
    category['edit_path'] = join(kwargs['activity']['edit_path'], path)
    url_slug = re.sub(ur'index.{}$'.format(CONTENT_FILE_EXTENSION), u'', path)

    kwargs.update(category=category, languages=languages, hexsha=repo.commit().hexsha, url_slug=url_slug)

    return render_template('directory-modify.html', **kwargs)

def render_edit_view(repo, branch_name, path, file):
    ''' Render the page that lets you edit a file
    '''
    front, body = load_jekyll_doc(file)
    languages = load_languages(repo.working_dir)
    url_slug = path
    # strip the index file from the slug if appropriate
    url_slug = re.sub(ur'index.{}$'.format(CONTENT_FILE_EXTENSION), u'', url_slug)
    view_path = join('/tree/{}/view'.format(branch_name2path(branch_name)), path)
    history_path = join('/tree/{}/history'.format(branch_name2path(branch_name)), path)
    save_path = join('/tree/{}/save'.format(branch_name2path(branch_name)), path)
    folder_root_slug = u'/'.join([item for item in url_slug.split('/') if item][:-1]) + u'/'
    app_authorized = False
    ga_config = read_ga_config(current_app.config['RUNNING_STATE_DIR'])
    analytics_dict = {}
    if ga_config.get('access_token'):
        app_authorized = True
        analytics_dict = fetch_google_analytics_for_page(current_app.config, path, ga_config.get('access_token'))
    commit = repo.commit()

    # contains 'author_email', 'task_description', 'task_beneficiary'
    activity = get_task_metadata_for_branch(repo, branch_name)
    activity['author_email'] = activity['author_email'] if 'author_email' in activity else u''
    activity['task_description'] = activity['task_description'] if 'task_description' in activity else u''
    activity['task_beneficiary'] = activity['task_beneficiary'] if 'task_beneficiary' in activity else u''

    # get the current review state and authorized status
    review_state, review_authorized = get_review_state_and_authorized(
        repo=repo, default_branch_name=current_app.config['default_branch'],
        working_branch_name=branch_name, actor_email=session.get('email', None)
    )

    activity.update(edit_path=u'/tree/{}/edit/'.format(branch_name2path(branch_name)),
                    overview_path=u'/tree/{}/'.format(branch_name2path(branch_name)),
                    review_state=review_state, review_authorized=review_authorized)

    kwargs = common_template_args(current_app.config, session)
    kwargs.update(branch=branch_name, safe_branch=branch_name2path(branch_name),
                  body=body, hexsha=commit.hexsha, url_slug=url_slug,
                  front=front, view_path=view_path, edit_path=path,
                  history_path=history_path, save_path=save_path, languages=languages,
                  breadcrumb_paths=make_breadcrumb_paths(branch_name, folder_root_slug),
                  app_authorized=app_authorized, activity=activity)
    kwargs.update(analytics_dict)
    return render_template('article-edit.html', **kwargs)

def add_article_or_category(repo, dir_path, request_path, create_what):
    ''' Add an article or category
    '''
    if create_what not in ('article', 'category'):
        raise ValueError(u'Can\'t create {} in {}.'.format(create_what, join(dir_path, request_path)))

    request_path = request_path.rstrip('/')

    # create and commit intermediate categories recursively
    if u'/' in request_path:
        cat_paths = repo.dirs_for_path(request_path)
        flash_messages = []
        for i in range(len(cat_paths)):
            cat_path = cat_paths[i]
            dir_cat_path = join(dir_path, sep.join(cat_paths[:i]))
            commit_message, file_path, _, do_save = add_article_or_category(repo, dir_cat_path, cat_path, CATEGORY_LAYOUT)
            if do_save:
                Logger.debug('save')
                save_working_file(repo, file_path, commit_message, repo.commit().hexsha, current_app.config['default_branch'])
            else:
                flash_messages.append(commit_message)

        if len(flash_messages):
            flash(', '.join(flash_messages), u'notice')

    # create the article or category
    display_name = splitext(request_path)[0]
    name = u'{}/index.{}'.format(display_name, CONTENT_FILE_EXTENSION)
    file_path = repo.canonicalize_path(dir_path, name)

    if create_what == 'article':
        redirect_path = file_path
        create_front = dict(title=u'', description=u'', order=0, layout=ARTICLE_LAYOUT)
    elif create_what == 'category':
        redirect_path = strip_index_file(file_path)
        create_front = dict(title=u'', description=u'', order=0, layout=CATEGORY_LAYOUT)

    if repo.exists(file_path):
        return '{} "{}" already exists'.format(create_what.title(), request_path), file_path, redirect_path, False

    file_path = create_new_page(clone=repo, dir_path=dir_path, request_path=name, front=create_front, body=u'')
    action_descriptions = [{'action': u'create', 'title': display_name, 'display_type': create_what, 'file_path': file_path}]
    commit_message = u'The "{}" {} was created\n\n{}'.format(display_name, create_what, json.dumps(action_descriptions, ensure_ascii=False))

    return commit_message, file_path, redirect_path, True

def strip_index_file(file_path):
    return re.sub(r'index.{}$'.format(CONTENT_FILE_EXTENSION), '', file_path)

def delete_page(repo, browse_path, target_path):
    ''' Delete a category or article.

        browse_path is where you are when issuing the deletion request; it's
                    used to figure out where to redirect if you're deleting
                    the directory you're in.

        target_path is the location of the object that needs to be deleted.
    '''
    # construct the commit message
    commit_message = make_delete_display_commit_message(repo, target_path)

    # delete the file(s)
    deleted_file_paths, do_save = delete_file(repo, target_path)

    # if we're in the path that's been deleted, redirect to the first still-existing directory in the path
    path_dirs = browse_path.split('/')
    req_dirs = target_path.split('/')
    if len(path_dirs) >= len(req_dirs) and path_dirs[len(req_dirs) - 1] == req_dirs[-1]:
        redirect_path = u'/'.join(req_dirs[:-1])
    else:
        redirect_path = browse_path

    if redirect_path and not redirect_path.endswith('/'):
        redirect_path = redirect_path + '/'

    return redirect_path, do_save, commit_message

def update_activity_review_status(branch_name, comment_text, action_list):
    ''' Comment and/or update the review state.
    '''
    repo = get_repo(flask_app=current_app)
    # which submit button was pressed?
    action = u''
    possible_actions = ['comment', 'request_feedback', 'endorse_edits', 'merge', 'abandon', 'clobber']
    for check_action in possible_actions:
        if check_action in action_list:
            action = check_action
            break

    # get the current review state and authorized status
    review_state, review_authorized = get_review_state_and_authorized(
        repo=repo, default_branch_name=current_app.config['default_branch'],
        working_branch_name=branch_name, actor_email=session.get('email', None)
    )
    action_authorized = (action == 'comment' and comment_text)

    # handle a review action
    if action != 'comment':
        if action == 'request_feedback':
            if review_state == REVIEW_STATE_EDITED and review_authorized:
                update_review_state(repo, REVIEW_STATE_FEEDBACK)
                action_authorized = True
        elif action == 'endorse_edits':
            if review_state == REVIEW_STATE_FEEDBACK and review_authorized:
                update_review_state(repo, REVIEW_STATE_ENDORSED)
                action_authorized = True
        elif action == 'merge':
            if review_state == REVIEW_STATE_ENDORSED and review_authorized:
                update_review_state(repo, REVIEW_STATE_PUBLISHED)
                action_authorized = True
        elif action == 'clobber' or action == 'abandon':
            action_authorized = True

    if not action:
        raise Exception(u'Tried to update an activity\'s review status but wasn\'t given a valid action.')

    # comment if comment text was sent and the action is authorized
    if comment_text and action_authorized:
        provide_feedback(repo, comment_text)

    # flash a message if the action wasn't authorized
    if action == 'comment' and not comment_text:
        flash(u'You can\'t leave an empty comment!', u'error')
    elif not action_authorized:
        action_lookup = {
            'comment': u'leave a comment',
            'request_feedback': u'request feedback',
            'endorse_edits': u'endorse the edits',
            'merge': u'publish the edits'
        }
        flash(u'Something changed behind the scenes and we couldn\'t {}! Please try again.'.format(action_lookup[action]), u'error')

    return action, action_authorized

def save_page(repo, default_branch_name, working_branch_name, file_path, new_values):
    ''' Save the page with the passed values
    '''
    working_branch_name = branch_var2name(working_branch_name)

    existing_branch = get_existing_branch(repo, default_branch_name, working_branch_name)

    if not existing_branch:
        flash(u'There is no {} branch!'.format(working_branch_name), u'warning')
        return file_path, False

    commit = existing_branch.commit

    if commit.hexsha != new_values.get('hexsha'):
        raise Exception(u'Unable to save page because someone else made edits while you were working.')

    #
    # Write changes.
    #
    existing_branch.checkout()

    # make sure order is an integer; otherwise default to 0
    try:
        order = int(dos2unix(new_values.get('order', '0')))
    except ValueError:
        order = 0

    front = {
        'layout': dos2unix(new_values.get('layout')),
        'order': order,
        'title': dos2unix(new_values.get('en-title', '')),
        'description': dos2unix(new_values.get('en-description', ''))
    }

    for iso in load_languages(repo.working_dir):
        if iso != 'en':
            front['title-' + iso] = dos2unix(new_values.get(iso + '-title', ''))
            front['description-' + iso] = dos2unix(new_values.get(iso + '-description', ''))
            front['body-' + iso] = dos2unix(new_values.get(iso + '-body', ''))

    body = dos2unix(new_values.get('en-body', ''))
    update_page(repo, file_path, front, body)

    #
    # Try to merge from the master to the current branch.
    #
    try:
        display_name = new_values.get('en-title')
        display_type = new_values.get('layout')
        action_descriptions = [{'action': u'edit', 'title': display_name, 'display_type': display_type, 'file_path': file_path}]
        commit_message = u'The "{}" {} was edited\n\n{}'.format(display_name, display_type, json.dumps(action_descriptions, ensure_ascii=False))
        c2 = save_working_file(repo, file_path, commit_message, commit.hexsha, default_branch_name)
        # they may've renamed the page by editing the URL slug
        original_slug = file_path
        if re.search(r'\/index.{}$'.format(CONTENT_FILE_EXTENSION), file_path):
            original_slug = re.sub(ur'index.{}$'.format(CONTENT_FILE_EXTENSION), u'', file_path)

        # do some simple input cleaning
        new_slug = new_values.get('url-slug')
        if new_slug:
            new_slug = re.sub(r'\/+', '/', new_slug)

            if new_slug != original_slug:
                try:
                    move_existing_file(repo, original_slug, new_slug, c2.hexsha, default_branch_name)
                except Exception as e:
                    error_message = e.args[0]
                    error_type = e.args[1] if len(e.args) > 1 else None
                    # let unexpected errors raise normally
                    if error_type:
                        flash(error_message, error_type)
                        return file_path, True
                    else:
                        raise

                file_path = new_slug
                # append the index file if it's an editable directory
                if is_article_dir(join(repo.working_dir, new_slug)):
                    file_path = join(new_slug, u'index.{}'.format(CONTENT_FILE_EXTENSION))

    except MergeConflict as conflict:
        repo.git.reset(commit.hexsha, hard=True)

        Logger.debug('1 {}'.format(conflict.remote_commit))
        Logger.debug('  {}'.format(repr(conflict.remote_commit.tree[file_path].data_stream.read())))
        Logger.debug('2 {}'.format(conflict.local_commit))
        Logger.debug('  {}'.format(repr(conflict.local_commit.tree[file_path].data_stream.read())))
        raise conflict

    return file_path, True

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
