from __future__ import absolute_import
from logging import getLogger
Logger = getLogger('chime.views')

from os.path import join, isdir, splitext, sep
from re import compile, MULTILINE, sub, search
from mimetypes import guess_type
from glob import glob

from git import Repo
from git.cmd import GitCommandError
from requests import post
from flask import current_app, flash, render_template, redirect, request, Response, session

from . import chime as app
from . import repo_functions, edit_functions
from . import publish
from .jekyll_functions import load_jekyll_doc, build_jekyll_site, load_languages
from .view_functions import (
    branch_name2path, branch_var2name, get_repo, dos2unix, login_required, browserid_hostname_required,
    synch_required, synched_checkout_required, breadcrumb_paths, directory_columns, should_redirect,
    make_redirect, get_auth_data_file, is_allowed_email, common_template_args, log_application_errors,
    is_article_dir, make_activity_history, make_delete_display_commit_message, CONTENT_FILE_EXTENSION,
    ARTICLE_LAYOUT, CATEGORY_LAYOUT
)

from .google_api_functions import (
    read_ga_config, write_ga_config, request_new_google_access_and_refresh_tokens,
    authorize_google, get_google_personal_info, get_google_analytics_properties,
    fetch_google_analytics_for_page)

@app.route('/', methods=['GET'])
@log_application_errors
@login_required
@synch_required
def index():
    repo = Repo(current_app.config['REPO_PATH']) # bare repo
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

        # behind_raw = repo.git.log(base + '..' + master_name, format='%H %at %ae')
        # ahead_raw = repo.git.log(base + '..' + branch_name, format='%H %at %ae')

        # pattern = compile(r'^(\w+) (\d+) (.+)$', MULTILINE)
        # # behind = [r.commit(sha) for (sha, t, e) in pattern.findall(behind_raw)]
        # # ahead = [r.commit(sha) for (sha, t, e) in pattern.findall(ahead_raw)]
        # behind = pattern.findall(behind_raw)
        # ahead = pattern.findall(ahead_raw)

        # contains 'author_email', 'task_description', 'task_beneficiary'
        activity = repo_functions.get_task_metadata_for_branch(repo, branch_name)
        activity['author_email'] = activity['author_email'] if 'author_email' in activity else u''
        activity['task_description'] = activity['task_description'] if 'task_description' in activity else branch_name
        activity['task_beneficiary'] = activity['task_beneficiary'] if 'task_beneficiary' in activity else u''

        # get the current review state and authorized status
        review_state, review_authorized = repo_functions.get_review_state_and_authorized(
            repo=repo, default_branch_name=current_app.config['default_branch'],
            working_branch_name=branch_name, actor_email=session.get('email', None)
        )

        date_created = repo.git.log('--format=%ad', '--date=relative', '--', repo_functions.TASK_METADATA_FILENAME).split('\n')[-1]
        date_updated = repo.git.log('--format=%ad', '--date=relative').split('\n')[0]

        # the email of the last person who edited the activity
        last_edited_email = repo_functions.get_last_edited_email(
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

    return render_template('activities-list.html', **kwargs)

@app.route('/not-allowed')
@log_application_errors
@browserid_hostname_required
def not_allowed():
    email = session.get('email', None)
    auth_data_href = current_app.config['AUTH_DATA_HREF']

    kwargs = common_template_args(current_app.config, session)
    kwargs.update(auth_url=auth_data_href)

    if not email:
        return render_template('signin.html', **kwargs)

    if not is_allowed_email(get_auth_data_file(auth_data_href), email):
        return render_template('signin.html', **kwargs)

    Logger.info("Redirecting from /not-allowed to /")
    return redirect('/')

@app.route('/sign-in', methods=['POST'])
@log_application_errors
def sign_in():
    posted = post('https://verifier.login.persona.org/verify',
                  data=dict(assertion=request.form.get('assertion'),
                            audience=current_app.config['BROWSERID_URL']))

    response = posted.json()

    if response.get('status', '') == 'okay':
        session['email'] = response['email']
        return 'OK'

    return Response('Failed', status=400)

@app.route('/sign-out', methods=['POST'])
@log_application_errors
def sign_out():
    if 'email' in session:
        session.pop('email')

    return 'OK'

@app.route('/setup', methods=['GET'])
@log_application_errors
@login_required
def setup():
    ''' Render a form that steps through application setup (currently only google analytics).
    '''
    values = common_template_args(current_app.config, session)

    ga_config = read_ga_config(current_app.config['RUNNING_STATE_DIR'])
    access_token = ga_config.get('access_token')

    if access_token:
        name, google_email, properties, backup_name = (None,) * 4
        try:
            # get the name and email associated with this google account
            name, google_email = get_google_personal_info(access_token)
        except Exception as e:
            error_message = e.args[0]
            error_type = e.args[1] if len(e.args) > 1 else None
            # let unexpected errors raise normally
            if error_type:
                flash(error_message, error_type)
            else:
                raise

        try:
            # get a list of google analytics properties associated with this google account
            properties, backup_name = get_google_analytics_properties(access_token)
        except Exception as e:
            error_message = e.args[0]
            error_type = e.args[1] if len(e.args) > 1 else None
            # let unexpected errors raise normally
            if error_type:
                flash(error_message, error_type)
            else:
                raise

        # try using the backup name if we didn't get a name from the google+ API
        if not name and backup_name != google_email:
            name = backup_name

        if not properties:
            flash(u'Your Google Account is not associated with any Google Analytics properties. Try connecting to Google with a different account.', u'error')

        values.update(dict(properties=properties, name=name, google_email=google_email))

    return render_template('authorize.html', **values)

@app.route('/callback')
@log_application_errors
def callback():
    ''' Complete Google authentication, get web properties, and show the form.
    '''
    try:
        # request (and write to config) current access and refresh tokens
        request_new_google_access_and_refresh_tokens(request)

    except Exception as e:
        error_message = e.args[0]
        error_type = e.args[1] if len(e.args) > 1 else None
        # let unexpected errors raise normally
        if error_type:
            flash(error_message, error_type)
        else:
            raise

    return redirect('/setup')

@app.route('/authorize', methods=['GET', 'POST'])
@log_application_errors
def authorize():
    ''' Start Google authentication.
    '''
    return authorize_google()

@app.route('/authorization-complete', methods=['POST'])
@log_application_errors
def authorization_complete():
    profile_id = request.form.get('property')
    project_domain = request.form.get('{}-domain'.format(profile_id))
    project_name = request.form.get('{}-name'.format(profile_id))
    project_domain = sub(r'http(s|)://', '', project_domain)
    project_name = project_name.strip()
    return_link = request.form.get('return_link') or u'/'
    # write the new values to the config file
    config_values = {'profile_id': profile_id, 'project_domain': project_domain}
    write_ga_config(config_values, current_app.config['RUNNING_STATE_DIR'])

    # pass the variables needed to summarize what's been done
    values = common_template_args(current_app.config, session)
    values.update(name=request.form.get('name'),
                  google_email=request.form.get('google_email'),
                  project_name=project_name, project_domain=project_domain,
                  return_link=return_link)

    return render_template('authorization-complete.html', **values)

@app.route('/authorization-failed')
@log_application_errors
def authorization_failed():
    kwargs = common_template_args(current_app.config, session)
    return render_template('authorization-failed.html', **kwargs)

@app.route('/start', methods=['POST'])
@log_application_errors
@login_required
@synch_required
def start_branch():
    repo = get_repo(current_app)
    task_description = request.form.get('task_description')
    task_beneficiary = request.form.get('task_beneficiary')
    master_name = current_app.config['default_branch']
    branch = repo_functions.get_start_branch(repo, master_name, task_description, task_beneficiary, session['email'])

    safe_branch = branch_name2path(branch.name)
    return redirect('/tree/{}/edit/'.format(safe_branch), code=303)

@app.route('/update', methods=['POST'])
@log_application_errors
@login_required
@synch_required
def update_activity():
    ''' Update the activity review state or merge, abandon, or clobber the posted branch
    '''
    safe_branch = branch_name2path(branch_var2name(request.form.get('branch')))
    action_list = [item for item in request.form if item != 'comment_text']
    action, action_authorized = update_activity_review_status(branch_name=safe_branch, comment_text=u'', action_list=action_list)
    if action_authorized:
        if action in ('merge', 'abandon', 'clobber'):
            return publish_or_destroy_activity(safe_branch, action)
        else:
            return redirect('/'.format(safe_branch), code=303)
    else:
        return redirect('/'.format(safe_branch), code=303)

def publish_or_destroy_activity(branch_name, action):
    ''' Publish, abandon, or clobber the activity defined by the passed branch name.
    '''
    repo = get_repo(current_app)
    master_name = current_app.config['default_branch']

    # contains 'author_email', 'task_description', 'task_beneficiary'
    activity = repo_functions.get_task_metadata_for_branch(repo, branch_name)
    activity['author_email'] = activity['author_email'] if 'author_email' in activity else u''
    activity['task_description'] = activity['task_description'] if 'task_description' in activity else u''
    activity['task_beneficiary'] = activity['task_beneficiary'] if 'task_beneficiary' in activity else u''

    try:
        args = repo, master_name, branch_name

        if action == 'merge':
            repo_functions.complete_branch(*args)
        elif action == 'abandon':
            repo_functions.abandon_branch(*args)
        elif action == 'clobber':
            repo_functions.clobber_default_branch(*args)
        else:
            raise Exception('I do not know what "%s" means' % action)

        if current_app.config['PUBLISH_SERVICE_URL']:
            publish.announce_commit(current_app.config['BROWSERID_URL'], repo, repo.commit().hexsha)

        else:
            publish.release_commit(current_app.config['RUNNING_STATE_DIR'], repo, repo.commit().hexsha)

    except repo_functions.MergeConflict as conflict:
        new_files, gone_files, changed_files = conflict.files()

        kwargs = common_template_args(current_app.config, session)
        kwargs.update(branch=branch_name, new_files=new_files,
                      gone_files=gone_files, changed_files=changed_files,
                      activity=activity)

        return render_template('merge-conflict.html', **kwargs)

    else:
        return redirect('/')

@app.route('/checkouts/<ref>.zip')
@log_application_errors
@login_required
@synch_required
def get_checkout(ref):
    '''
    '''
    r = get_repo(current_app)

    bytes = publish.retrieve_commit_checkout(current_app.config['RUNNING_STATE_DIR'], r, ref)

    return Response(bytes.getvalue(), mimetype='application/zip')

@app.route('/tree/<branch>/view/', methods=['GET'])
@app.route('/tree/<branch>/view/<path:path>', methods=['GET'])
@log_application_errors
@login_required
@synched_checkout_required
def branch_view(branch, path=None):
    r = get_repo(current_app)

    build_jekyll_site(r.working_dir)

    local_base, _ = splitext(join(join(r.working_dir, '_site'), path or ''))

    if isdir(local_base):
        local_base += '/index'

    local_paths = glob(local_base + '.*')

    if not local_paths:
        return '404: ' + local_base

    local_path = local_paths[0]
    mime_type, _ = guess_type(local_path)

    return Response(open(local_path).read(), 200, {'Content-Type': mime_type})

def render_list_dir(repo, branch_name, path):
    # :NOTE: temporarily turning off filtering if 'showallfiles=true' is in the request
    showallfiles = request.args.get('showallfiles') == u'true'

    # contains 'author_email', 'task_description', 'task_beneficiary'
    activity = repo_functions.get_task_metadata_for_branch(repo, branch_name)
    activity['author_email'] = activity['author_email'] if 'author_email' in activity else u''
    activity['task_description'] = activity['task_description'] if 'task_description' in activity else u''
    activity['task_beneficiary'] = activity['task_beneficiary'] if 'task_beneficiary' in activity else u''

    # get created and modified dates via git logs (relative dates for now)
    date_created = repo.git.log('--format=%ad', '--date=relative', '--', repo_functions.TASK_METADATA_FILENAME).split('\n')[-1]
    date_updated = repo.git.log('--format=%ad', '--date=relative').split('\n')[0]

    # get the current review state and authorized status
    review_state, review_authorized = repo_functions.get_review_state_and_authorized(
        repo=repo, default_branch_name=current_app.config['default_branch'],
        working_branch_name=branch_name, actor_email=session.get('email', None)
    )

    activity.update(date_created=date_created, date_updated=date_updated,
                    edit_path=u'/tree/{}/edit/'.format(branch_name2path(branch_name)),
                    overview_path=u'/tree/{}/'.format(branch_name2path(branch_name)),
                    review_state=review_state, review_authorized=review_authorized)

    kwargs = common_template_args(current_app.config, session)
    kwargs.update(branch=branch_name, safe_branch=branch_name2path(branch_name),
                  breadcrumb_paths=breadcrumb_paths(branch_name, path),
                  dir_columns=directory_columns(repo, branch_name, path, showallfiles),
                  activity=activity)

    return render_template('articles-list.html', **kwargs)

def render_edit_view(repo, branch_name, path, file):
    ''' Render the page that lets you edit a file
    '''
    front, body = load_jekyll_doc(file)
    languages = load_languages(repo.working_dir)
    url_slug = path
    # strip the index file from the slug if appropriate
    url_slug = sub(ur'index.{}$'.format(CONTENT_FILE_EXTENSION), u'', url_slug)
    view_path = join('/tree/{}/view'.format(branch_name2path(branch_name)), path)
    history_path = join('/tree/{}/history'.format(branch_name2path(branch_name)), path)
    folder_root_slug = u'/'.join([item for item in url_slug.split('/') if item][:-1]) + u'/'
    app_authorized = False
    ga_config = read_ga_config(current_app.config['RUNNING_STATE_DIR'])
    analytics_dict = {}
    if ga_config.get('access_token'):
        app_authorized = True
        analytics_dict = fetch_google_analytics_for_page(current_app.config, path, ga_config.get('access_token'))
    commit = repo.commit()

    # contains 'author_email', 'task_description', 'task_beneficiary'
    activity = repo_functions.get_task_metadata_for_branch(repo, branch_name)
    activity['author_email'] = activity['author_email'] if 'author_email' in activity else u''
    activity['task_description'] = activity['task_description'] if 'task_description' in activity else u''
    activity['task_beneficiary'] = activity['task_beneficiary'] if 'task_beneficiary' in activity else u''

    # get the current review state and authorized status
    review_state, review_authorized = repo_functions.get_review_state_and_authorized(
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
                  history_path=history_path, languages=languages,
                  breadcrumb_paths=breadcrumb_paths(branch_name, folder_root_slug),
                  app_authorized=app_authorized, activity=activity)
    kwargs.update(analytics_dict)
    return render_template('article-edit.html', **kwargs)

@app.route('/tree/<branch>/edit/', methods=['GET'])
@app.route('/tree/<branch>/edit/<path:path>', methods=['GET'])
@log_application_errors
@login_required
@synched_checkout_required
def branch_edit(branch, path=None):
    repo = get_repo(current_app)
    branch = branch_var2name(branch)

    full_path = join(repo.working_dir, path or '.').rstrip('/')

    if isdir(full_path):
        # if this is an editable directory (contains only an editable index file), redirect
        if is_article_dir(full_path):
            index_path = join(path or u'', u'index.{}'.format(CONTENT_FILE_EXTENSION))
            return redirect('/tree/{}/edit/{}'.format(branch_name2path(branch), index_path))

        # if the directory path didn't end with a slash, add it
        if path and not path.endswith('/'):
            return redirect('/tree/{}/edit/{}/'.format(branch_name2path(branch), path), code=302)

        # render the directory contents
        return render_list_dir(repo, branch, path)

    # it's a file, edit it
    return render_edit_view(repo, branch, path, open(full_path, 'r'))

def add_article_or_category(repo, dir_path, request_path, create_what):
    ''' Add an article or category
    '''
    request_path = request_path.rstrip('/')
    article_front = dict(title=u'', description=u'', order=0, layout=ARTICLE_LAYOUT)
    cat_front = dict(title=u'', description=u'', order=0, layout=CATEGORY_LAYOUT)
    body = u''

    # create and commit intermediate categories recursively
    if u'/' in request_path:
        cat_paths = repo.dirs_for_path(request_path)
        flash_messages = []
        for i in range(len(cat_paths)):
            cat_path = cat_paths[i]
            dir_cat_path = join(dir_path, sep.join(cat_paths[:i]))
            message, file_path, _, do_save = add_article_or_category(repo, dir_cat_path, cat_path, CATEGORY_LAYOUT)
            if do_save:
                Logger.debug('save')
                repo_functions.save_working_file(repo, file_path, message, repo.commit().hexsha, current_app.config['default_branch'])
            else:
                flash_messages.append(message)

        if len(flash_messages):
            flash(', '.join(flash_messages), u'notice')

    name = u'{}/index.{}'.format(splitext(request_path)[0], CONTENT_FILE_EXTENSION)

    if create_what == 'article':
        file_path = repo.canonicalize_path(dir_path, name)
        if repo.exists(file_path):
            return 'Article "{}" already exists'.format(request_path), file_path, file_path, False
        else:
            file_path = edit_functions.create_new_page(repo, dir_path, name, article_front, body)
            message = u'The "{}" article was created\n\ncreated new file {}'.format(name.split('/')[-2], file_path)
            redirect_path = file_path
            return message, file_path, redirect_path, True
    elif create_what == 'category':
        file_path = repo.canonicalize_path(dir_path, name)
        if repo.exists(file_path):
            return 'Category "{}" already exists'.format(request_path), file_path, strip_index_file(file_path), False
        else:
            file_path = edit_functions.create_new_page(repo, dir_path, name, cat_front, body)
            message = u'The "{}" category was created\n\ncreated new file {}'.format(name.split('/')[-2], file_path)
            redirect_path = strip_index_file(file_path)
            return message, file_path, redirect_path, True
    else:
        raise ValueError("Illegal {} creation request in {}".format(create_what, join(dir_path, request_path)))

def strip_index_file(file_path):
    return sub(r'index.{}$'.format(CONTENT_FILE_EXTENSION), '', file_path)

@app.route('/tree/<branch>/edit/', methods=['POST'])
@app.route('/tree/<branch>/edit/<path:path>', methods=['POST'])
@log_application_errors
@login_required
@synched_checkout_required
def branch_edit_file(branch, path=None):
    repo = get_repo(current_app)
    commit = repo.commit()

    path = path or u''
    action = request.form.get('action', '').lower()
    create_what = request.form.get('create_what', '').lower()
    create_path = request.form.get('create_path', path)
    do_save = True

    file_path = path
    commit_message = u''
    if action == 'upload' and 'file' in request.files:
        file_path = edit_functions.upload_new_file(repo, path, request.files['file'])
        redirect_path = path
        commit_message = u'Uploaded file "{}"'.format(file_path)

    elif action == 'create' and (create_what == 'article' or create_what == 'category') and create_path is not None:
        add_message, file_path, redirect_path, do_save = add_article_or_category(repo, create_path, request.form['request_path'], create_what)
        if do_save:
            commit = repo.commit()
            commit_message = add_message
        else:
            flash(add_message, u'notice')

    elif action == 'delete' and 'request_path' in request.form:
        # construct the commit message
        commit_message = make_delete_display_commit_message(repo, request.form['request_path'])

        # delete the file(s)
        candidate_file_paths = edit_functions.list_contained_files(repo, request.form['request_path'])
        deleted_file_paths, do_save = edit_functions.delete_file(repo, request.form['request_path'])

        # add details to the commit message
        file_files = u'files' if len(candidate_file_paths) > 1 else u'file'
        commit_message = commit_message + u'\n\ndeleted {} "{}"'.format(file_files, u'", "'.join(candidate_file_paths))

        # if we're in the path that's been deleted, redirect to the first still-existing directory in the path
        path_dirs = path.split('/')
        req_dirs = request.form['request_path'].split('/')
        if len(path_dirs) >= len(req_dirs) and path_dirs[len(req_dirs) - 1] == req_dirs[-1]:
            redirect_path = u'/'.join(req_dirs[:-1])
        else:
            redirect_path = path

    else:
        raise Exception(u'Unrecognized request posted to branch_edit_file()')

    if do_save:
        master_name = current_app.config['default_branch']
        Logger.debug('save')
        repo_functions.save_working_file(repo, file_path, commit_message, commit.hexsha, master_name)

    safe_branch = branch_name2path(branch_var2name(branch))
    return redirect('/tree/%s/edit/%s' % (safe_branch, redirect_path), code=303)

@app.route('/tree/<branch>/', methods=['GET'])
@log_application_errors
@login_required
@synched_checkout_required
def show_activity_overview(branch):
    branch_name = branch_var2name(branch)
    repo = get_repo(current_app)
    safe_branch = branch_name2path(branch_name)

    # contains 'author_email', 'task_description', 'task_beneficiary'
    activity = repo_functions.get_task_metadata_for_branch(repo, branch_name)
    activity['author_email'] = activity['author_email'] if 'author_email' in activity else u''
    activity['task_description'] = activity['task_description'] if 'task_description' in activity else u''
    activity['task_beneficiary'] = activity['task_beneficiary'] if 'task_beneficiary' in activity else u''

    kwargs = common_template_args(current_app.config, session)

    languages = load_languages(repo.working_dir)

    app_authorized = False
    ga_config = read_ga_config(current_app.config['RUNNING_STATE_DIR'])
    if ga_config.get('access_token'):
        app_authorized = True

    history = make_activity_history(repo)

    # get the current review state and authorized status
    review_state, review_authorized = repo_functions.get_review_state_and_authorized(
        repo=repo, default_branch_name=current_app.config['default_branch'],
        working_branch_name=branch_name, actor_email=session.get('email', None)
    )

    date_created = repo.git.log('--format=%ad', '--date=relative', '--', repo_functions.TASK_METADATA_FILENAME).split('\n')[-1]
    date_updated = repo.git.log('--format=%ad', '--date=relative').split('\n')[0]

    activity.update(date_created=date_created, date_updated=date_updated,
                    edit_path=u'/tree/{}/edit/'.format(branch_name2path(branch_name)),
                    overview_path=u'/tree/{}/'.format(branch_name2path(branch_name)),
                    safe_branch=safe_branch, history=history, review_state=review_state,
                    review_authorized=review_authorized)

    kwargs.update(activity=activity, app_authorized=app_authorized, languages=languages)

    return render_template('activity-overview.html', **kwargs)

@app.route('/tree/<branch>/', methods=['POST'])
@log_application_errors
@login_required
@synched_checkout_required
def edit_activity_overview(branch):
    ''' Handle a POST from a form on the activity overview page
    '''
    safe_branch = branch_name2path(branch_var2name(branch))
    comment_text = request.form.get('comment_text', u'').strip()
    action_list = [item for item in request.form if item != 'comment_text']
    action, action_authorized = update_activity_review_status(branch_name=safe_branch, comment_text=comment_text, action_list=action_list)
    if action_authorized:
        if action in ('merge', 'abandon', 'clobber'):
            return publish_or_destroy_activity(safe_branch, action)
        else:
            return redirect('/tree/{}/'.format(safe_branch), code=303)
    else:
        return redirect('/tree/{}/'.format(safe_branch), code=303)

def update_activity_review_status(branch_name, comment_text, action_list):
    ''' Comment and/or update the review state.
    '''
    repo = get_repo(current_app)
    # which submit button was pressed?
    action = u''
    possible_actions = ['comment', 'request_feedback', 'endorse_edits', 'merge', 'abandon', 'clobber']
    for check_action in possible_actions:
        if check_action in action_list:
            action = check_action
            break

    # get the current review state and authorized status
    review_state, review_authorized = repo_functions.get_review_state_and_authorized(
        repo=repo, default_branch_name=current_app.config['default_branch'],
        working_branch_name=branch_name, actor_email=session.get('email', None)
    )
    action_authorized = (action == 'comment' and comment_text)

    # handle a review action
    if action != 'comment':
        if action == 'request_feedback':
            if review_state == repo_functions.REVIEW_STATE_EDITED and review_authorized:
                repo_functions.update_review_state(repo, repo_functions.REVIEW_STATE_FEEDBACK)
                action_authorized = True
        elif action == 'endorse_edits':
            if review_state == repo_functions.REVIEW_STATE_FEEDBACK and review_authorized:
                repo_functions.update_review_state(repo, repo_functions.REVIEW_STATE_ENDORSED)
                action_authorized = True
        elif action == 'merge':
            if review_state == repo_functions.REVIEW_STATE_ENDORSED and review_authorized:
                action_authorized = True
        elif action == 'clobber' or action == 'abandon':
            action_authorized = True

    if not action:
        raise Exception(u'Unrecognized request sent to update_activity_review_status')

    # comment if comment text was sent and the action is authorized
    if comment_text and action_authorized:
        repo_functions.provide_feedback(repo, comment_text)

    # flash a message if the action wasn't authorized
    if not action_authorized:
        action_lookup = {
            'comment': u'leave a comment',
            'request_feedback': u'request feedback',
            'endorse_edits': u'endorse the edits',
            'merge': u'publish the edits'
        }
        flash(u'Something changed behind the scenes and we couldn\'t {}! Please try again.'.format(action_lookup[action]), u'error')

    return action, action_authorized

@app.route('/tree/<branch>/history/', methods=['GET'])
@app.route('/tree/<branch>/history/<path:path>', methods=['GET'])
@log_application_errors
@login_required
@synched_checkout_required
def branch_history(branch, path=None):
    branch_name = branch_var2name(branch)

    repo = get_repo(current_app)

    safe_branch = branch_name2path(branch_name)

    # contains 'author_email', 'task_description', 'task_beneficiary'
    activity = repo_functions.get_task_metadata_for_branch(repo, branch_name)
    activity['author_email'] = activity['author_email'] if 'author_email' in activity else u''
    activity['task_description'] = activity['task_description'] if 'task_description' in activity else u''
    activity['task_beneficiary'] = activity['task_beneficiary'] if 'task_beneficiary' in activity else u''

    article_edit_path = join('/tree/{}/edit'.format(branch_name2path(branch_name)), path)

    activity.update(edit_path=u'/tree/{}/edit/'.format(branch_name2path(branch_name)),
                    overview_path=u'/tree/{}/'.format(branch_name2path(branch_name)),
                    view_path=u'/tree/{}/view/'.format(branch_name2path(branch_name)))

    languages = load_languages(repo.working_dir)

    app_authorized = False

    ga_config = read_ga_config(current_app.config['RUNNING_STATE_DIR'])
    if ga_config.get('access_token'):
        app_authorized = True

    # see <http://git-scm.com/docs/git-log> for placeholders
    log_format = '%x00Name: %an\tEmail: %ae\tDate: %ad\tSubject: %s'
    pattern = compile(r'^\x00Name: (.*?)\tEmail: (.*?)\tDate: (.*?)\tSubject: (.*?)$', MULTILINE)
    log = repo.git.log('-30', '--format={}'.format(log_format), '--date=relative', path)

    history = []

    for (name, email, date, subject) in pattern.findall(log):
        history.append(dict(name=name, email=email, date=date, subject=subject))

    kwargs = common_template_args(current_app.config, session)
    kwargs.update(branch=branch_name, safe_branch=safe_branch,
                  history=history, path=path, languages=languages,
                  app_authorized=app_authorized, article_edit_path=article_edit_path,
                  activity=activity)

    return render_template('article-history.html', **kwargs)

@app.route('/tree/<branch>/save/<path:path>', methods=['POST'])
@log_application_errors
@login_required
@synch_required
def branch_save(branch, path):
    branch = branch_var2name(branch)
    safe_branch = branch_name2path(branch)
    master_name = current_app.config['default_branch']

    repo = get_repo(current_app)
    existing_branch = repo_functions.get_existing_branch(repo, master_name, branch)

    if not existing_branch:
        flash(u'There is no {} branch!'.format(branch), u'warning')
        return redirect('/')

    commit = existing_branch.commit

    if commit.hexsha != request.form.get('hexsha'):
        raise Exception('Out of date SHA: %s' % request.form.get('hexsha'))

    #
    # Write changes.
    #
    existing_branch.checkout()

    # make sure order is an integer; otherwise default to 0
    try:
        order = int(dos2unix(request.form.get('order', '0')))
    except ValueError:
        order = 0

    front = {
        'layout': dos2unix(request.form.get('layout')),
        'order': order,
        'title': dos2unix(request.form.get('en-title', '')),
        'description': dos2unix(request.form.get('en-description', ''))
    }

    for iso in load_languages(repo.working_dir):
        if iso != 'en':
            front['title-' + iso] = dos2unix(request.form.get(iso + '-title', ''))
            front['description-' + iso] = dos2unix(request.form.get(iso + '-description', ''))
            front['body-' + iso] = dos2unix(request.form.get(iso + '-body', ''))

    body = dos2unix(request.form.get('en-body', ''))
    edit_functions.update_page(repo, path, front, body)

    #
    # Try to merge from the master to the current branch.
    #
    try:
        message = u'The "{}" {} was edited\n\nsaved file "{}"'.format(request.form.get('en-title'), request.form.get('layout'), path)
        c2 = repo_functions.save_working_file(repo, path, message, commit.hexsha, master_name)
        # they may've renamed the page by editing the URL slug
        original_slug = path
        if search(r'\/index.{}$'.format(CONTENT_FILE_EXTENSION), path):
            original_slug = sub(ur'index.{}$'.format(CONTENT_FILE_EXTENSION), u'', path)

        # do some simple input cleaning
        new_slug = request.form.get('url-slug')
        if new_slug:
            new_slug = sub(r'\/+', '/', new_slug)

            if new_slug != original_slug:
                try:
                    repo_functions.move_existing_file(repo, original_slug, new_slug, c2.hexsha, master_name)
                except Exception as e:
                    error_message = e.args[0]
                    error_type = e.args[1] if len(e.args) > 1 else None
                    # let unexpected errors raise normally
                    if error_type:
                        flash(error_message, error_type)
                        return redirect('/tree/{}/edit/{}'.format(safe_branch, path), code=303)
                    else:
                        raise

                path = new_slug
                # append the index file if it's an editable directory
                if is_article_dir(join(repo.working_dir, new_slug)):
                    path = join(new_slug, u'index.{}'.format(CONTENT_FILE_EXTENSION))

    except repo_functions.MergeConflict as conflict:
        repo.git.reset(commit.hexsha, hard=True)

        Logger.debug('1 {}'.format(conflict.remote_commit))
        Logger.debug('  {}'.format(repr(conflict.remote_commit.tree[path].data_stream.read())))
        Logger.debug('2 {}'.format(conflict.local_commit))
        Logger.debug('  {}'.format(repr(conflict.local_commit.tree[path].data_stream.read())))
        raise

    return redirect('/tree/{}/edit/{}'.format(safe_branch, path), code=303)

@app.route('/.well-known/deploy-key.txt')
@log_application_errors
def deploy_key():
    ''' Return contents of public deploy key file.
    '''
    try:
        with open('/var/run/chime/deploy-key.txt') as file:
            return Response(file.read(), 200, content_type='text/plain')
    except IOError:
        return Response('Not found.', 404, content_type='text/plain')


@app.route('/<path:path>')
@log_application_errors
def all_other_paths(path):
    '''
    '''
    if should_redirect():
        return make_redirect()
    else:
        return 'OK'
