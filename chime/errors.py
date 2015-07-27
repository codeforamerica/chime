from . import chime as app
from flask import current_app, render_template, session, request
from urlparse import urlparse
from .error_functions import common_error_template_args, make_email_params, summarize_conflict_details, extract_branch_name_from_path
from .view_functions import common_template_args, get_repo
from .repo_functions import MergeConflict

ERROR_TYPE_404 = u'404'
ERROR_TYPE_500 = u'500'
ERROR_TYPE_MERGE_CONFLICT = u'merge-conflict'
ERROR_TYPE_EXCEPTION = u'exception'

@app.app_errorhandler(404)
def page_not_found(error):
    ''' Render a 404 error page
    '''
    repo = get_repo(flask_app=current_app)
    kwargs = common_template_args(current_app.config, session)
    kwargs.update(common_error_template_args(current_app.config))
    # if we can extract a branch name from the path, construct an edit link for it
    path = urlparse(request.url).path
    branch_name = repo.active_branch.name
    if branch_name == current_app.config['default_branch']:
        branch_name = extract_branch_name_from_path(path)

    branch_name = extract_branch_name_from_path(path)
    if branch_name:
        kwargs.update({"edit_path": u'/tree/{}/edit/'.format(branch_name)})

    kwargs.update({"error_type": ERROR_TYPE_404})
    template_message = u'(404) {}'.format(path)
    kwargs.update({"message": template_message})
    kwargs.update({"email_params": make_email_params(message=template_message)})
    return render_template('error_404.html', **kwargs), 404

@app.app_errorhandler(500)
def internal_server_error(error):
    ''' Render a 500 error page
    '''
    kwargs = common_template_args(current_app.config, session)
    kwargs.update(common_error_template_args(current_app.config))
    kwargs.update({"error_type": ERROR_TYPE_500})
    path = urlparse(request.url).path
    template_message = u'(500) {}'.format(path)
    kwargs.update({"message": template_message})
    kwargs.update({"email_params": make_email_params(message=template_message)})
    return render_template('error_500.html', **kwargs), 500

@app.app_errorhandler(MergeConflict)
def merge_conflict(error):
    ''' Render a 500 error page with merge conflict details
    '''
    kwargs = common_template_args(current_app.config, session)
    kwargs.update(common_error_template_args(current_app.config))

    kwargs.update({"conflict_files": summarize_conflict_details(error)})

    kwargs.update({"error_type": ERROR_TYPE_MERGE_CONFLICT})

    message = u'\n'.join([u'{} {}'.format(item['actions'], item['path']) for item in error.files()])
    template_message = u'(MergeConflict)\n{}'.format(message)
    kwargs.update({"message": template_message})
    kwargs.update({"email_params": make_email_params(message=template_message, path=urlparse(request.url).path)})

    return render_template('error_500.html', **kwargs), 500

@app.app_errorhandler(Exception)
def exception(error):
    ''' Render a 500 error page for exceptions not caught elsewhere
    '''
    error_class = type(error).__name__
    kwargs = common_template_args(current_app.config, session)
    kwargs.update(common_error_template_args(current_app.config))

    try:
        error_message = error.args[0]
    except:
        error_message = u''
    kwargs.update({"error_type": ERROR_TYPE_EXCEPTION})
    kwargs.update({"error_class": error_class})
    template_message = u'({}) {}'.format(error_class, error_message)
    kwargs.update({"message": template_message})
    kwargs.update({"email_params": make_email_params(message=template_message, path=urlparse(request.url).path)})
    return render_template('error_500.html', **kwargs), 500
