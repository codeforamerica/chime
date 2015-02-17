from os import environ
from flask import Flask, current_app
from logging import getLogger, DEBUG

from . import repo_functions, edit_functions, jekyll_functions

def create_app():
    app = Flask(__name__)
    app.secret_key = 'boop'
    app.config['WORK_PATH'] = environ.get('WORK_PATH', '.')
    app.config['REPO_PATH'] = environ.get('REPO_PATH', 'sample-site')
    app.config['BROWSERID_URL'] = environ.get('BROWSERID_URL', 'http://127.0.0.1:5000')
    app.config['SINGLE_USER'] = bool(environ.get('SINGLE_USER', False))
    app.config['default_branch'] = 'master'

    # attach routes and custom error pages here

    return app

# @app.before_first_request
# def before_first_request():
#     '''
#     '''
#     if current_app.debug:
#         getLogger('bizarro').setLevel(DEBUG)

from . import views

