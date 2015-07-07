from . import chime as app
from flask import current_app, render_template, session, request
from urlparse import urlparse
from .view_functions import common_template_args, get_repo
from .repo_functions import MergeConflict

ERROR_TYPE_404 = u'404'
ERROR_TYPE_500 = u'500'
ERROR_TYPE_MERGE_CONFLICT = u'merge-conflict'
ERROR_TYPE_EXCEPTION = u'exception'

def common_error_template_args(app_config):
    ''' Return dictionary of template arguments common to error pages.
    '''
    return {
        'activities_path': u'/',
        'support_email': app_config.get('SUPPORT_EMAIL_ADDRESS', u'support@chimecms.org'),
        'support_phone_number': app_config.get('SUPPORT_PHONE_NUMBER', u'(415) 794-8729')
    }

@app.app_errorhandler(404)
def page_not_found(error):
    kwargs = common_template_args(current_app.config, session)
    kwargs.update(common_error_template_args(current_app.config))
    # if we can extract a branch name from the URL, construct an edit link for it
    repo = get_repo(current_app)
    path = urlparse(request.url).path
    for branch_name_candidate in path.split('/'):
        if branch_name_candidate in repo.branches:
            kwargs.update({"edit_path": u'/tree/{}/edit/'.format(branch_name_candidate)})
            break

    kwargs.update({"error_type": ERROR_TYPE_404})
    return render_template('error_404.html', **kwargs), 404

@app.app_errorhandler(500)
def internal_server_error(error):
    kwargs = common_template_args(current_app.config, session)
    kwargs.update(common_error_template_args(current_app.config))
    kwargs.update({"error_type": ERROR_TYPE_500})
    return render_template('error_500.html', **kwargs), 500

@app.app_errorhandler(MergeConflict)
def merge_conflict(error):
    new_files, gone_files, changed_files = error.files()
    kwargs = common_template_args(current_app.config, session)
    kwargs.update(common_error_template_args(current_app.config))
    kwargs.update(new_files=new_files, gone_files=gone_files, changed_files=changed_files)
    file_count = len(new_files) + len(gone_files) + len(changed_files)
    message = u'Conflicts were found'
    if file_count == 1:
        message = message + ' in the following file:'
    elif file_count > 1:
        message = message + ' in the following files:'
    else:
        message = message + '.'

    kwargs.update({"message": message})
    kwargs.update({"error_type": ERROR_TYPE_MERGE_CONFLICT})
    return render_template('error_500.html', **kwargs), 500

@app.app_errorhandler(Exception)
def exception(error):
    error_class = type(error).__name__
    kwargs = common_template_args(current_app.config, session)
    kwargs.update(common_error_template_args(current_app.config))
    kwargs.update({"message": error.args[0]})
    kwargs.update({"error_type": ERROR_TYPE_EXCEPTION})
    kwargs.update({"error_class": error_class})
    return render_template('error_500.html', **kwargs), 500
