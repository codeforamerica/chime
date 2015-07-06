from . import chime as app
from flask import current_app, render_template, session, request
from .view_functions import common_template_args
from .repo_functions import MergeConflict

@app.app_errorhandler(404)
def page_not_found(error):
    kwargs = common_template_args(current_app.config, session)
    kwargs.update({"message": u'No such URL: {}'.format(request.url)})
    return render_template('error_404.html', **kwargs), 404

@app.app_errorhandler(500)
def internal_server_error(error):
    kwargs = common_template_args(current_app.config, session)
    return render_template('error_500.html', **kwargs), 500

@app.app_errorhandler(MergeConflict)
def merge_conflict(error):
    new_files, gone_files, changed_files = error.files()
    kwargs = common_template_args(current_app.config, session)
    kwargs.update(new_files=new_files, gone_files=gone_files, changed_files=changed_files)
    kwargs.update({"message": u'It is a merge conflict, folks'})
    return render_template('error_500.html', **kwargs), 500

@app.app_errorhandler(Exception)
def exception(error):
    kwargs = common_template_args(current_app.config, session)
    kwargs.update({"message": error.args[0]})
    return render_template('error_500.html', **kwargs), 500
