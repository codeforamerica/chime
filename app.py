from flask import Flask, redirect, request, Response
from os.path import join, isdir, realpath, basename
from urllib import quote, unquote
from os import listdir

from git import Repo
from jekyll import load_jekyll_doc, dump_jekyll_doc

_default_branch = 'master'
_repo_path = 'sample-site'
_user_id = 'mike@localhost'

app = Flask(__name__)

def get_repo():
    ''' Gets repository for the current user, cloned from the origin.
    '''
    user_dir = realpath(quote('repo-' + _user_id))
    
    if isdir(user_dir):
        user_repo = Repo(user_dir)
        user_repo.remotes.origin.fetch()
        return user_repo
    
    source_repo = Repo(_repo_path)
    user_repo = source_repo.clone(user_dir)
    
    return user_repo

def name_branch(description):
    ''' Generate a name for a branch from a description.
    
        Prepends with _user_id, and replaces spaces with dashes.

        TODO: follow rules in http://git-scm.com/docs/git-check-ref-format.html
    '''
    safe_description = description.replace('.', '-').replace(' ', '-')
    return quote(_user_id, '@.-_') + '/' + quote(safe_description, '-_!')

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

@app.route('/')
def index():
    r = get_repo()
    branch_names = [b.name for b in r.branches if b.name != _default_branch]
    
    list_item = '<li><a href="/tree/%(safe_branch)s/edit/">%(branch)s</a></li>'
    list_items = [list_item % dict(safe_branch=branch_name2path(name), branch=name)
                  for name in branch_names]
    
    html = '''<doctype: html>
<html>
<body>
    <ul>%(list_items)s</ul>
    <form action="/start" method="POST">
    <input name="branch" placeholder="branch name" type="text">
    <input type="submit">
    </form>
</body>
</html>''' % dict(list_items=''.join(list_items))
    
    return html

@app.route('/start', methods=['POST'])
def start_branch():
    r = get_repo()
    branch_desc = request.form.get('branch')
    branch_name = name_branch(branch_desc)
    branch = r.create_head(branch_name)

    r.remotes.origin.push(branch.name)
    
    safe_branch = branch_name2path(branch.name)
    
    return redirect('/tree/%s/edit/' % safe_branch, code=303)

@app.route('/merge', methods=['POST'])
def merge_branch():
    r = get_repo()
    branch_name = request.form.get('branch')
    branch = r.branches[branch_name]
    
    r.branches[_default_branch].checkout()
    
    try:
        r.git.merge(branch.name)
    
    except:
        r.git.reset(hard=True)
        branch.checkout()
        
        return 'FFFuuu'
    
    else:
        r.remotes.origin.push(_default_branch)
        r.remotes.origin.push(':' + branch.name)
        r.delete_head([branch])
    
        return 'Done'

@app.route('/tree/<branch>/edit/', methods=['GET'])
@app.route('/tree/<branch>/edit/<path:path>', methods=['GET'])
def branch_edit(branch, path=None):
    branch = branch_var2name(branch)

    r = get_repo()
    b = r.branches[branch]
    b.checkout()
    c = r.commit()
    
    full_path = join(r.working_dir, path or '.').rstrip('/')
    
    if isdir(full_path):
        full_paths = [join(full_path, name) for name in listdir(full_path)]
        good_paths = [fp for fp in full_paths if realpath(fp) != r.git_dir]
    
        list_item = '<li><a href="%(name)s">%(name)s</a></li>'
        list_items = [list_item % dict(name=basename(gp)) for gp in good_paths]
    
        html = '''<doctype: html>
<html>
<body>
    <ul>%(list_items)s</ul>
</body>
</html>''' % dict(list_items=''.join(list_items))
    
        return html
    
    with open(join(r.working_dir, path), 'r') as file:
        front, body = load_jekyll_doc(file)
        
        safe_branch = branch_name2path(branch)
    
        html = '''<doctype: html>
<html>
<body>
    <form action="/tree/%(safe_branch)s/save/%(path)s" method="POST">
    <p><input name="title" value="%(title)s" type="text">
    <p><textarea name="body">%(body)s</textarea>
    <p><input name="hexsha" value="%(hexsha)s" type="text">
    <p><input type="submit">
    </form>
    <form action="/merge" method="POST">
    <input name="branch" value="%(branch)s" type="hidden">
    <input type="submit" value="Merge">
    </form>
</body>
</html>''' % dict(branch=branch, safe_branch=safe_branch, path=path, title=front['title'], body=body, hexsha=c.hexsha)
        
        return html

@app.route('/tree/<branch>/save/<path:path>', methods=['POST'])
def branch_save(branch, path):
    branch = branch_var2name(branch)

    r = get_repo()
    b = r.branches[branch]
    b.checkout()
    c = r.commit()
    
    if c.hexsha != request.form.get('hexsha'):
        raise Exception('Out of date SHA: %s' % request.form.get('hexsha'))
    
    with open(join(r.working_dir, path), 'w') as file:
        front = dict(title=request.form.get('title'))
        body = request.form.get('body').replace('\r\n', '\n')
        
        dump_jekyll_doc(front, body, file)
    
    r.index.add([path])
    r.index.commit('Saved')
    r.remotes.origin.push(branch)
    
    safe_branch = branch_name2path(branch)

    return redirect('/tree/%s/edit/%s' % (safe_branch, path), code=303)

if __name__ == '__main__':
    app.run(debug=True)