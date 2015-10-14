# -- coding: utf-8 --
from __future__ import absolute_import
from logging import getLogger
Logger = getLogger('chime.views')

from os.path import join, isdir, exists
from re import compile, MULTILINE, sub

from requests import post
from datetime import datetime
from urlparse import urlparse
from flask import current_app, flash, render_template, redirect, request, Response, session, abort

from . import chime as app
from . import constants, repo_functions, chime_activity
from . import publish
from .jekyll_functions import load_languages

# the decorator functions
from .view_functions import login_required, lock_on_user, browserid_hostname_required, synch_required, synched_checkout_required, log_application_errors
# everything else
from . import view_functions

from .google_api_functions import read_ga_config, write_ga_config, request_new_google_access_and_refresh_tokens, authorize_google, get_google_personal_info, get_google_analytics_properties

@app.after_request
def after_request(response):
    response.headers['Last-Modified'] = datetime.now()
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@app.route('/', methods=['GET'])
@log_application_errors
@login_required
@lock_on_user
@synch_required
def index():
    return redirect(constants.ROUTE_BROWSE_LIVE, code=303)

@app.route(constants.ROUTE_ACTIVITY, methods=['GET'])
@log_application_errors
@login_required
@lock_on_user
@synch_required
def activity():
    return view_functions.render_activities_list()

@app.route('/start-activity', methods=['GET'])
@log_application_errors
@login_required
@lock_on_user
@synch_required
def create_activity():
    return view_functions.render_activities_list(show_new_activity_modal=True)

@app.route('/not-allowed')
@log_application_errors
@browserid_hostname_required
def not_allowed():
    email = session.get('email', None)
    auth_data_href = current_app.config['AUTH_DATA_HREF']
    is_auth_data_default = bool(auth_data_href == view_functions.AUTH_DATA_HREF_DEFAULT)

    kwargs = view_functions.common_template_args(current_app.config, session)
    kwargs.update(auth_url=auth_data_href, is_auth_data_default=is_auth_data_default)
    kwargs.update(support_email=current_app.config.get('SUPPORT_EMAIL_ADDRESS'))

    if not email:
        return render_template('signin.html', **kwargs)

    if not view_functions.is_allowed_email(view_functions.get_auth_data_file(auth_data_href), email):
        return render_template('signin.html', **kwargs)

    Logger.info("Redirecting from /not-allowed to /")
    return redirect('/')

@app.route('/sign-in', methods=['POST', 'GET'])
@log_application_errors
def sign_in():
    assertion = request.form.get('assertion') if request.method == 'POST' else request.values.get('assertion')
    if not assertion:
        Logger.info("Failed Persona auth (no email address passed)")
        return Response('Failed', status=400)

    if current_app.config['ACCEPTANCE_TEST_MODE']:
        session['email'] = assertion
        Logger.info("bypassing auth")
    else:
        success, email = _verify_persona_assertion(assertion)
        if success:
            Logger.info("Successful Persona auth")
            session['email'] = email
        else:
            Logger.info("Failed Persona auth (rejected by Persona)")
            return Response('Failed', status=400)
    Logger.info(u'Logged in as "{}"'.format(session['email']))
    return 'OK'

def _verify_persona_assertion(assertion):
    posted = post('https://verifier.login.persona.org/verify',
                  data=dict(assertion=assertion,
                            audience=current_app.config['BROWSERID_URL']))
    response = posted.json()
    success = response.get('status', '') == 'okay'
    return success, response.get('email')

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
    values = view_functions.common_template_args(current_app.config, session)

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
    values = view_functions.common_template_args(current_app.config, session)
    values.update(name=request.form.get('name'),
                  google_email=request.form.get('google_email'),
                  project_name=project_name, project_domain=project_domain,
                  return_link=return_link)

    return render_template('authorization-complete.html', **values)

@app.route('/authorization-failed')
@log_application_errors
def authorization_failed():
    kwargs = view_functions.common_template_args(current_app.config, session)
    return render_template('authorization-failed.html', **kwargs)

@app.route('/start', methods=['GET', 'POST'])
@log_application_errors
@login_required
@lock_on_user
@synch_required
def start_branch():
    repo = view_functions.get_repo(flask_app=current_app)
    if request.method == 'POST':
        task_description = sub(r'\s+', ' ', request.form.get('task_description', u'')).strip()
    else:
        task_description = view_functions.make_new_activity_description()

    master_name = current_app.config['default_branch']

    # require a task description
    if len(task_description) == 0:
        flash(u'Please describe what you\'re doing when you start a new activity!', u'warning')
        return redirect(constants.ROUTE_ACTIVITY, code=303)

    branch = repo_functions.get_start_branch(repo, master_name, task_description, session['email'])
    safe_branch = view_functions.branch_name2path(branch.name)
    return redirect('/tree/{}/edit/'.format(safe_branch), code=303)

@app.route('/update', methods=['POST'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def update_activity():
    ''' Update the activity review state or merge, abandon, or clobber the posted branch
    '''
    comment_text = u''
    task_description = u''
    action_list = [item for item in request.form if item != 'comment_text']
    safe_branch = view_functions.branch_name2path(view_functions.branch_var2name(request.form.get('branch')))
    return view_functions.update_activity_review_state(repo=view_functions.get_repo(flask_app=current_app), working_branch_name=safe_branch, default_branch_name=current_app.config['default_branch'], comment_text=comment_text, task_description=task_description, action_list=action_list, redirect_path='/tree/{}/'.format(safe_branch))

@app.route('/checkouts/<ref>.zip')
@log_application_errors
@login_required
@lock_on_user
@synch_required
def get_checkout(ref):
    '''
    '''
    r = view_functions.get_repo(flask_app=current_app)

    bytes = publish.retrieve_commit_checkout(current_app.config['RUNNING_STATE_DIR'], r, ref)

    return Response(bytes.getvalue(), mimetype='application/zip')

@app.route('/tree/<branch_name>/view/', methods=['GET'])
@app.route('/tree/<branch_name>/view/<path:path>', methods=['GET'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def branch_view(branch_name, path=None):
    repo = view_functions.get_repo(flask_app=current_app)
    return view_functions.get_preview_asset_response(repo.working_dir, path)

@app.route(constants.ROUTE_BROWSE_LIVE, methods=['GET'])
@app.route('{}<path:path>'.format(constants.ROUTE_BROWSE_LIVE), methods=['GET'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def look_in_master(path=None):
    repo = view_functions.get_repo(flask_app=current_app)
    default_branch_name = current_app.config['default_branch']
    full_path = join(repo.working_dir, path or '.').rstrip('/')

    # make sure the path points to something that exists
    if not exists(full_path):
        abort(404)

    if isdir(full_path):
        # if this is a directory representing an article, redirect to to the index file within
        if view_functions.is_article_dir(full_path):
            index_path = join(path or u'', u'index.{}'.format(constants.CONTENT_FILE_EXTENSION))
            return redirect('{}{}'.format(constants.ROUTE_BROWSE_LIVE, index_path))

        # if the directory path didn't end with a slash, add it and redirect
        if path and not path.endswith('/'):
            return redirect('{}{}/'.format(constants.ROUTE_BROWSE_LIVE, path), code=302)

        # redirect inside solo directories if necessary
        redirect_path = view_functions.get_redirect_path_for_solo_directory(
            repo=repo, branch_name=default_branch_name,
            path=path, route_base_url=constants.ROUTE_BROWSE_LIVE
        )
        if redirect_path:
            return redirect(redirect_path, code=302)

        # render the directory contents
        return view_functions.render_articles_list(
            repo=repo, branch_name=default_branch_name,
            path=path, edit_base_url=constants.ROUTE_BROWSE_LIVE,
            modify_base_url=constants.ROUTE_MODIFY_LIVE
        )

    # it's a file, show the edit view
    return view_functions.render_edit_view(
        repo=repo, branch_name=default_branch_name,
        path=path, file=open(full_path, 'r'),
        base_save_path='/look/save'
    )

@app.route(constants.ROUTE_BROWSE_LIVE, methods=['POST'])
@app.route('{}<path:path>'.format(constants.ROUTE_BROWSE_LIVE), methods=['POST'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def handle_look_in_submit(path=None):
    ''' Handle submits from forms on the article list page
    '''
    repo = view_functions.get_repo(flask_app=current_app)
    default_branch_name = current_app.config['default_branch']
    # start a new branch to save any changes in
    working_branch_name = view_functions.start_activity_for_edits(repo, default_branch_name)
    try:
        redirect_path, did_save = view_functions.handle_article_list_submit(repo, working_branch_name, path)
    except Exception:
        # abandon the new branch and raise the exception
        repo_functions.abandon_branch(repo, default_branch_name, working_branch_name)
        raise

    if not did_save:
        # abandon the new branch
        repo_functions.abandon_branch(repo, default_branch_name, working_branch_name)
        # redirect to where we started
        return redirect('{}{}'.format(constants.ROUTE_BROWSE_LIVE, path), code=303)

    # redirect to the edit page in the new branch
    return redirect(redirect_path, code=303)

@app.route('/look/save/<path:path>', methods=['POST'])
@log_application_errors
@login_required
@lock_on_user
def handle_look_article_submit(path):
    ''' Handle a submission from the article-edit form.
    '''
    repo = view_functions.get_repo(flask_app=current_app)
    default_branch_name = current_app.config['default_branch']
    # start a new branch to save any changes in
    working_branch_name = view_functions.start_activity_for_edits(repo, default_branch_name)
    start_point = repo.branches[working_branch_name].commit.hexsha
    try:
        redirect_path, did_save = view_functions.handle_article_edit_submit(
            repo=repo, branch_name=working_branch_name, path=path, start_point=start_point
        )
    except Exception:
        # abandon the new branch and raise the exception
        repo_functions.abandon_branch(repo, default_branch_name, working_branch_name)
        raise

    if not did_save:
        # abandon the new branch
        repo_functions.abandon_branch(repo, default_branch_name, working_branch_name)
        # redirect to where we started
        return redirect('{}{}'.format(constants.ROUTE_BROWSE_LIVE, path), code=303)

    # redirect to the edit or view page in the new branch
    return redirect(redirect_path, code=303)

@app.route(constants.ROUTE_MODIFY_LIVE, methods=['GET'])
@app.route('{}<path:path>'.format(constants.ROUTE_MODIFY_LIVE), methods=['GET'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def look_at_master(path=None):
    repo = view_functions.get_repo(flask_app=current_app)
    default_branch_name = current_app.config['default_branch']
    full_path = join(repo.working_dir, path or '.').rstrip('/')

    # if the directory path didn't end with a slash, add it and redirect
    if isdir(full_path) and path and not path.endswith('/'):
        return redirect('{}{}/'.format(constants.ROUTE_MODIFY_LIVE, path), code=302)

    # if this is a category directory, render the modification view
    if view_functions.is_category_dir(full_path):
        return view_functions.render_category_modify(
            repo=repo, branch_name=default_branch_name, path=path,
            edit_base_url=constants.ROUTE_BROWSE_LIVE, modify_base_url=constants.ROUTE_MODIFY_LIVE
        )

    # if this is an article directory, add the index file and redirect to constants.ROUTE_BROWSE_LIVE
    if view_functions.is_article_dir(full_path):
        path = join(path or u'', u'index.{}'.format(constants.CONTENT_FILE_EXTENSION))

    # this is not a category or article directory; redirect to constants.ROUTE_BROWSE_LIVE
    return redirect('{}{}'.format(constants.ROUTE_BROWSE_LIVE, path))

@app.route(constants.ROUTE_MODIFY_LIVE, methods=['POST'])
@app.route('{}<path:path>'.format(constants.ROUTE_MODIFY_LIVE), methods=['POST'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def handle_look_at_submit(path=u''):
    ''' Handle submits from forms on the category modify page
    '''
    repo = view_functions.get_repo(flask_app=current_app)
    default_branch_name = current_app.config['default_branch']
    # start a new branch to save any changes in
    working_branch_name = view_functions.start_activity_for_edits(repo, default_branch_name)
    try:
        redirect_path, did_save = view_functions.handle_category_modify_submit(repo, working_branch_name, path)
    except Exception:
        # abandon the new branch and raise the exception
        repo_functions.abandon_branch(repo, default_branch_name, working_branch_name)
        raise

    if not did_save:
        # abandon the new branch
        repo_functions.abandon_branch(repo, default_branch_name, working_branch_name)
        # redirect where we started
        return redirect('{}{}'.format(constants.ROUTE_MODIFY_LIVE, path), code=303)

    # redirect to the modify or edit page in the new branch
    return redirect(redirect_path, code=303)

@app.route('/tree/<branch_name>/edit/', methods=['GET'])
@app.route('/tree/<branch_name>/edit/<path:path>', methods=['GET'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def branch_edit(branch_name, path=None):
    repo = view_functions.get_repo(flask_app=current_app)
    branch_name = view_functions.branch_var2name(branch_name)
    safe_branch = view_functions.branch_name2path(branch_name)
    working_state = repo_functions.get_activity_working_state(repo, current_app.config['default_branch'], safe_branch)

    # if this is a published branch, redirect to overview
    if working_state == constants.WORKING_STATE_PUBLISHED:
        return redirect('/tree/{}/'.format(safe_branch), code=303)

    # flash a conflict warning if necessary
    if repo_functions.get_conflict(repo, current_app.config['default_branch']):
        view_functions.flash_unique(repo_functions.MERGE_CONFLICT_WARNING_FLASH_MESSAGE, u'warning')

    full_path = join(repo.working_dir, path or '.').rstrip('/')

    # make sure the path points to something that exists
    if not exists(full_path):
        abort(404)

    if isdir(full_path):
        # if this is a directory representing an article, redirect to the index file within
        if view_functions.is_article_dir(full_path):
            index_path = join(path or u'', u'index.{}'.format(constants.CONTENT_FILE_EXTENSION))
            return redirect('/tree/{}/edit/{}'.format(safe_branch, index_path))

        # if the directory path didn't end with a slash, add it and redirect
        if path and not path.endswith('/'):
            return redirect('/tree/{}/edit/{}/'.format(safe_branch, path), code=302)

        # redirect inside solo directories if necessary
        redirect_path = view_functions.get_redirect_path_for_solo_directory(
            repo=repo, branch_name=branch_name, path=path
        )
        if redirect_path:
            return redirect(redirect_path, code=302)

        # render the directory contents
        return view_functions.render_articles_list(
            repo=repo, branch_name=branch_name, path=path
        )

    # it's a file, show the edit view
    return view_functions.render_edit_view(
        repo=repo, branch_name=branch_name,
        path=path, file=open(full_path, 'r')
    )

@app.route('/tree/<branch_name>/edit/', methods=['POST'])
@app.route('/tree/<branch_name>/edit/<path:path>', methods=['POST'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def handle_edit_submit(branch_name, path=None):
    ''' Handle submits from forms on the article list page
    '''
    repo = view_functions.get_repo(flask_app=current_app)
    redirect_path, _ = view_functions.handle_article_list_submit(repo, branch_name, path)
    return redirect(redirect_path, code=303)

@app.route('/tree/<branch_name>/modify/', methods=['GET'])
@app.route('/tree/<branch_name>/modify/<path:path>', methods=['GET'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def branch_show_category_form(branch_name, path=None):
    repo = view_functions.get_repo(flask_app=current_app)
    branch_name = view_functions.branch_var2name(branch_name)
    full_path = join(repo.working_dir, path or '.').rstrip('/')

    # if the directory path didn't end with a slash, add it
    if isdir(full_path) and path and not path.endswith('/'):
        return redirect('/tree/{}/modify/{}/'.format(view_functions.branch_name2path(branch_name), path), code=302)

    if view_functions.is_category_dir(full_path):
        # render the directory modification view
        return view_functions.render_category_modify(repo, branch_name, path)

    # if this is an article directory, redirect to edit
    if view_functions.is_article_dir(full_path):
        path = join(path or u'', u'index.{}'.format(constants.CONTENT_FILE_EXTENSION))

    # this is not a category or article directory; redirect to edit
    return redirect('/tree/{}/edit/{}'.format(branch_name, path))

@app.route('/tree/<branch_name>/modify/', methods=['POST'])
@app.route('/tree/<branch_name>/modify/<path:path>', methods=['POST'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def branch_modify_category(branch_name, path=u''):
    ''' Save edits to a category's title and description or delete a category and its contents.
    '''
    repo = view_functions.get_repo(flask_app=current_app)
    redirect_path, _ = view_functions.handle_category_modify_submit(repo, branch_name, path)
    return redirect(redirect_path, code=303)

@app.route('/tree/<branch_name>/', methods=['GET'])
@app.route('/tree/<branch_name>/rename/', methods=['GET'])
@app.route('/tree/<branch_name>/review/', methods=['GET'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def show_activity_overview(branch_name):
    branch_name = view_functions.branch_var2name(branch_name)
    repo = view_functions.get_repo(flask_app=current_app)
    safe_branch = view_functions.branch_name2path(branch_name)

    if repo_functions.get_conflict(repo, current_app.config['default_branch']):
        view_functions.flash_unique(repo_functions.MERGE_CONFLICT_WARNING_FLASH_MESSAGE, u'warning')

    kwargs = view_functions.common_template_args(current_app.config, session)

    languages = load_languages(repo.working_dir)

    app_authorized = False
    ga_config = read_ga_config(current_app.config['RUNNING_STATE_DIR'])
    if ga_config.get('access_token'):
        app_authorized = True

    if repo_functions.get_activity_working_state(repo, current_app.config['default_branch'], safe_branch) == constants.WORKING_STATE_ACTIVE:
        activity = chime_activity.ChimeActivity(repo=repo, branch_name=safe_branch, default_branch_name=current_app.config['default_branch'], actor_email=session.get('email', None))
    else:
        activity = chime_activity.ChimePublishedActivity(repo=repo, branch_name=safe_branch, default_branch_name=current_app.config['default_branch'])

    kwargs.update(safe_branch=branch_name, activity=activity, app_authorized=app_authorized, languages=languages)

    # check the request's base URL for modals
    modal_type = urlparse(request.base_url).path.rstrip('/').split('/')[-1]
    if modal_type == 'rename':
        kwargs.update(show_rename_modal=True)
    elif modal_type == 'review':
        kwargs.update(show_review_modal=True)

    return render_template('activity-overview.html', **kwargs)

@app.route('/tree/<branch_name>/comment/', methods=['POST'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def handle_comment_form(branch_name):
    ''' Handle the comment form on the overview page
    '''
    comment_text = request.form.get('comment_text', u'').strip() or u''
    safe_branch = view_functions.branch_name2path(view_functions.branch_var2name(branch_name))
    view_functions.submit_comment(repo=view_functions.get_repo(flask_app=current_app), working_branch_name=safe_branch, comment_text=comment_text)
    return redirect('/tree/{}/'.format(safe_branch), code=303)

@app.route('/tree/<branch_name>/rename/', methods=['POST'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def handle_rename_form(branch_name):
    ''' Handle the rename form on the overview page
    '''
    task_description = sub(r'\s+', ' ', request.form.get('task_description', u'')).strip()
    safe_branch = view_functions.branch_name2path(view_functions.branch_var2name(branch_name))
    view_functions.submit_description(repo=view_functions.get_repo(flask_app=current_app), default_branch_name=current_app.config['default_branch'], working_branch_name=safe_branch, task_description=task_description)
    return redirect('/tree/{}/'.format(safe_branch), code=303)

@app.route('/tree/<branch_name>/', methods=['POST'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def edit_activity_overview(branch_name):
    ''' Handle a POST from a form on the activity overview page
    '''
    comment_text = request.form.get('comment_text', u'').strip() or u''
    task_description = sub(r'\s+', ' ', request.form.get('task_description', u'')).strip()
    action_list = [item for item in request.form if item not in ('comment_text', 'task_description')]
    safe_branch = view_functions.branch_name2path(view_functions.branch_var2name(branch_name))
    return view_functions.update_activity_review_state(repo=view_functions.get_repo(flask_app=current_app), working_branch_name=safe_branch, default_branch_name=current_app.config['default_branch'], comment_text=comment_text, task_description=task_description, action_list=action_list, redirect_path='/tree/{}/'.format(safe_branch))

@app.route('/tree/<branch_name>/history/', methods=['GET'])
@app.route('/tree/<branch_name>/history/<path:path>', methods=['GET'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def branch_history(branch_name, path=None):
    branch_name = view_functions.branch_var2name(branch_name)
    safe_branch = view_functions.branch_name2path(branch_name)
    repo = view_functions.get_repo(flask_app=current_app)

    activity = chime_activity.ChimeActivity(repo=repo, branch_name=safe_branch, default_branch_name=current_app.config['default_branch'], actor_email=session.get('email', None))

    article_edit_path = join('/tree/{}/edit'.format(view_functions.branch_name2path(branch_name)), path)

    languages = load_languages(repo.working_dir)

    app_authorized = False

    ga_config = read_ga_config(current_app.config['RUNNING_STATE_DIR'])
    if ga_config.get('access_token'):
        app_authorized = True

    # see <http://git-scm.com/docs/git-log> for placeholders
    log_format = '%x00Name: %an\tEmail: %ae\tDate: %ar\tSubject: %s'
    pattern = compile(r'^\x00Name: (.*?)\tEmail: (.*?)\tDate: (.*?)\tSubject: (.*?)$', MULTILINE)
    log = repo.git.log('-30', '--format={}'.format(log_format), path)

    history = []

    for (name, email, date, subject) in pattern.findall(log):
        history.append(dict(name=name, email=email, date=date, subject=subject))

    kwargs = view_functions.common_template_args(current_app.config, session)
    kwargs.update(safe_branch=safe_branch,
                  history=history, path=path, languages=languages,
                  app_authorized=app_authorized, article_edit_path=article_edit_path,
                  activity=activity)

    return render_template('article-history.html', **kwargs)

@app.route('/tree/<branch_name>/save/<path:path>', methods=['POST'])
@log_application_errors
@login_required
@lock_on_user
def branch_save(branch_name, path):
    ''' Handle a submission from the article-edit form.
    '''
    repo = view_functions.get_repo(flask_app=current_app)
    redirect_path, _ = view_functions.handle_article_edit_submit(
        repo=repo, branch_name=branch_name, path=path
    )
    return redirect(redirect_path, code=303)

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

@app.route('/styleguide')
def styleguide():
    return render_template('styleguide.html')

@app.route('/admin')
@log_application_errors
@login_required
def admin():
    return render_template('admin.html')

@app.route('/admin/publish', methods=['POST'])
@log_application_errors
@login_required
def publish_branch():
    repo = view_functions.get_repo(flask_app=current_app)
    master_name = current_app.config['default_branch']
    repo.git.checkout(master_name)
    view_functions.publish_commit(repo, current_app.config['PUBLISH_PATH'])
    flash(u'Published!', u'notice')
    return redirect('/admin')

@app.route('/<path:path>')
@log_application_errors
def all_other_paths(path):
    '''
    '''
    if view_functions.should_redirect():
        return view_functions.make_redirect()
    else:
        abort(404)
