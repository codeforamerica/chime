from os.path import join, isdir, realpath, basename, splitext
from os import listdir, environ
from re import compile, MULTILINE
from mimetypes import guess_type
from glob import glob

from git import Repo
from requests import post
from flask import redirect, request, Response, render_template, session, current_app

from . import app
from . import repo as bizarro_repo
from . import edit as bizarro_edit
from .jekyll import load_jekyll_doc, build_jekyll_site
from .view_functions import (
  branch_name2path, branch_var2name, get_repo, path_type, name_branch, dos2unix,
  login_required, synch_required, synched_checkout_required
  )

_default_branch = 'master'

@app.route('/')
@synch_required
def index():
    r = Repo(current_app.config['REPO_PATH']) # bare repo
    branch_names = [b.name for b in r.branches if b.name != _default_branch]
    
    list_items = []
    
    for name in branch_names:
        path = branch_name2path(name)

        base = r.git.merge_base(_default_branch, name)
        behind_raw = r.git.log(base+'..'+_default_branch, format='%H %at %ae')
        ahead_raw = r.git.log(base+'..'+name, format='%H %at %ae')
        
        pattern = compile(r'^(\w+) (\d+) (.+)$', MULTILINE)
        # behind = [r.commit(sha) for (sha, t, e) in pattern.findall(behind_raw)]
        # ahead = [r.commit(sha) for (sha, t, e) in pattern.findall(ahead_raw)]
        behind = pattern.findall(behind_raw)
        ahead = pattern.findall(ahead_raw)
        
        needs_peer_review = bizarro_repo.needs_peer_review(r, _default_branch, name)
        is_peer_approved = bizarro_repo.is_peer_approved(r, _default_branch, name)
        is_peer_rejected = bizarro_repo.is_peer_rejected(r, _default_branch, name)
        
        review_subject = 'Plz review this thing'
        review_body = '%s/tree/%s/edit' % (request.url, path)

        list_items.append(dict(name=name, path=path, behind=behind, ahead=ahead,
                               needs_peer_review=needs_peer_review,
                               is_peer_approved=is_peer_approved,
                               is_peer_rejected=is_peer_rejected,
                               review_subject=review_subject,
                               review_body=review_body))
    
    kwargs = dict(items=list_items, email=session.get('email', None))
    return render_template('index.html', **kwargs)

@app.route('/sign-in', methods=['POST'])
def sign_in():
    posted = post('https://verifier.login.persona.org/verify',
                  data=dict(assertion=request.form.get('assertion'),
                            audience='http://127.0.0.1:5000'))

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

@app.route('/start', methods=['POST'])
@login_required
@synch_required
def start_branch():
    r = get_repo(current_app)
    branch_desc = request.form.get('branch')
    branch_name = name_branch(branch_desc)
    branch = bizarro_repo.start_branch(r, _default_branch, branch_name)
    
    safe_branch = branch_name2path(branch.name)
    
    return redirect('/tree/%s/edit/' % safe_branch, code=303)

@app.route('/merge', methods=['POST'])
@login_required
@synch_required
def merge_branch():
    r = get_repo(current_app)
    branch_name = request.form.get('branch')
    branch = r.branches[branch_name]
    
    try:
        action = request.form.get('action', '').lower()
        args = r, _default_branch, branch_name
        
        if action == 'merge':
            bizarro_repo.complete_branch(*args)
        elif action == 'abandon':
            bizarro_repo.abandon_branch(*args)
        elif action == 'clobber':
            bizarro_repo.clobber_default_branch(*args)
        else:
            raise Exception('I do not know what "%s" means' % action)
    
    except bizarro_repo.MergeConflict as conflict:
        new_files, gone_files, changed_files = conflict.files()
        
        kwargs = dict(branch=branch_name, new_files=new_files,
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
            bizarro_repo.mark_as_reviewed(r)
        elif action == 'feedback':
            comments = request.form.get('comments')
            bizarro_repo.provide_feedback(r, comments)
        else:
            raise Exception('I do not know what "%s" means' % action)
    
    except bizarro_repo.MergeConflict as conflict:
        new_files, gone_files, changed_files = conflict.files()
    
        kwargs = dict(branch=branch_name, new_files=new_files,
                      gone_files=gone_files, changed_files=changed_files)
        
        return render_template('merge-conflict.html', **kwargs)
    
    else:
        safe_branch = branch_name2path(branch_name)

        return redirect('/tree/%s/edit/' % safe_branch, code=303)

@app.route('/tree/<branch>/view/', methods=['GET'])
@app.route('/tree/<branch>/view/<path:path>', methods=['GET'])
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

@app.route('/tree/<branch>/edit/', methods=['GET'])
@app.route('/tree/<branch>/edit/<path:path>', methods=['GET'])
@login_required
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
    
        file_names = [n for n in listdir(full_path) if not n.startswith('_')]
        view_paths = [join('/tree/%s/view' % branch_name2path(branch), join(path or '', fn))
                      for fn in file_names]
        
        full_paths = [join(full_path, name) for name in file_names]
        path_pairs = zip(full_paths, view_paths)
        
        list_paths = [(basename(fp), vp, path_type(fp))
                      for (fp, vp) in path_pairs if realpath(fp) != r.git_dir]

        kwargs = dict(branch=branch, safe_branch=safe_branch,
                      email=session['email'], list_paths=list_paths)

        kwargs['needs_peer_review'] = bizarro_repo.needs_peer_review(r, _default_branch, branch)
        kwargs['is_peer_approved'] = bizarro_repo.is_peer_approved(r, _default_branch, branch)
        kwargs['is_peer_rejected'] = bizarro_repo.is_peer_rejected(r, _default_branch, branch)
        kwargs['eligible_peer'] = session['email'] != bizarro_repo.ineligible_peer(r, _default_branch, branch)
        kwargs['rejection_messages'] = list(bizarro_repo.get_rejection_messages(r, _default_branch, branch))
        
        if kwargs['is_peer_rejected']:
            kwargs['rejecting_peer'], kwargs['rejection_message'] = kwargs['rejection_messages'].pop(0)

        return render_template('tree-branch-edit-listdir.html', **kwargs)
    
    with open(full_path, 'r') as file:
        front, body = load_jekyll_doc(file)
        
        url_slug, _ = splitext(path)
        view_path = join('/tree/%s/view' % branch_name2path(branch), path)
        
        kwargs = dict(branch=branch, safe_branch=safe_branch,
                      body=body, hexsha=c.hexsha, url_slug=url_slug,
                      front=front, email=session['email'],
                      view_path=view_path, edit_path=path)

        return render_template('tree-branch-edit-file.html', **kwargs)

@app.route('/tree/<branch>/edit/', methods=['POST'])
@app.route('/tree/<branch>/edit/<path:path>', methods=['POST'])
@login_required
@synched_checkout_required
def branch_edit_file(branch, path=None):
    r = get_repo(current_app)
    c = r.commit()
    
    action = request.form.get('action', '').lower()
    do_save = True
    
    if action == 'upload' and 'file' in request.files:
        file_path = bizarro_edit.upload_new_file(r, path, request.files['file'])
        message = 'Uploaded new file "%s"' % file_path
        path_303 = path or ''
    
    elif action == 'add' and 'path' in request.form:
        front, body = dict(title='', layout='multi'), ''
        name = splitext(request.form['path'])[0] + '.md'

        file_path = bizarro_edit.create_new_page(r, path, name, front, body)
        message = 'Created new file "%s"' % file_path
        path_303 = file_path
    
    elif action == 'delete' and 'path' in request.form:
        file_path = bizarro_edit.delete_file(r, path, request.form['path'])
        message = 'Deleted file "%s"' % file_path
        path_303 = path or ''
    
    else:
        raise Exception()
    
    if do_save:
        bizarro_repo.save_working_file(r, file_path, message, c.hexsha, _default_branch)

    safe_branch = branch_name2path(branch_var2name(branch))

    return redirect('/tree/%s/edit/%s' % (safe_branch, path_303), code=303)

@app.route('/tree/<branch>/review/', methods=['GET'])
@login_required
@synched_checkout_required
def branch_review(branch):
    branch = branch_var2name(branch)

    r = get_repo(current_app)
    c = r.commit()

    kwargs = dict(branch=branch, safe_branch=branch_name2path(branch),
                  hexsha=c.hexsha, email=session['email'])

    return render_template('tree-branch-review.html', **kwargs)

@app.route('/tree/<branch>/save/<path:path>', methods=['POST'])
@login_required
@synch_required
def branch_save(branch, path):
    branch = branch_var2name(branch)

    r = get_repo(current_app)
    b = bizarro_repo.start_branch(r, _default_branch, branch)
    c = b.commit
    
    if c.hexsha != request.form.get('hexsha'):
        raise Exception('Out of date SHA: %s' % request.form.get('hexsha'))
    
    #
    # Write changes.
    #
    b.checkout()
    
    front = {'layout': dos2unix(request.form.get('layout')),
             'title':  dos2unix(request.form.get('title')),
             'title-es': dos2unix(request.form.get('title-es')),
             'body-es':  dos2unix(request.form.get('body-es')),
             'title-zh-cn': dos2unix(request.form.get('title-zh-cn')),
             'body-zh-cn':  dos2unix(request.form.get('body-zh-cn'))}

    body = dos2unix(request.form.get('body'))
    bizarro_edit.update_page(r, path, front, body)
    
    #
    # Try to merge from the master to the current branch.
    #
    try:
        message = 'Saved file "%s"' % path
        c2 = bizarro_repo.save_working_file(r, path, message, c.hexsha, _default_branch)
        new_path = request.form.get('url-slug') + splitext(path)[1]
        
        if new_path != path:
            bizarro_repo.move_existing_file(r, path, new_path, c2.hexsha, _default_branch)
            path = new_path
        
    except bizarro_repo.MergeConflict as conflict:
        r.git.reset(c.hexsha, hard=True)
    
        print 1, conflict.remote_commit
        print ' ', repr(conflict.remote_commit.tree[path].data_stream.read())
        print 2, conflict.local_commit
        print ' ', repr(conflict.local_commit.tree[path].data_stream.read())
        raise
    
    safe_branch = branch_name2path(branch)

    return redirect('/tree/%s/edit/%s' % (safe_branch, path), code=303)
