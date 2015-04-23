from logging import getLogger
Logger = getLogger('bizarro.views')

from os.path import join, isdir, splitext
from re import compile, MULTILINE, sub
from mimetypes import guess_type
from glob import glob

from git import Repo
from git.cmd import GitCommandError
from requests import post
from flask import current_app, flash, render_template, redirect, request, Response, session

from . import bizarro as app
from . import repo_functions, edit_functions
from . import publish
from .jekyll_functions import load_jekyll_doc, build_jekyll_site, load_languages
from .view_functions import (
    branch_name2path, branch_var2name, get_repo, name_branch, dos2unix,
    login_required, synch_required, synched_checkout_required, sorted_paths,
    directory_paths, should_redirect, make_redirect, get_auth_data_file,
    is_allowed_email, relative_datetime_string, common_template_args, branch_required
    )
from .google_api_functions import (
    read_ga_config, write_ga_config, request_new_google_access_and_refresh_tokens,
    authorize_google, get_google_personal_info, get_google_analytics_properties,
    fetch_google_analytics_for_page, GA_CONFIG_FILENAME
    )

import json

@app.route('/')
@login_required
@synch_required
def index():
    r = Repo(current_app.config['REPO_PATH']) # bare repo
    master_name = current_app.config['default_branch']
    branch_names = [b.name for b in r.branches if b.name != master_name]

    list_items = []

    for name in branch_names:
        path = branch_name2path(name)

        try:
            base = r.git.merge_base(master_name, name)
        except GitCommandError:
            # Skip this branch if it looks to be an orphan. Just don't show it.
            continue

        behind_raw = r.git.log(base + '..' + master_name, format='%H %at %ae')
        ahead_raw = r.git.log(base + '..' + name, format='%H %at %ae')

        pattern = compile(r'^(\w+) (\d+) (.+)$', MULTILINE)
        # behind = [r.commit(sha) for (sha, t, e) in pattern.findall(behind_raw)]
        # ahead = [r.commit(sha) for (sha, t, e) in pattern.findall(ahead_raw)]
        behind = pattern.findall(behind_raw)
        ahead = pattern.findall(ahead_raw)

        if current_app.config['SINGLE_USER']:
            needs_peer_review = False
            is_peer_approved = True
            is_peer_rejected = False
        else:
            needs_peer_review = repo_functions.needs_peer_review(r, master_name, name)
            is_peer_approved = repo_functions.is_peer_approved(r, master_name, name)
            is_peer_rejected = repo_functions.is_peer_rejected(r, master_name, name)

        review_subject = 'Plz review this thing'
        review_body = '%s/tree/%s/edit' % (request.url, path)

        list_items.append(dict(name=name, path=path, behind=behind, ahead=ahead,
                               needs_peer_review=needs_peer_review,
                               is_peer_approved=is_peer_approved,
                               is_peer_rejected=is_peer_rejected,
                               review_subject=review_subject,
                               review_body=review_body))

    kwargs = common_template_args(current_app.config, session)
    kwargs.update(items=list_items)

    return render_template('index.html', **kwargs)

@app.route('/not-allowed')
def not_allowed():
    email = session.get('email', None)
    auth_data_href = current_app.config['AUTH_DATA_HREF']

    kwargs = common_template_args(current_app.config, session)
    kwargs.update(auth_url=auth_data_href)

    if not email:
        return render_template('not-allowed.html', **kwargs)

    if not is_allowed_email(get_auth_data_file(auth_data_href), email):
        return render_template('not-allowed.html', **kwargs)

    return redirect('/')

@app.route('/sign-in', methods=['POST'])
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
def sign_out():
    if 'email' in session:
        session.pop('email')

    return 'OK'

@app.route('/setup', methods=['GET'])
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
def authorize():
    ''' Start Google authentication.
    '''
    return authorize_google()

@app.route('/authorization-complete', methods=['POST'])
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
def authorization_failed():
    kwargs = common_template_args(current_app.config, session)
    return render_template('authorization-failed.html', **kwargs)

@app.route('/start', methods=['POST'])
@login_required
@synch_required
def start_branch():
    r = get_repo(current_app)
    branch_desc = request.form.get('branch')
    branch_name = name_branch(branch_desc)
    master_name = current_app.config['default_branch']
    branch = repo_functions.start_branch(r, master_name, branch_name)

    safe_branch = branch_name2path(branch.name)
    return redirect('/tree/%s/edit/' % safe_branch, code=303)

@app.route('/merge', methods=['POST'])
@login_required
@synch_required
def merge_branch():
    r = get_repo(current_app)
    branch_name = request.form.get('branch')
    master_name = current_app.config['default_branch']

    try:
        action = request.form.get('action', '').lower()
        args = r, master_name, branch_name

        if action == 'merge':
            repo_functions.complete_branch(*args)
        elif action == 'abandon':
            repo_functions.abandon_branch(*args)
        elif action == 'clobber':
            repo_functions.clobber_default_branch(*args)
        else:
            raise Exception('I do not know what "%s" means' % action)

        if current_app.config['PUBLISH_SERVICE_URL']:
            publish.announce_commit(current_app.config['BROWSERID_URL'], r, r.commit().hexsha)

        else:
            publish.release_commit(current_app.config['RUNNING_STATE_DIR'], r, r.commit().hexsha)

    except repo_functions.MergeConflict as conflict:
        new_files, gone_files, changed_files = conflict.files()

        kwargs = common_template_args(current_app.config, session)
        kwargs.update(branch=branch_name, new_files=new_files,
                      gone_files=gone_files, changed_files=changed_files)

        return render_template('merge-conflict.html', **kwargs)

    else:
        return redirect('/')

@app.route('/review', methods=['POST'])
@login_required
def review_branch():
    r = get_repo(current_app)
    branch_name = request.form.get('branch')
    branch = r.branches[branch_name]
    branch.checkout()

    try:
        action = request.form.get('action', '').lower()

        if action == 'approve':
            repo_functions.mark_as_reviewed(r)
        elif action == 'feedback':
            comments = request.form.get('comments')
            repo_functions.provide_feedback(r, comments)
        else:
            raise Exception('I do not know what "%s" means' % action)

    except repo_functions.MergeConflict as conflict:
        new_files, gone_files, changed_files = conflict.files()

        kwargs = common_template_args(current_app.config, session)
        kwargs.update(branch=branch_name, new_files=new_files,
                      gone_files=gone_files, changed_files=changed_files)

        return render_template('merge-conflict.html', **kwargs)

    else:
        safe_branch = branch_name2path(branch_name)

        return redirect('/tree/%s/edit/' % safe_branch, code=303)

@app.route('/checkouts/<ref>.zip')
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
@login_required
@branch_required
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

@app.route('/tree/<branch>/edit/', methods=['GET'])
@app.route('/tree/<branch>/edit/<path:path>', methods=['GET'])
@login_required
@branch_required
@synched_checkout_required
def branch_edit(branch, path=None):
    branch = branch_var2name(branch)

    r = get_repo(current_app)
    c = r.commit()

    full_path = join(r.working_dir, path or '.').rstrip('/')
    safe_branch = branch_name2path(branch)

    if isdir(full_path):
        if path and not path.endswith('/'):
            return redirect('/tree/%s/edit/%s' % (safe_branch, path + '/'), code=302)

        # :NOTE: temporarily turning off filtering if 'showallfiles=true' is in the request
        showallfiles = request.args.get('showallfiles') == u'true'

        kwargs = common_template_args(current_app.config, session)
        kwargs.update(branch=branch, safe_branch=safe_branch,
                      dirs_and_paths=directory_paths(branch, path),
                      list_paths=sorted_paths(r, branch, path, showallfiles))

        master_name = current_app.config['default_branch']
        kwargs['rejection_messages'] = list(repo_functions.get_rejection_messages(r, master_name, branch))

        # TODO: the above might throw a GitCommandError if branch is an orphan.

        if current_app.config['SINGLE_USER']:
            kwargs['eligible_peer'] = True
            kwargs['needs_peer_review'] = False
            kwargs['is_peer_approved'] = True
            kwargs['is_peer_rejected'] = False
        else:
            kwargs['eligible_peer'] = session['email'] != repo_functions.ineligible_peer(r, master_name, branch)
            kwargs['needs_peer_review'] = repo_functions.needs_peer_review(r, master_name, branch)
            kwargs['is_peer_approved'] = repo_functions.is_peer_approved(r, master_name, branch)
            kwargs['is_peer_rejected'] = repo_functions.is_peer_rejected(r, master_name, branch)

        if kwargs['is_peer_rejected']:
            kwargs['rejecting_peer'], kwargs['rejection_message'] = kwargs['rejection_messages'].pop(0)

        return render_template('tree-branch-edit-listdir.html', **kwargs)

    with open(full_path, 'r') as file:
        front, body = load_jekyll_doc(file)
        languages = load_languages(r.working_dir)

        url_slug, _ = splitext(path)
        view_path = join('/tree/%s/view' % branch_name2path(branch), path)
        history_path = join('/tree/%s/history' % branch_name2path(branch), path)
        app_authorized = False

        ga_config = read_ga_config(current_app.config['RUNNING_STATE_DIR'])
        analytics_dict = {}
        if ga_config.get('access_token'):
            app_authorized = True
            analytics_dict = fetch_google_analytics_for_page(current_app.config, path, ga_config.get('access_token'))

        kwargs = common_template_args(current_app.config, session)

        kwargs.update(branch=branch, safe_branch=safe_branch,
                      body=body, hexsha=c.hexsha, url_slug=url_slug,
                      front=front, view_path=view_path, edit_path=path,
                      history_path=history_path, languages=languages,
                      app_authorized=app_authorized)

        kwargs.update(analytics_dict)

        return render_template('tree-branch-edit-file.html', **kwargs)

@app.route('/tree/<branch>/edit/', methods=['POST'])
@app.route('/tree/<branch>/edit/<path:path>', methods=['POST'])
@login_required
@branch_required
@synched_checkout_required
def branch_edit_file(branch, path=None):
    r = get_repo(current_app)
    c = r.commit()

    action = request.form.get('action', '').lower()
    do_save = True

    if action == 'upload' and 'file' in request.files:
        file_path = edit_functions.upload_new_file(r, path, request.files['file'])
        message = 'Uploaded new file "%s"' % file_path
        path_303 = path or ''

    elif action == 'add' and 'path' in request.form:
        front, body = dict(title='', layout='default'), ''
        name = splitext(request.form['path'])[0] + '.html'

        file_path = edit_functions.create_new_page(r, path, name, front, body)
        message = 'Created new file "%s"' % file_path
        path_303 = file_path

    elif action == 'delete' and 'path' in request.form:
        file_path, do_save = edit_functions.delete_file(r, path, request.form['path'])
        message = 'Deleted file "%s"' % file_path
        path_303 = path or ''

    else:
        raise Exception()

    if do_save:
        master_name = current_app.config['default_branch']
        Logger.debug('save')
        repo_functions.save_working_file(r, file_path, message, c.hexsha, master_name)

    safe_branch = branch_name2path(branch_var2name(branch))

    return redirect('/tree/%s/edit/%s' % (safe_branch, path_303), code=303)

@app.route('/tree/<branch>/history/', methods=['GET'])
@app.route('/tree/<branch>/history/<path:path>', methods=['GET'])
@login_required
@branch_required
@synched_checkout_required
def branch_history(branch, path=None):
    branch = branch_var2name(branch)

    r = get_repo(current_app)

    safe_branch = branch_name2path(branch)

    view_path = join('/tree/%s/view' % branch_name2path(branch), path)
    edit_path = join('/tree/%s/edit' % branch_name2path(branch), path)
    languages = load_languages(r.working_dir)

    app_authorized = False

    ga_config = read_ga_config(current_app.config['RUNNING_STATE_DIR'])
    if ga_config.get('access_token'):
        app_authorized = True

    format = '%x00Name: %an\tEmail: %ae\tTime: %aD\tSubject: %s'
    pattern = compile(r'^\x00Name: (.*?)\tEmail: (.*?)\tTime: (.*?)\tSubject: (.*?)$', MULTILINE)
    log = r.git.log('-30', '--format=' + format, path)

    history = []

    for (name, email, time, subject) in pattern.findall(log):
        date = relative_datetime_string(time)
        history.append(dict(name=name, email=email, date=date, subject=subject))

    kwargs = common_template_args(current_app.config, session)
    kwargs.update(branch=branch, safe_branch=safe_branch,
                  history=history, view_path=view_path, edit_path=edit_path,
                  path=path, languages=languages, app_authorized=app_authorized)

    return render_template('tree-branch-history.html', **kwargs)

@app.route('/tree/<branch>/review/', methods=['GET'])
@login_required
@branch_required
@synched_checkout_required
def branch_review(branch):
    branch = branch_var2name(branch)

    r = get_repo(current_app)
    c = r.commit()

    kwargs = common_template_args(current_app.config, session)
    kwargs.update(branch=branch, safe_branch=branch_name2path(branch),
                  hexsha=c.hexsha)

    return render_template('tree-branch-review.html', **kwargs)

@app.route('/tree/<branch>/save/<path:path>', methods=['POST'])
@login_required
@branch_required
@synch_required
def branch_save(branch, path):
    branch = branch_var2name(branch)
    master_name = current_app.config['default_branch']

    r = get_repo(current_app)
    b = repo_functions.start_branch(r, master_name, branch)
    c = b.commit

    if c.hexsha != request.form.get('hexsha'):
        raise Exception('Out of date SHA: %s' % request.form.get('hexsha'))

    #
    # Write changes.
    #
    b.checkout()

    front = {'layout': dos2unix(request.form.get('layout')), 'title': dos2unix(request.form.get('en-title'))}

    for iso in load_languages(r.working_dir):
        if iso != 'en':
            front['title-' + iso] = dos2unix(request.form.get(iso + '-title', ''))
            front['body-' + iso] = dos2unix(request.form.get(iso + '-body', ''))

    body = dos2unix(request.form.get('en-body'))
    edit_functions.update_page(r, path, front, body)

    #
    # Try to merge from the master to the current branch.
    #
    try:
        message = 'Saved file "%s"' % path
        c2 = repo_functions.save_working_file(r, path, message, c.hexsha, master_name)
        new_path = request.form.get('url-slug') + splitext(path)[1]

        if new_path != path:
            repo_functions.move_existing_file(r, path, new_path, c2.hexsha, master_name)
            path = new_path

    except repo_functions.MergeConflict as conflict:
        r.git.reset(c.hexsha, hard=True)

        Logger.debug('1 {}'.format(conflict.remote_commit))
        Logger.debug('  {}'.format(repr(conflict.remote_commit.tree[path].data_stream.read())))
        Logger.debug('2 {}'.format(conflict.local_commit))
        Logger.debug('  {}'.format(repr(conflict.local_commit.tree[path].data_stream.read())))
        raise

    safe_branch = branch_name2path(branch)

    return redirect('/tree/%s/edit/%s' % (safe_branch, path), code=303)

@app.route('/.well-known/deploy-key.txt')
def deploy_key():
    ''' Return contents of public deploy key file.
    '''
    try:
        with open('/var/run/bizarro/deploy-key.txt') as file:
            return Response(file.read(), 200, content_type='text/plain')
    except IOError:
        return Response('Not found.', 404, content_type='text/plain')

@app.route('/<path:path>')
def all_other_paths(path):
    '''
    '''
    if should_redirect():
        return make_redirect()
    else:
        return 'OK'
