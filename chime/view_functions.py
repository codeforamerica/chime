from __future__ import absolute_import
from logging import getLogger

from .simple_flock import SimpleFlock

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
from collections import Counter
from tempfile import mkdtemp
from subprocess import Popen
from git.cmd import GitCommandError
from glob import glob
import csv
import re
import json
import time
import uuid

from dateutil import parser, tz
from dateutil.relativedelta import relativedelta
from flask import request, session, current_app, redirect, flash, render_template, abort, Response

from requests import get

from .edit_functions import create_new_page, delete_file, update_page
from .jekyll_functions import load_jekyll_doc, load_languages, build_jekyll_site
from .google_api_functions import read_ga_config, fetch_google_analytics_for_page
from .repo_functions import (
    get_existing_branch, get_branch_if_exists_locally, ignore_task_metadata_on_merge,
    get_commit_classification, ChimeRepo, get_task_metadata_for_branch, complete_branch,
    abandon_branch, clobber_default_branch, get_review_state_and_authorized,
    update_review_state, provide_feedback, move_existing_file,
    get_last_edited_email, mark_upstream_push_needed, MergeConflict,
    get_activity_working_state, ACTIVITY_CREATED_MESSAGE, TASK_METADATA_FILENAME,
    make_branch_name, save_local_working_file, sync_with_default_and_upstream_branches
)
from . import constants

from .href import needs_redirect, get_redirect

# Maximum age of an authentication check in seconds.
AUTH_CHECK_LIFESPAN = 300.0

# when creating a content file, what extension should it have?
CONTENT_FILE_EXTENSION = u'markdown'

# Name of default AUTH_DATA_HREF value
AUTH_DATA_HREF_DEFAULT = 'data/authentication.csv'

# the names of layouts, used in jekyll front matter and also in interface text
CATEGORY_LAYOUT = 'category'
ARTICLE_LAYOUT = 'article'
FOLDER_FILE_TYPE = 'folder'
FILE_FILE_TYPE = 'file'
IMAGE_FILE_TYPE = 'image'
# how we describe items based on their layout
LAYOUT_DISPLAY_LOOKUP = {
    CATEGORY_LAYOUT: 'topic',
    ARTICLE_LAYOUT: 'article',
    FOLDER_FILE_TYPE: 'folder',
    FILE_FILE_TYPE: 'file',
    IMAGE_FILE_TYPE: 'image'
}
LAYOUT_PLURAL_LOOKUP = {
    CATEGORY_LAYOUT: 'topics',
    ARTICLE_LAYOUT: 'articles',
    FOLDER_FILE_TYPE: 'folders',
    FILE_FILE_TYPE: 'files',
    IMAGE_FILE_TYPE: 'images'
}

# error messages
MESSAGE_ACTIVITY_DELETED = u'This activity has been deleted or never existed! Please start a new activity to make changes.'
MESSAGE_ACTIVITY_PUBLISHED = u'This activity was published {published_date} by {published_by}! Please start a new activity to make changes.'
MESSAGE_PAGE_EDITED = u'{published_by} edited this file while you were working, {published_date}! Your changes have been lost.'

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

def file_display_name(file_type):
    ''' Get the display name of the passed file type
    '''
    if file_type in LAYOUT_DISPLAY_LOOKUP:
        return LAYOUT_DISPLAY_LOOKUP[file_type]

    return file_type

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
    file_path = file_path.rstrip('/')
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

def get_solo_directory_name(repo, branch_name, path):
    ''' If, in the passed directory, there is a non-article or -category directory
        that's the only visible object in the hierarchy, return its name.
    '''
    directory_contents = sorted_paths(repo=repo, branch_name=branch_name, path=path)
    if len(directory_contents) == 1 and directory_contents[0]['display_type'] == FOLDER_FILE_TYPE:
        return directory_contents[0]['name']

    return None

def get_redirect_path_for_solo_directory(repo, branch_name, path):
    ''' If, in the passed directory, there is a non-article or -category directory
        that's the only visible object in the hierarchy, return a redirect URL inside
        that directory
    '''
    solo_directory_name = get_solo_directory_name(repo, branch_name, path)
    if solo_directory_name:
        path = join(path, solo_directory_name) if path else solo_directory_name
        vars = dict(branch_name=branch_name2path(branch_name), path=path)
        return '/tree/{branch_name}/edit/{path}/'.format(**vars)

    # no redirect necessary
    return None

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
            # If we find the domain "*" we'll know that anyone's allowed in.
            if row[domain_index] == '*':
                return True

            # Allow this email if the domain matches.
            if domain_pat.match(row[domain_index]):
                domain = domain_pat.match(row[domain_index]).group('domain')
                if email_domain == domain:
                    return True

        # Allow this email if the entire string matches.
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
            # not all exceptions have a 'code' attribute
            error_code = getattr(e, 'code', 500)

            # assign an error UUID attribute
            e.uuid = str(uuid.uuid4())[-12:]
            extras = dict(request=request, session=session, id=e.uuid)

            if error_code in range(400, 499):
                Logger.info(e, exc_info=False, extra=extras)
            else:
                Logger.error(e, exc_info=True, extra=extras)

            raise

    return decorated_function

def lock_on_user(route_function):
    ''' Lock decorator for route functions.

        Prevents conflicts with flock()
    '''
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        safe_username = re.sub(r'\W+', '-', session.get('email', 'nobody'))
        lock_path = join(current_app.config['WORK_PATH'], "{}.lock".format(safe_username))
        with SimpleFlock(lock_path):
            return route_function(*args, **kwargs)

    return decorated_function

def login_required(route_function):
    ''' Login decorator for route functions.

        Adapts http://flask.pocoo.org/docs/patterns/viewdecorators/
    '''
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        email = session.get('email', '')

        if not email:
            redirect_url = '/not-allowed'
            Logger.info("No email; redirecting to %s", redirect_url)
            return redirect(redirect_url)

        auth_data_href = current_app.config['AUTH_DATA_HREF']
        last_check = session.get('auth_check', {}).get('last_check', 0.0)
        last_result = session.get('auth_check', {}).get('last_result')

        if last_result is True and (last_check + AUTH_CHECK_LIFESPAN) > time.time():
            # Email still allowed
            pass

        elif not is_allowed_email(get_auth_data_file(auth_data_href), email):
            Logger.debug('Remembering that email was not allowed')
            session['auth_check'] = dict(last_check=time.time(), last_result=False)

            redirect_url = '/not-allowed'
            Logger.info("Email not allowed; redirecting to %s", redirect_url)
            return redirect(redirect_url)
        
        else:
            Logger.debug('Remembering that email was allowed in')
            session['auth_check'] = dict(last_check=time.time(), last_result=True)

        environ['GIT_AUTHOR_NAME'] = ' '
        environ['GIT_AUTHOR_EMAIL'] = email.encode('utf-8')
        environ['GIT_COMMITTER_NAME'] = ' '
        environ['GIT_COMMITTER_EMAIL'] = email.encode('utf-8')

        return route_function(*args, **kwargs)

    return decorated_function

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

def guess_branch_names_in_decorator(kwargs, config, form):
    '''
    '''
    branch_name_raw = kwargs.get('branch_name')
    if not branch_name_raw:
        branch_name_raw = form.get('branch', None)

    branch_name = branch_name_raw and branch_var2name(branch_name_raw)
    master_name = config['default_branch']
    
    return branch_name, master_name

def synch_required(route_function):
    ''' Decorator for routes needing a repository synched to upstream.

        Syncs with upstream origin after. Use below @login_required.
    '''
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        repo = get_repo(flask_app=current_app)
        branch_name, master_name = \
            guess_branch_names_in_decorator(kwargs, current_app.config, request.form)

        # fetch
        repo.git.fetch('origin')

        if branch_name:
            # are we in a remotely published or deleted activity?
            working_state = get_activity_working_state(repo, master_name, branch_name)
            local_branch = get_branch_if_exists_locally(repo, master_name, branch_name)

            if working_state == constants.WORKING_STATE_PUBLISHED:
                tag_ref = repo.tag('refs/tags/{}'.format(branch_name))
                commit = tag_ref.commit
                published_date = repo.git.show('--format=%ad', '--date=relative', commit.hexsha).strip()
                published_by = commit.committer.email
                flash_only(MESSAGE_ACTIVITY_PUBLISHED.format(published_date=published_date, published_by=published_by), u'warning')

                # if the published branch doesn't exist locally, raise a 404
                if not local_branch:
                    abort(404)

        response = route_function(*args, **kwargs)
        
        if request.method in ('PUT', 'POST', 'DELETE'):
            # Attempt to push to origin in all cases.
            if branch_name:
                if working_state == constants.WORKING_STATE_ACTIVE:
                    repo.git.push('origin', branch_name)

                    # Push upstream only if the request method indicates a change.
                    mark_upstream_push_needed(current_app.config['RUNNING_STATE_DIR'])

        return response

    return decorated_function

def synched_checkout_required(route_function):
    ''' Decorator for routes needing a repository checked out to a branch.

        Syncs with upstream origin before and after. Use below @login_required.
    '''
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        repo = get_repo(flask_app=current_app)
        branch_name, master_name = \
            guess_branch_names_in_decorator(kwargs, current_app.config, request.form)

        # fetch
        repo.git.fetch('origin')

        # are we in a remotely published or deleted activity?
        working_state = get_activity_working_state(repo, master_name, branch_name)
        local_branch = get_branch_if_exists_locally(repo, master_name, branch_name)
        if working_state == constants.WORKING_STATE_PUBLISHED:
            tag_ref = repo.tag('refs/tags/{}'.format(branch_name))
            commit = tag_ref.commit
            published_date = repo.git.show('--format=%ad', '--date=relative', commit.hexsha).strip()
            published_by = commit.committer.email
            flash_only(MESSAGE_ACTIVITY_PUBLISHED.format(published_date=published_date, published_by=published_by), u'warning')

            # if the published branch doesn't exist locally, raise a 404
            if not local_branch:
                abort(404)

        elif working_state == constants.WORKING_STATE_DELETED:
            flash_only(MESSAGE_ACTIVITY_DELETED, u'warning')

            # if the deleted branch doesn't exist locally, raise a 404
            if not local_branch:
                abort(404)

        else:
            # if the branch doesn't exist, raise a 404
            branch = get_existing_branch(repo, master_name, branch_name)
            if not branch:
                abort(404)

            branch.checkout()
            Logger.debug('  checked out to {}'.format(branch))

            # Push upstream only if the request method indicates a change.
            if request.method in ('PUT', 'POST', 'DELETE'):
                mark_upstream_push_needed(current_app.config['RUNNING_STATE_DIR'])

        return route_function(*args, **kwargs)

    return decorated_function

def flash_unique(message, category):
    ''' Add the passed message to flash messages if it's not an exact dupe of
        an existing message.
    '''
    session_flashes = session.get('_flashes', [])
    if (category, message) not in session_flashes:
        flash(message, category)

def flash_only(message, category, by_category=False):
    ''' Add the passed message to flash messages if there's not already a
        message in the queue. Pass by_category=True and the passed message
        will be flashed if it's the only one of its type.
    '''
    session_flashes = session.get('_flashes', [])
    if not by_category:
        if not len(session_flashes):
            flash(message, category)

    else:
        # category is in the first position in the flash tuples
        if category not in [item[0] for item in session_flashes]:
            flash(message, category)

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
                message_details[display_type]['noun'] = file_display_name(display_type)
                message_details[display_type]['files'] = []
            else:
                message_details[display_type]['noun'] = file_type_plural(display_type)
            message_details[display_type]['files'].append(file_details)
    commit_message = u'The "{}" {}'.format(root_file['title'], file_display_name(root_file['display_type']))
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
        name, email, date, subject, body = tuple([item for item in log_details])
        commit_category, commit_type, commit_action = get_commit_classification(subject, body)
        log_item = dict(author_name=name, author_email=email, commit_date=date, commit_subject=subject,
                        commit_body=body, commit_category=commit_category, commit_type=commit_type,
                        commit_action=commit_action)
        history.append(log_item)
        # don't get any history beyond the creation of the task metadata file, which is the beginning of the activity
        if re.search(r'{}$'.format(ACTIVITY_CREATED_MESSAGE), subject):
            break

    return history

def make_list_of_published_activities(repo, limit=10):
    ''' Make a list of recently published activities.
    '''
    # ;;;

    # something like this...?
    # http://git-scm.com/docs/git-for-each-ref
    # git for-each-ref --format="%(refname:short) %(*authoremail) %(taggerdate:relative) %(subject)" --sort=-taggerdate refs/tags

    published = []

    return published

def summarize_activity_history(repo=None, history=None, branch_name=u''):
    ''' Make an object that summarizes an activity's history. If no history is passed, will get a new one from make_activity_history()

        The object looks like this:
        {
            'summary': u'3 articles and 1 category have been changed',
            'changes': [
                {'edit_path': u'', 'display_type': u'Article', 'actions': u'Created, Edited, Deleted', 'title': u'How to Find Us'},
                {'edit_path': u'/tree/34246e3/edit/contact/hours-of-operation/', 'display_type': u'Article', 'actions': u'Created, Edited', 'title': u'Hours of Operation'},
                {'edit_path': u'/tree/34246e3/edit/contact/driving-directions/', 'display_type': u'Article', 'actions': u'Created, Edited', 'title': u'Driving Directions'},
                {'edit_path': u'/tree/34246e3/edit/contact/', 'display_type': u'Category', 'actions': u'Created', 'title': u'Contact'}
            ]
        }
    '''
    # an empty summary object
    summary = dict(summary=u'', changes=[])

    # make sure we've got what we need
    if not history:
        try:
            history = make_activity_history(repo=repo)
        except:
            # we weren't given what we need, return an empty summary
            return summary

    ed_lookup = {'create': u'created', 'edit': u'edited', 'delete': u'deleted'}
    change_lookup = {}
    display_types_encountered = []
    # we only care about edits
    edit_history = [action for action in reversed(history) if action['commit_category'] == constants.COMMIT_CATEGORY_EDIT]
    for action in edit_history:
        # get the list of changed files from the commit body
        try:
            commit_body = json.loads(action['commit_body'])
        except:
            # could't parse json in the commit body, keep moving
            continue

        # step through the changed files
        for file_change in commit_body:
            # the passed title or the filename if no title is there
            title = file_change['title'] or file_change['file_path'].split('/')[-1]
            # the passed display type or Unknown if no type is there
            display_type = file_change['display_type'].title() or u'Unknown'
            try:
                action = ed_lookup[file_change['action']].title()
            except:
                action = file_change['action'].title()
            file_path = file_change['file_path']
            # if the last action is delete, we don't want an edit_path to a file that no longer exists
            edit_path = join(u'/tree/{}/edit/'.format(branch_name), strip_index_file(file_path)) if action != u'Deleted' else u''
            sort_time = datetime.now()
            if file_path in change_lookup:
                change_lookup[file_path]['sort_time'] = sort_time
                # add the action to the end of the list if it's different from the last action added
                if not re.search(r'{}$'.format(action), change_lookup[file_path]['actions']):
                    change_lookup[file_path]['actions'] = change_lookup[file_path]['actions'] + u', {}'.format(action)
                # add the other variables, which may've changed
                change_lookup[file_path]['edit_path'] = edit_path
                change_lookup[file_path]['title'] = title
                change_lookup[file_path]['display_type'] = display_type
            else:
                change_lookup[file_path] = dict(title=title, display_type=display_type, actions=action, edit_path=edit_path, sort_time=sort_time)
                display_types_encountered.append(display_type)

    # flatten and sort the changes
    changes = [change_lookup[item] for item in change_lookup]
    if len(changes):
        changes.sort(key=lambda k: k['sort_time'], reverse=True)
        summary['changes'] = changes

        # now construct the summary sentence
        summary_sentence_parts = []
        display_type_tally = Counter(display_types_encountered)
        display_lookup = (
            (display_type_tally[ARTICLE_LAYOUT.title()], unicode(ARTICLE_LAYOUT), unicode(file_type_plural(ARTICLE_LAYOUT))),
            (display_type_tally[CATEGORY_LAYOUT.title()], unicode(CATEGORY_LAYOUT), unicode(file_type_plural(CATEGORY_LAYOUT)))
        )
        for tally, singular, plural in display_lookup:
            if tally:
                summary_sentence_parts.append("{} {}".format(tally, singular if tally == 1 else plural))
        has_have = u''
        has_have = u'have' if len(changes) > 1 else u'has'
        summary_sentence = u'{} {} been changed'.format(u', '.join(summary_sentence_parts[:-2] + [u' and '.join(summary_sentence_parts[-2:])]), has_have)
        summary['summary'] = summary_sentence

    return summary

def sorted_paths(repo, branch_name, path=None, showallfiles=False):
    ''' Returns a list of files and their attributes in the passed directory.
    '''
    full_path = join(repo.working_dir, path or '.').rstrip('/')
    all_sorted_files_dirs = sorted(listdir(full_path))

    file_names = [filename for filename in all_sorted_files_dirs if not FILE_FILTERS_COMPILED.search(filename)]
    if showallfiles:
        file_names = all_sorted_files_dirs

    view_paths = [join('/tree/{}/view'.format(branch_name2path(branch_name)), join(path or '', fn)) for fn in file_names]
    full_paths = [join(full_path, name) for name in file_names]
    path_pairs = zip(full_paths, view_paths)

    # name, title, view_path, display_type, is_editable, modified_date
    path_details = []
    for (edit_path, view_path) in path_pairs:
        if realpath(edit_path) != repo.git_dir:
            info = {}
            info['name'] = basename(edit_path)
            info['display_type'] = path_display_type(edit_path)
            info['link_name'] = u'{}/'.format(info['name']) if info['display_type'] in (FOLDER_FILE_TYPE, CATEGORY_LAYOUT, ARTICLE_LAYOUT) else info['name']
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
                        {'name': 'hello', 'title': 'Hello', 'base_path': '', 'file_path': 'hello', 'edit_path': '/tree/8bf27f6/edit/hello/', 'view_path': '/tree/dfffcd8/view/hello', 'display_type': 'category', 'is_editable': False, 'modified_date': '75 minutes ago', 'selected': True},
                        {'name': 'goodbye', 'title': 'Goodbye', 'base_path': '', 'file_path': 'goodbye', 'edit_path': '/tree/8bf27f6/edit/goodbye/', 'view_path': '/tree/dfffcd8/view/goodbye', 'display_type': 'category', 'is_editable': False, 'modified_date': '2 days ago', 'selected': False}
                    ]
                },
                {'base_path': 'hello',
                 'files':
                    [
                        {'name': 'world', 'title': 'World', 'base_path': 'hello', 'file_path': 'hello/world', 'edit_path': '/tree/8bf27f6/edit/hello/world/', 'view_path': '/tree/dfffcd8/view/hello/world', 'display_type': 'category', 'is_editable': False, 'modified_date': '75 minutes ago', 'selected': True},
                        {'name': 'moon', 'title': 'Moon', 'base_path': 'hello', 'file_path': 'hello/moon', 'edit_path': '/tree/8bf27f6/edit/hello/moon/', 'view_path': '/tree/dfffcd8/view/hello/moon', 'display_type': 'category', 'is_editable': False, 'modified_date': '4 days ago', 'selected': False}
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
        listing = [{'name': item['name'], 'title': item['title'], 'base_path': base_path, 'file_path': join(base_path, item['link_name']), 'edit_path': join(current_edit_path, item['link_name']), 'modify_path': join(current_modify_path, item['link_name']), 'view_path': item['view_path'], 'display_type': item['display_type'], 'is_editable': item['is_editable'], 'modified_date': item['modified_date'], 'selected': (current_dir == item['name'])} for item in files]
        # explicitly sort the list alphabetically by title
        listing.sort(key=lambda k: k['title'])
        dir_listings.append({'base_path': base_path, 'files': listing})

    return dir_listings

def publish_commit(repo, publish_path):
    ''' Publish current commit from the given repo to the publish_path directory.
    '''
    try:
        checkout_dir = mkdtemp(prefix='built-site-')

        # http://stackoverflow.com/questions/4479960/git-checkout-to-a-specific-folder
        environ['GIT_WORK_TREE'], old_GWT = checkout_dir, environ.get('GIT_WORK_TREE')
        repo.git.checkout(repo.commit().hexsha, '.')

        built_dir = build_jekyll_site(checkout_dir)

        call = 'rsync -ur --delete {built_dir}/ {publish_path}/'.format(**locals())
        rsync = Popen(call.split())
        rsync.wait()
    
    finally:
        # Clean up GIT_WORK_TREE so we don't pollute the environment.
        if old_GWT:
            environ['GIT_WORK_TREE'] = old_GWT
        else:
            del environ['GIT_WORK_TREE']

def update_activity_review_state(safe_branch, comment_text, action_list, redirect_path):
    ''' Update the activity review state, which may include merging, abandoning, or clobbering
        the associated branch.
    '''
    repo = get_repo(flask_app=current_app)
    action, action_authorized = get_activity_action_and_authorized(branch_name=safe_branch, comment_text=comment_text, action_list=action_list)
    if action_authorized:
        if action in ('merge', 'abandon', 'clobber'):
            try:
                return_redirect = publish_or_destroy_activity(safe_branch, action, comment_text)
            except MergeConflict as conflict:
                raise conflict
        else:
            # comment if comment text was sent and the action is authorized
            if comment_text:
                provide_feedback(clone=repo, comment_text=comment_text, push=True)

            # handle a review action
            if action != 'comment':
                if action == 'request_feedback':
                    update_review_state(clone=repo, new_review_state=current_app.config['REVIEW_STATE_FEEDBACK'], push=True)
                elif action == 'endorse_edits':
                    update_review_state(clone=repo, new_review_state=current_app.config['REVIEW_STATE_ENDORSED'], push=True)
            elif not comment_text:
                flash(u'You can\'t leave an empty comment!', u'warning')

            return_redirect = redirect(redirect_path, code=303)
    else:
        # flash a message if the action wasn't authorized
        action_lookup = {
            'comment': u'leave a comment',
            'request_feedback': u'request feedback',
            'endorse_edits': u'endorse the edits',
            'merge': u'publish the edits'
        }
        flash(u'Something changed behind the scenes and we couldn\'t {}! Please try again.'.format(action_lookup[action]), u'error')

        return_redirect = redirect(redirect_path, code=303)

    # return the redirect
    return return_redirect

def publish_or_destroy_activity(branch_name, action, comment_text=None):
    ''' Publish, abandon, or clobber the activity defined by the passed branch name.
    '''
    repo = get_repo(flask_app=current_app)
    master_name = current_app.config['default_branch']

    # contains 'author_email', 'task_description'
    activity = get_task_metadata_for_branch(repo, branch_name)
    activity['author_email'] = activity['author_email'] if 'author_email' in activity else u''
    activity['task_description'] = activity['task_description'] if 'task_description' in activity else u''

    try:
        args = repo, master_name, branch_name, comment_text

        if action == 'merge':
            complete_branch(*args)
        elif action == 'abandon':
            abandon_branch(*args)
        elif action == 'clobber':
            clobber_default_branch(*args)
        else:
            raise Exception(u'Tried to {} an activity, and I don\'t know how to do that.'.format(action))

        if current_app.config['PUBLISH_PATH']:
            publish_commit(repo, current_app.config['PUBLISH_PATH'])

    except MergeConflict as conflict:
        raise conflict

    else:
        activity_blurb = u'"{task_description}" activity'.format(task_description=activity['task_description'])
        if action == 'merge':
            flash(u'You published the {activity_blurb}!'.format(activity_blurb=activity_blurb), u'notice')
        elif action == 'abandon':
            flash(u'You deleted the {activity_blurb}!'.format(activity_blurb=activity_blurb), u'notice')
        elif action == 'clobber':
            flash(u'You clobbered the {activity_blurb}!'.format(activity_blurb=activity_blurb), u'notice')

        return redirect('/', code=303)

def render_activities_list(task_description=None):
    ''' Render the activities list page
    '''
    repo = ChimeRepo(current_app.config['REPO_PATH'])
    master_name = current_app.config['default_branch']
    branch_names = [b.name for b in repo.branches if b.name != master_name]

    activities = []
    for branch_name in branch_names:
        safe_branch = branch_name2path(branch_name)

        try:
            repo.git.merge_base(master_name, branch_name)
        except GitCommandError:
            # Skip this branch if it looks to be an orphan. Just don't show it.
            continue

        # contains 'author_email', 'task_description'
        activity = get_task_metadata_for_branch(repo, branch_name)
        activity['author_email'] = activity['author_email'] if 'author_email' in activity else u''
        activity['task_description'] = activity['task_description'] if 'task_description' in activity else branch_name

        # get the current review state and authorized status
        review_state, review_authorized = get_review_state_and_authorized(
            repo=repo, default_branch_name=current_app.config['default_branch'],
            working_branch_name=branch_name, actor_email=session.get('email', None)
        )

        date_created = repo.git.log('--format=%ad', '--date=relative', '--', TASK_METADATA_FILENAME).split('\n')[-1]
        date_updated = repo.git.log('--format=%ad', '--date=relative').split('\n')[0]

        # the email of the last person who edited the activity
        last_edited_email = get_last_edited_email(
            repo=repo, default_branch_name=current_app.config['default_branch'],
            working_branch_name=branch_name
        )

        activity.update(date_created=date_created, date_updated=date_updated,
                        edit_path=u'/tree/{}/edit/'.format(branch_name2path(branch_name)),
                        overview_path=u'/tree/{}/'.format(branch_name2path(branch_name)),
                        safe_branch=safe_branch, review_state=review_state,
                        review_authorized=review_authorized, last_edited_email=last_edited_email)

        activities.append(activity)

    kwargs = common_template_args(current_app.config, session)
    kwargs.update(activities=activities)

    # pre-populate the new activity form with description value if it was passed
    if task_description:
        kwargs.update(task_description=task_description)

    return render_template('activities-list.html', **kwargs)

def make_kwargs_for_activity_files_page(repo, branch_name, path):
    ''' Assemble the kwargs for a page that shows an activity's files.
    '''
    # :NOTE: temporarily turning off filtering if 'showallfiles=true' is in the request
    showallfiles = request.args.get('showallfiles') == u'true'

    # contains 'author_email', 'task_description'
    activity = get_task_metadata_for_branch(repo, branch_name)
    activity['author_email'] = activity['author_email'] if 'author_email' in activity else u''
    activity['task_description'] = activity['task_description'] if 'task_description' in activity else u''

    # get created and modified dates via git logs (relative dates for now)
    date_created = repo.git.log('--format=%ad', '--date=relative', '--', TASK_METADATA_FILENAME).split('\n')[-1]
    date_updated = repo.git.log('--format=%ad', '--date=relative').split('\n')[0]

    # get the current review state and authorized status
    review_state, review_authorized = get_review_state_and_authorized(
        repo=repo, default_branch_name=current_app.config['default_branch'],
        working_branch_name=branch_name, actor_email=session.get('email', None)
    )

    working_state = get_activity_working_state(repo, current_app.config['default_branch'], branch_name)

    activity.update(date_created=date_created, date_updated=date_updated,
                    edit_path=u'/tree/{}/edit/'.format(branch_name2path(branch_name)),
                    overview_path=u'/tree/{}/'.format(branch_name2path(branch_name)),
                    review_state=review_state, review_authorized=review_authorized,
                    working_state=working_state)

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

    # contains 'author_email', 'task_description'
    activity = get_task_metadata_for_branch(repo, branch_name)
    activity['author_email'] = activity['author_email'] if 'author_email' in activity else u''
    activity['task_description'] = activity['task_description'] if 'task_description' in activity else u''

    # get the current review state and authorized status
    review_state, review_authorized = get_review_state_and_authorized(
        repo=repo, default_branch_name=current_app.config['default_branch'],
        working_branch_name=branch_name, actor_email=session.get('email', None)
    )

    working_state = get_activity_working_state(repo, current_app.config['default_branch'], branch_name)

    activity.update(edit_path=u'/tree/{}/edit/'.format(branch_name2path(branch_name)),
                    overview_path=u'/tree/{}/'.format(branch_name2path(branch_name)),
                    review_state=review_state, review_authorized=review_authorized,
                    working_state=working_state)

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
    if create_what not in (ARTICLE_LAYOUT, CATEGORY_LAYOUT):
        raise ValueError(u'Can\'t create {} in {}.'.format(create_what, join(dir_path, request_path)))

    request_path = request_path.rstrip('/')

    # create the article or category
    display_name = request_path
    slug_name = slugify(request_path)
    name = u'{}/index.{}'.format(slug_name, CONTENT_FILE_EXTENSION)
    file_path = repo.canonicalize_path(dir_path, name)

    if create_what == ARTICLE_LAYOUT:
        redirect_path = file_path
        create_front = dict(title=display_name, description=u'', order=0, layout=ARTICLE_LAYOUT)
    elif create_what == CATEGORY_LAYOUT:
        redirect_path = strip_index_file(file_path)
        create_front = dict(title=display_name, description=u'', order=0, layout=CATEGORY_LAYOUT)

    display_what = file_display_name(create_what)
    if repo.exists(file_path):
        return '{} "{}" already exists'.format(display_what.title(), request_path), file_path, redirect_path, False

    file_path = create_new_page(clone=repo, dir_path=dir_path, request_path=name, front=create_front, body=u'')
    action_descriptions = [{'action': u'create', 'title': display_name, 'display_type': create_what, 'file_path': file_path}]
    commit_message = u'The "{}" {} was created\n\n{}'.format(display_name, display_what, json.dumps(action_descriptions, ensure_ascii=False))

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

def get_activity_action_and_authorized(branch_name, comment_text, action_list):
    ''' Return the proposed action and whether it's authorized
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
    action_authorized = (action == 'comment')

    # handle a review action
    if action != 'comment':
        if action == 'request_feedback':
            if review_state == current_app.config['REVIEW_STATE_EDITED'] and review_authorized:
                action_authorized = True
        elif action == 'endorse_edits':
            if review_state == current_app.config['REVIEW_STATE_FEEDBACK'] and review_authorized:
                action_authorized = True
        elif action == 'merge':
            if review_state == current_app.config['REVIEW_STATE_ENDORSED'] and review_authorized:
                action_authorized = True
        elif action == 'clobber' or action == 'abandon':
            action_authorized = True

    if not action:
        action_authorized = False

    return action, action_authorized

def get_preview_asset_response(working_dir, path):
    ''' Make sure a Jekyll preview is ready and return a response for the passed asset.
    '''
    build_jekyll_site(working_dir)

    view_path = join(working_dir, constants.JEKYLL_BUILD_DIRECTORY_NAME, path or '')

    # make sure the path points to something that exists
    exists_path = strip_index_file(view_path.rstrip('/'))
    if not exists(exists_path):
        abort(404)

    local_base, _ = splitext(view_path)

    if isdir(local_base):
        local_base += '/index'

    local_paths = glob(local_base + '.*')

    if not local_paths:
        flash_only(MESSAGE_ACTIVITY_DELETED, u'warning')
        abort(500)

    local_path = local_paths[0]
    mime_type, _ = guess_type(local_path)

    return Response(open(local_path).read(), 200, {'Content-Type': mime_type})

def save_page(repo, default_branch_name, working_branch_name, file_path, new_values):
    ''' Save the page with the passed values
    '''
    did_save = True
    working_branch_name = branch_var2name(working_branch_name)
    if get_activity_working_state(repo, default_branch_name, working_branch_name) != constants.WORKING_STATE_ACTIVE:
        did_save = False
        return file_path, did_save

    existing_branch = get_existing_branch(repo, default_branch_name, working_branch_name)

    commit = existing_branch.commit

    if commit.hexsha != new_values.get('hexsha'):
        tmp_branch_name = make_branch_name()
        tmp_branch = repo.create_head(tmp_branch_name, commit=new_values.get('hexsha'), force=True)
        tmp_branch.checkout()
        possible_conflict = True
    
    else:
        existing_branch.checkout()
        possible_conflict = False
    
    # make sure order is an integer; otherwise default to 0
    try:
        order = int(dos2unix(new_values.get('order', '0')))
    except ValueError:
        order = 0

    # populate the jekyll front matter
    front = {
        'layout': dos2unix(new_values.get('layout')),
        'order': order,
        'title': dos2unix(new_values.get('en-title', '')),
        'description': dos2unix(new_values.get('en-description', ''))
    }
    for iso in load_languages(repo.working_dir):
        if iso != constants.ISO_CODE_ENGLISH:
            front['title-' + iso] = dos2unix(new_values.get(iso + '-title', ''))
            front['description-' + iso] = dos2unix(new_values.get(iso + '-description', ''))
            front['body-' + iso] = dos2unix(new_values.get(iso + '-body', ''))

    #
    # Write changes.
    #
    body = dos2unix(new_values.get('en-body', ''))
    update_page(repo, file_path, front, body)
    
    #
    # Commit the local file.
    #
    display_name = new_values.get('en-title')
    display_type = new_values.get('layout')
    action_descriptions = [{'action': u'edit', 'title': display_name, 'display_type': display_type, 'file_path': file_path}]
    commit_message = u'The "{}" {} was edited\n\n{}'.format(display_name, display_type, json.dumps(action_descriptions, ensure_ascii=False))
    c2 = save_local_working_file(repo, file_path, commit_message)

    if possible_conflict:
        try:
            repo.git.rebase(existing_branch.commit)
        except GitCommandError:
            published_date = repo.git.show('--format=%ad', '--date=relative', existing_branch.commit.hexsha).split('\n')[0]
            published_by = existing_branch.commit.committer.email
            flash(MESSAGE_PAGE_EDITED.format(published_date=published_date, published_by=published_by), u'error')
            did_save = False
            # Ditch the temporary branch now that rebase has failed.
            repo.git.reset(hard=True)
            existing_branch.checkout()
            repo.git.branch('-D', tmp_branch_name)
        else:
            rebase_commit = tmp_branch.commit
            # Ditch the temporary branch now that rebase has worked.
            existing_branch.checkout()
            repo.git.reset(rebase_commit, hard=True)
            repo.git.branch('-D', tmp_branch_name)

    sync_with_default_and_upstream_branches(repo, working_branch_name)

    repo.git.push('origin', working_branch_name)

    #
    # Try to merge from the master to the current branch.
    #
    try:
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
                        return file_path, did_save
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

    return file_path, did_save

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
