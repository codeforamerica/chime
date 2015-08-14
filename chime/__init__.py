from __future__ import absolute_import
from logging import getLogger, INFO, DEBUG
import logging
from .chimelog import SnsHandler, get_filehandler

logger = getLogger('chime')

from os import mkdir
from os.path import realpath, join

from flask import Blueprint, Flask

from .httpd import run_apache_forever
from . import constants
from . import view_functions

chime = Blueprint('chime', __name__, template_folder='templates')

class AppShim:

    def __init__(self, app):
        '''
        '''
        self.app = app
        self.config = app.config

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

def run_apache(running_dir):
    '''
    '''
    logger.debug('Starting Apache in {running_dir}'.format(**locals()))

    root = join(realpath(running_dir), 'apache')
    doc_root = join(realpath(running_dir), 'master')
    port = 5001

    try:
        mkdir(root)
        mkdir(doc_root)
    except OSError:
        pass

    return run_apache_forever(doc_root, root, port, False)

def create_app(environ):
    app = Flask(__name__, static_folder='static')
    app.secret_key = 'boop'
    app.logger_name = 'chime-flask'
    app.config.from_object(constants)
    app.config['RUNNING_STATE_DIR'] = environ['RUNNING_STATE_DIR']
    app.config['GA_CLIENT_ID'] = environ['GA_CLIENT_ID']
    app.config['GA_CLIENT_SECRET'] = environ['GA_CLIENT_SECRET']
    app.config['GA_REDIRECT_URI'] = environ.get('GA_REDIRECT_URI', 'http://127.0.0.1:5000/callback')
    app.config['WORK_PATH'] = environ.get('WORK_PATH', '.')
    app.config['LOG_PATH'] = environ.get('LOG_PATH')
    app.config['REPO_PATH'] = environ.get('REPO_PATH', 'sample-site')
    app.config['BROWSERID_URL'] = environ['BROWSERID_URL']
    app.config['SINGLE_USER'] = bool(environ.get('SINGLE_USER', False))
    app.config['AUTH_DATA_HREF'] = environ.get('AUTH_DATA_HREF', view_functions.AUTH_DATA_HREF_DEFAULT)
    app.config['LIVE_SITE_URL'] = environ.get('LIVE_SITE_URL', 'http://127.0.0.1:5001/')
    app.config['PUBLISH_PATH'] = environ.get('PUBLISH_PATH')
    app.config['SNS_ALERTS_TOPIC'] = environ.get('SNS_ALERTS_TOPIC')
    app.config['SUPPORT_EMAIL_ADDRESS'] = environ.get('SUPPORT_EMAIL_ADDRESS')
    app.config['SUPPORT_PHONE_NUMBER'] = environ.get('SUPPORT_PHONE_NUMBER')
    app.config['ACCEPTANCE_TEST_MODE'] = environ.get('ACCEPTANCE_TEST_MODE', False)
    app.config['default_branch'] = 'master'

    # If no live site URL was provided, we'll use Apache to make our own.
    if 'LIVE_SITE_URL' not in environ:
        run_apache(app.config['RUNNING_STATE_DIR'])

    # attach routes and custom error pages here
    app.register_blueprint(chime)

    @app.before_first_request
    def before_first_request():
        directories = app.config['LOG_PATH'], '/var/log/chime', app.config['WORK_PATH']
        logger.addHandler(get_filehandler(directories))
        logger.setLevel(DEBUG if app.debug else INFO)

        if app.config.get('SNS_ALERTS_TOPIC'):
            try:
                sns_handler = SnsHandler(app.config['SNS_ALERTS_TOPIC'])
                sns_handler.setLevel(logging.ERROR)
                logger.addHandler(sns_handler)
            except Exception:
                logger.exception("Unexpected failure setting up SNS logging")

        logger.info("app config before_first_request: %s" % app.config)

    return AppShim(app)

# noinspection PyUnresolvedReferences
from . import views, errors
