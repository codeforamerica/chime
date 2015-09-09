from __future__ import absolute_import
from logging import getLogger
Logger = getLogger('chime.views')

from os.path import join, isdir, exists
from re import compile, MULTILINE, sub, search

from requests import post
from slugify import slugify
from datetime import datetime
from flask import current_app, flash, render_template, redirect, request, Response, session, abort

from . import chime as app
from . import repo_functions, edit_functions
from . import publish
from .jekyll_functions import load_jekyll_doc, load_languages

from .view_functions import branch_name2path, branch_var2name, get_repo, login_required, lock_on_user, browserid_hostname_required, synch_required, synched_checkout_required, should_redirect, make_redirect, get_auth_data_file, is_allowed_email, common_template_args, log_application_errors, is_article_dir, is_category_dir, make_activity_history, summarize_activity_history, render_edit_view, render_modify_dir, render_list_dir, add_article_or_category, strip_index_file, delete_page, save_page, render_activities_list, update_activity_review_state, flash_only, flash_unique, file_display_name, get_redirect_path_for_solo_directory, get_preview_asset_response, CONTENT_FILE_EXTENSION, ARTICLE_LAYOUT, CATEGORY_LAYOUT, MESSAGE_ACTIVITY_DELETED, publish_commit

from .google_api_functions import read_ga_config, write_ga_config, request_new_google_access_and_refresh_tokens, authorize_google, get_google_personal_info, get_google_analytics_properties

from . import view_functions

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
    return render_activities_list()

@app.route('/not-allowed')
@log_application_errors
@browserid_hostname_required
def not_allowed():
    email = session.get('email', None)
    auth_data_href = current_app.config['AUTH_DATA_HREF']
    is_auth_data_default = bool(auth_data_href == view_functions.AUTH_DATA_HREF_DEFAULT)

    kwargs = common_template_args(current_app.config, session)
    kwargs.update(auth_url=auth_data_href, is_auth_data_default=is_auth_data_default)
    kwargs.update(support_email=current_app.config.get('SUPPORT_EMAIL_ADDRESS'))

    if not email:
        return render_template('signin.html', **kwargs)

    if not is_allowed_email(get_auth_data_file(auth_data_href), email):
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
@lock_on_user
@synch_required
def start_branch():
    repo = get_repo(flask_app=current_app)
    task_description = request.form.get('task_description').strip()
    master_name = current_app.config['default_branch']

    # require a task description
    if len(task_description) == 0:
        flash(u'Please describe what you\'re doing when you start a new activity!', u'warning')
        return render_activities_list()

    branch = repo_functions.get_start_branch(repo, master_name, task_description, session['email'])
    safe_branch = branch_name2path(branch.name)
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
    action_list = [item for item in request.form if item != 'comment_text']
    safe_branch = branch_name2path(branch_var2name(request.form.get('branch')))
    return update_activity_review_state(safe_branch=safe_branch, comment_text=comment_text, action_list=action_list, redirect_path='/tree/{}/'.format(safe_branch))

@app.route('/checkouts/<ref>.zip')
@log_application_errors
@login_required
@lock_on_user
@synch_required
def get_checkout(ref):
    '''
    '''
    r = get_repo(flask_app=current_app)

    bytes = publish.retrieve_commit_checkout(current_app.config['RUNNING_STATE_DIR'], r, ref)

    return Response(bytes.getvalue(), mimetype='application/zip')

@app.route('/tree/<branch_name>/view/', methods=['GET'])
@app.route('/tree/<branch_name>/view/<path:path>', methods=['GET'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def branch_view(branch_name, path=None):
    repo = get_repo(flask_app=current_app)
    return get_preview_asset_response(repo.working_dir, path)

@app.route('/tree/<branch_name>/edit/', methods=['GET'])
@app.route('/tree/<branch_name>/edit/<path:path>', methods=['GET'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def branch_edit(branch_name, path=None):
    repo = get_repo(flask_app=current_app)
    branch_name = branch_var2name(branch_name)
    if repo_functions.get_conflict(repo, current_app.config['default_branch']):
        flash_unique(repo_functions.MERGE_CONFLICT_WARNING_FLASH_MESSAGE, u'warning')

    full_path = join(repo.working_dir, path or '.').rstrip('/')

    # make sure the path points to something that exists
    if not exists(full_path):
        abort(404)

    if isdir(full_path):
        # if this is a directory representing an article, redirect to edit
        if is_article_dir(full_path):
            index_path = join(path or u'', u'index.{}'.format(CONTENT_FILE_EXTENSION))
            return redirect('/tree/{}/edit/{}'.format(branch_name2path(branch_name), index_path))

        # if the directory path didn't end with a slash, add it and redirect
        if path and not path.endswith('/'):
            return redirect('/tree/{}/edit/{}/'.format(branch_name2path(branch_name), path), code=302)

        # redirect inside solo directories if necessary
        redirect_path = get_redirect_path_for_solo_directory(repo, branch_name, path)
        if redirect_path:
            return redirect(redirect_path, code=302)

        # render the directory contents
        return render_list_dir(repo, branch_name, path)

    # it's a file, edit it
    return render_edit_view(repo, branch_name, path, open(full_path, 'r'))

@app.route('/tree/<branch_name>/modify/', methods=['GET'])
@app.route('/tree/<branch_name>/modify/<path:path>', methods=['GET'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def branch_show_category_form(branch_name, path=None):
    repo = get_repo(flask_app=current_app)
    branch_name = branch_var2name(branch_name)
    full_path = join(repo.working_dir, path or '.').rstrip('/')

    # if the directory path didn't end with a slash, add it
    if isdir(full_path) and path and not path.endswith('/'):
        return redirect('/tree/{}/modify/{}/'.format(branch_name2path(branch_name), path), code=302)

    if is_category_dir(full_path):
        # render the directory modification view
        return render_modify_dir(repo, branch_name, path)

    # if this is an article directory, redirect to edit
    if is_article_dir(full_path):
        index_path = join(path or u'', u'index.{}'.format(CONTENT_FILE_EXTENSION))
        return redirect('/tree/{}/edit/{}'.format(branch_name2path(branch_name), index_path))

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
    repo = get_repo(flask_app=current_app)
    # get a path to the category's index file
    path = path.rstrip('/')
    index_slug = path
    dir_path = join(repo.working_dir, index_slug)
    index_path = dir_path
    if not search(r'\/index.{}$'.format(CONTENT_FILE_EXTENSION), path):
        index_slug = join(path, u'index.{}'.format(CONTENT_FILE_EXTENSION))
        index_path = join(dir_path, u'index.{}'.format(CONTENT_FILE_EXTENSION))

    # delete the passed category
    if 'delete' in request.form:
        # delete the page
        redirect_path, do_save, commit_message = delete_page(repo=repo, browse_path=path, target_path=path)
        # save and redirect
        if do_save:
            master_name = current_app.config['default_branch']
            Logger.debug('save')
            repo_functions.save_working_file(clone=repo, path=path, message=commit_message, base_sha=repo.commit().hexsha, default_branch_name=master_name)
            # flash the human-readable part of the commit message
            flash_message = commit_message.split('\n')[0]
            flash(flash_message, u'notice')

        safe_branch = branch_name2path(branch_var2name(branch_name))
        return redirect('/tree/{}/edit/{}'.format(safe_branch, redirect_path), code=303)

    # save the passed category
    elif 'save' in request.form:
        # verify that it exists
        if isdir(index_path) or not exists(index_path):
            raise Exception(u'No writable file exists at {}!'.format(index_path))

        # get the form values
        new_values = {}
        for key in request.form:
            # ImmutableMultiDicts can have multiple values assigned to the same key
            values = request.form.getlist(key)
            new_values[key] = values[0] if len(values) == 1 else values

        # get the current contents of the file
        with open(index_path) as file:
            front_matter, en_body = load_jekyll_doc(file)

        # add en_body to the front matter
        front_matter['en_body'] = en_body
        check_front_matter = dict(front_matter)

        # now update the file description with the values from the form
        try:
            front_matter.update(new_values)
        except ValueError:
            raise Exception(u'Unable to update file at {}!'.format(index_path))

        # only write if there are changes
        safe_branch = branch_name2path(branch_var2name(branch_name))
        new_path = path
        if check_front_matter != front_matter:
            new_path, did_save = save_page(repo, current_app.config['default_branch'], branch_name, index_slug, new_values)
            if not did_save:
                flash(u'Unable to save changes to {}!'.format(front_matter['title']), u'error')
            else:
                flash(u'Saved changes to the {} topic! Remember to submit this change for feedback when you\'re ready to go live.'.format(front_matter['en-title']), u'notice')

        return redirect('/tree/{}/modify/{}'.format(safe_branch, strip_index_file(new_path)), code=303)

    else:
        raise Exception(u'Tried to modify a category, but received an unfamiliar command.')

@app.route('/tree/<branch_name>/edit/', methods=['POST'])
@app.route('/tree/<branch_name>/edit/<path:path>', methods=['POST'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def branch_edit_file(branch_name, path=None):
    repo = get_repo(flask_app=current_app)
    commit = repo.commit()
    safe_branch = branch_name2path(branch_var2name(branch_name))

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

    elif action == 'create' and (create_what == ARTICLE_LAYOUT or create_what == CATEGORY_LAYOUT) and create_path is not None:
        # don't allow empty names for categories or articles
        request_path = request.form['request_path'].strip()
        if len(request_path) == 0 or len(slugify(request_path)) == 0:
            if len(request_path) != 0:
                display_what = file_display_name(create_what)
                flash(u'{} is not an acceptable {} name!'.format(request_path, display_what), u'warning')
            else:
                describe_what = u'an article' if create_what == 'article' else u'a topic'
                flash(u'Please enter a name to create {}!'.format(describe_what), u'warning')
            return redirect('/tree/{}/edit/{}'.format(safe_branch, file_path), code=303)

        add_message, file_path, redirect_path, do_save = add_article_or_category(repo, create_path, request.form['request_path'], create_what)
        if do_save:
            commit = repo.commit()
            commit_message = add_message
            describe_what = file_display_name(create_what)
            flash(u'Created a new {} named {}! Remember to submit this change for feedback when you\'re ready to go live.'.format(describe_what, request.form['request_path']), u'notice')
        else:
            flash(add_message, u'notice')

    elif action == 'delete' and 'request_path' in request.form:
        redirect_path, do_save, commit_message = delete_page(repo=repo, browse_path=path, target_path=request.form['request_path'])
        if do_save:
            # flash the human-readable part of the commit message
            flash(u'{}! Remember to submit this change for feedback when you\'re ready to go live.'.format(commit_message.split('\n')[0]), u'notice')

    else:
        raise Exception(u'Tried to edit a file, but received an unfamiliar command.')

    if do_save:
        master_name = current_app.config['default_branch']
        Logger.debug('save')
        repo_functions.save_working_file(clone=repo, path=file_path, message=commit_message, base_sha=commit.hexsha, default_branch_name=master_name)

    return redirect('/tree/{}/edit/{}'.format(safe_branch, redirect_path), code=303)

@app.route('/tree/<branch_name>/', methods=['GET'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def show_activity_overview(branch_name):
    branch_name = branch_var2name(branch_name)
    repo = get_repo(flask_app=current_app)
    safe_branch = branch_name2path(branch_name)

    if repo_functions.get_conflict(repo, current_app.config['default_branch']):
        flash_unique(repo_functions.MERGE_CONFLICT_WARNING_FLASH_MESSAGE, u'warning')

    # contains 'author_email', 'task_description'
    activity = repo_functions.get_task_metadata_for_branch(repo, branch_name)
    activity['author_email'] = activity['author_email'] if 'author_email' in activity else u''
    activity['task_description'] = activity['task_description'] if 'task_description' in activity else u''

    kwargs = common_template_args(current_app.config, session)

    languages = load_languages(repo.working_dir)

    app_authorized = False
    ga_config = read_ga_config(current_app.config['RUNNING_STATE_DIR'])
    if ga_config.get('access_token'):
        app_authorized = True

    history = make_activity_history(repo=repo)
    history_summary = summarize_activity_history(history=history, branch_name=branch_name)

    # get the current review state and authorized status
    review_state, review_authorized = repo_functions.get_review_state_and_authorized(
        repo=repo, default_branch_name=current_app.config['default_branch'],
        working_branch_name=branch_name, actor_email=session.get('email', None)
    )

    # the email of the last person who edited the activity
    last_edited_email = repo_functions.get_last_edited_email(
        repo=repo, default_branch_name=current_app.config['default_branch'],
        working_branch_name=branch_name
    )

    date_created = repo.git.log('--format=%ad', '--date=relative', '--', repo_functions.TASK_METADATA_FILENAME).split('\n')[-1]
    date_updated = repo.git.log('--format=%ad', '--date=relative').split('\n')[0]

    working_state = repo_functions.get_activity_working_state(repo, current_app.config['default_branch'], branch_name)

    activity.update(date_created=date_created, date_updated=date_updated,
                    edit_path=u'/tree/{}/edit/'.format(safe_branch),
                    overview_path=u'/tree/{}/'.format(safe_branch), safe_branch=safe_branch,
                    branch=safe_branch, history=history, history_summary=history_summary,
                    review_state=review_state, review_authorized=review_authorized,
                    last_edited_email=last_edited_email, working_state=working_state)

    kwargs.update(activity=activity, app_authorized=app_authorized, languages=languages)

    return render_template('activity-overview.html', **kwargs)

@app.route('/tree/<branch_name>/', methods=['POST'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def edit_activity_overview(branch_name):
    ''' Handle a POST from a form on the activity overview page
    '''
    comment_text = request.form.get('comment_text', u'').strip()
    action_list = [item for item in request.form if item != 'comment_text']
    safe_branch = branch_name2path(branch_var2name(branch_name))
    return update_activity_review_state(safe_branch=safe_branch, comment_text=comment_text, action_list=action_list, redirect_path='/tree/{}/'.format(safe_branch))

@app.route('/tree/<branch_name>/history/', methods=['GET'])
@app.route('/tree/<branch_name>/history/<path:path>', methods=['GET'])
@log_application_errors
@login_required
@lock_on_user
@synched_checkout_required
def branch_history(branch_name, path=None):
    branch_name = branch_var2name(branch_name)

    repo = get_repo(flask_app=current_app)

    safe_branch = branch_name2path(branch_name)

    # contains 'author_email', 'task_description'
    activity = repo_functions.get_task_metadata_for_branch(repo, branch_name)
    activity['author_email'] = activity['author_email'] if 'author_email' in activity else u''
    activity['task_description'] = activity['task_description'] if 'task_description' in activity else u''

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

@app.route('/tree/<branch_name>/save/<path:path>', methods=['POST'])
@log_application_errors
@login_required
@lock_on_user
@synch_required
def branch_save(branch_name, path):
    ''' Handle a submission from the article-edit form.
    '''
    repo = get_repo(flask_app=current_app)
    safe_branch = branch_name2path(branch_var2name(branch_name))
    new_path, did_save = save_page(repo, current_app.config['default_branch'], branch_name, path, request.form)
    if did_save:
        flash(u'Saved changes to the {} article! Remember to submit this change for feedback when you\'re ready to go live.'.format(request.form['en-title']), u'notice')

    if request.form.get('action', '').lower() == 'preview':
        return redirect('/tree/{}/view/{}'.format(safe_branch, new_path), code=303)
    else:
        return redirect('/tree/{}/edit/{}'.format(safe_branch, new_path), code=303)

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

@app.route('/admin/publish', methods = ['POST'])
@log_application_errors
@login_required
def publish():
    repo = get_repo(flask_app=current_app)
    master_name = current_app.config['default_branch']
    repo.git.checkout(master_name)
    publish_commit(repo, current_app.config['PUBLISH_PATH'])
    flash(u'Published!', u'notice')
    return redirect('/admin')

@app.route('/<path:path>')
@log_application_errors
def all_other_paths(path):
    '''
    '''
    if should_redirect():
        return make_redirect()
    else:
        abort(404)
