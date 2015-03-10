from logging import getLogger, DEBUG
logger = getLogger('bizarro')

from os import mkdir
from os.path import realpath, join

from flask import Blueprint, Flask

from .httpd import run_apache_forever

bizarro = Blueprint('bizarro', __name__, template_folder='templates')

class AppShim:

    def __init__(self, app, run_apache):
        '''
        '''
        running_dir = app.config['RUNNING_STATE_DIR']
        logger.debug('Starting AppShim in {running_dir}'.format(**locals()))
    
        self.app = app
        self.config = app.config
        self.httpd = None
        
        root = join(realpath(running_dir), 'apache')
        doc_root = join(realpath(running_dir), 'master')

        if run_apache:
            try:
                mkdir(root)
                mkdir(doc_root)
            except OSError:
                pass
            port = 5001
            self.httpd = run_apache_forever(doc_root, root, port, False)
    
    def app_context(self, *args, **kwargs):
        ''' Used in tests.
        '''
        return self.app.app_context(*args, **kwargs)
    
    def test_client(self, *args, **kwargs):
        ''' Used in tests.
        '''
        return self.app.test_client(*args, **kwargs)
    
    def test_request_context(self, *args, **kwargs):
        ''' Used in tests.
        '''
        return self.app.test_request_context(*args, **kwargs)
    
    def run(self, *args, **kwargs):
        ''' Used in debug context, typically by run.py.
        '''
        return self.app.run(*args, **kwargs)
    
    def __call__(self, *args, **kwargs):
        ''' Used in WSGI context, typically by gunicorn.
        '''
        return self.app(*args, **kwargs)

def create_app(environ, run_apache):
    app = Flask(__name__, static_folder='static')
    app.secret_key = 'boop'
    app.config['RUNNING_STATE_DIR'] = environ['RUNNING_STATE_DIR']
    app.config['GA_CLIENT_ID'] = environ['GA_CLIENT_ID']
    app.config['GA_CLIENT_SECRET'] = environ['GA_CLIENT_SECRET']
    app.config['GA_REDIRECT_URI'] = environ.get('GA_REDIRECT_URI', 'http://127.0.0.1:5000/callback')
    app.config['WORK_PATH'] = environ.get('WORK_PATH', '.')
    app.config['REPO_PATH'] = environ.get('REPO_PATH', 'sample-site')
    app.config['BROWSERID_URL'] = environ.get('BROWSERID_URL', 'http://127.0.0.1:5000')
    app.config['SINGLE_USER'] = bool(environ.get('SINGLE_USER', False))
    app.config['AUTH_DATA_HREF'] = environ.get('AUTH_DATA_HREF', 'data/authentication.csv')
    app.config['default_branch'] = 'master'

    # attach routes and custom error pages here
    app.register_blueprint(bizarro)

    @app.before_first_request
    def before_first_request():
        '''
        '''
        if app.debug:
            logger.setLevel(DEBUG)
    
    return AppShim(app, run_apache)

from . import views
