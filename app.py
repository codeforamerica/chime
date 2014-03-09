from flask import Flask, redirect, request, Response
from os.path import join

from git import Repo
from jekyll import load_jekyll_doc, dump_jekyll_doc

_default_branch = 'master'

app = Flask(__name__)

@app.route('/')
def index():
    r = Repo('sample-site')
    branch_names = [b.name for b in r.branches if b.name != _default_branch]
    
    list_item = '<li><a href="/tree/%(branch)s">%(branch)s</a></li>'
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
    r = Repo('sample-site')
    branch_name = request.form.get('branch')
    branch = r.create_head(branch_name)
    branch.checkout()
    
    return redirect('/tree/%s' % branch.name, code=303)

@app.route('/tree/<branch>/edit/<path:path>', methods=['GET'])
def branch_edit(branch, path):
    r = Repo('sample-site')
    c = r.commit()
    
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
</body>
</html>''' % dict(branch=branch, path=path, title=front['title'], body=body, hexsha=c.hexsha)
        
        return html

@app.route('/tree/<branch>/save/<path:path>', methods=['POST'])
def branch_save(branch, path):
    r = Repo('sample-site')
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