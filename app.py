from flask import Flask, redirect, request, Response
from os.path import join, isdir, realpath, basename
from os import listdir

from git import Repo
from jekyll import load_jekyll_doc, dump_jekyll_doc

_default_branch = 'master'
_repo_path = 'sample-site'

app = Flask(__name__)

@app.route('/')
def index():
    r = Repo(_repo_path)
    branch_names = [b.name for b in r.branches if b.name != _default_branch]
    
    list_item = '<li><a href="/tree/%(branch)s/edit/">%(branch)s</a></li>'
    list_items = [list_item % dict(branch=name) for name in branch_names]
    
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
    r = Repo(_repo_path)
    branch_name = request.form.get('branch')
    branch = r.create_head(branch_name)
    
    return redirect('/tree/%s/edit/' % branch.name, code=303)

@app.route('/merge', methods=['POST'])
def merge_branch():
    r = Repo(_repo_path)
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
        r.delete_head([branch])
    
        return 'Done'

@app.route('/tree/<branch>/edit/', methods=['GET'])
@app.route('/tree/<branch>/edit/<path:path>', methods=['GET'])
def branch_edit(branch, path=None):
    r = Repo(_repo_path)
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
        
        html = '''<doctype: html>
<html>
<body>
    <form action="/tree/%(branch)s/save/%(path)s" method="POST">
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
</html>''' % dict(branch=branch, path=path, title=front['title'], body=body, hexsha=c.hexsha)
        
        return html

@app.route('/tree/<branch>/save/<path:path>', methods=['POST'])
def branch_save(branch, path):
    r = Repo(_repo_path)
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
    
    return redirect('/tree/%s/edit/%s' % (branch, path), code=303)

if __name__ == '__main__':
    app.run(debug=True)