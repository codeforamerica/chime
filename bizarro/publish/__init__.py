from logging import getLogger
logger = getLogger('bizarro.publish')

from os.path import join
from tempfile import mkdtemp
from shutil import rmtree

from flask import Blueprint, Flask
from logging import getLogger, DEBUG

from .functions import process_local_commit

def release_commit(app, repo, commit_sha):
    '''
    '''
    print 'NEED TO RELEASE', repr(repo), commit_sha
    
    try:
        working_dir = mkdtemp()
        archive_path = join(working_dir, 'archive.zip')
        
        with open(archive_path, 'w') as file:
            repo.archive(file, commit_sha, format='zip')
        
        process_local_commit(archive_path)
        
    except Exception as e:
        print e
        logger.warning(e)

    finally:
        rmtree(working_dir)

publish = Blueprint('bizarro.publish', __name__, template_folder='templates')

def create_app(environ):
    app = Flask(__name__, static_folder='static')
    app.secret_key = 'boop'

    # attach routes and custom error pages here
    app.register_blueprint(publish)

    @app.before_first_request
    def before_first_request():
        '''
        '''
        if app.debug:
            getLogger('bizarro.publish').setLevel(DEBUG)

    return app

from . import views
