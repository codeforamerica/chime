from . import chime as app
from flask import current_app, render_template, session, request
from urlparse import urlparse
from urllib import quote
from .view_functions import common_template_args, get_repo
from .repo_functions import MergeConflict

ERROR_TYPE_404 = u'404'
ERROR_TYPE_500 = u'500'
ERROR_TYPE_MERGE_CONFLICT = u'merge-conflict'
ERROR_TYPE_EXCEPTION = u'exception'
EMAIL_SUBJECT_TEXT = u'Chime Error Report'

def common_error_template_args(app_config):
    ''' Return dictionary of template arguments common to error pages.
    '''
    return {
        "activities_path": u'/',
        "support_email": app_config.get('SUPPORT_EMAIL_ADDRESS', u'support@chimecms.org'),
        "support_phone_number": app_config.get('SUPPORT_PHONE_NUMBER', u'(415) 555-1212')
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
    kwargs.update({"email_params": u'?subject={}'.format(quote(EMAIL_SUBJECT_TEXT))})
    return render_template('error_404.html', **kwargs), 404

@app.app_errorhandler(500)
def internal_server_error(error):
    kwargs = common_template_args(current_app.config, session)
    kwargs.update(common_error_template_args(current_app.config))
    kwargs.update({"error_type": ERROR_TYPE_500})
    kwargs.update({"email_params": u'?subject={}'.format(quote(EMAIL_SUBJECT_TEXT))})
    return render_template('error_500.html', **kwargs), 500

@app.app_errorhandler(MergeConflict)
def merge_conflict(error):
    new_files, gone_files, changed_files = error.files()
    kwargs = common_template_args(current_app.config, session)
    kwargs.update(common_error_template_args(current_app.config))
    kwargs.update(new_files=new_files, gone_files=gone_files, changed_files=changed_files)
    file_count = len(new_files) + len(gone_files) + len(changed_files)

    files_messages = []
    message = u'No files were affected.'
    if len(changed_files):
        files_messages.append(u'Changed: {}'.format(u', '.join([item['path'] for item in changed_files])))
    if len(new_files):
        files_messages.append(u'New: {}'.format(u', '.join([item['path'] for item in new_files])))
    if len(gone_files):
        files_messages.append(u'Gone: {}'.format(u', '.join([item['path'] for item in gone_files])))

    if len(files_messages):
        message = u'Affected files: {}'.format(u'; '.join(files_messages))

    kwargs.update({"file_count": file_count})
    kwargs.update({"error_type": ERROR_TYPE_MERGE_CONFLICT})
    kwargs.update({"message": u'(MergeConflict) {}'.format(message)})
    kwargs.update({"email_params": u'?subject={}&body={}'.format(quote(EMAIL_SUBJECT_TEXT), quote(message))})
    return render_template('error_500.html', **kwargs), 500

@app.app_errorhandler(Exception)
def exception(error):
    error_class = type(error).__name__
    kwargs = common_template_args(current_app.config, session)
    kwargs.update(common_error_template_args(current_app.config))

    try:
        error_message = error.args[0]
    except:
        error_message = u''
    message = u'({}) {}'.format(error_class, error_message)

    kwargs.update({"error_type": ERROR_TYPE_EXCEPTION})
    kwargs.update({"error_class": error_class})
    kwargs.update({"message": message})
    kwargs.update({"email_params": u'?subject={}&body={}'.format(quote(EMAIL_SUBJECT_TEXT), quote(message))})
    return render_template('error_500.html', **kwargs), 500
