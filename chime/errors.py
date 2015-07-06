from . import chime as app
from flask import current_app, render_template, session
from .view_functions import common_template_args

@app.app_errorhandler(404)
def page_not_found(error):
    kwargs = common_template_args(current_app.config, session)
    return render_template('error_404.html', **kwargs), 404

@app.app_errorhandler(500)
def internal_server_error(error):
    kwargs = common_template_args(current_app.config, session)
    return render_template('error_500.html', **kwargs), 500
