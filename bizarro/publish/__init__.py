from flask import Blueprint, Flask
from logging import getLogger, DEBUG

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
