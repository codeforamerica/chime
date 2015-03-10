from logging import getLogger
logger = getLogger('bizarro.publish.views')

from flask import request, Response
from . import publish as app
from .functions import process_remote_commit

@app.route('/', methods=['POST'])
def index():
    payload = request.get_json(force=True)
    commit = payload.get('commits', [None])[0]
    
    if commit is None or 'url' not in commit:
        return Response('No', status=400)
    
    process_remote_commit(commit['url'], commit['sha'])
    
    return ''
