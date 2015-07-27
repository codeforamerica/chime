from __future__ import absolute_import
from logging import getLogger
Logger = getLogger('chime.error_functions')

from flask import current_app, request
from urllib import quote
from urlparse import urlparse
from os.path import join
from .view_functions import get_repo, strip_index_file, path_display_type, get_value_from_front_matter
from .repo_functions import CONFLICT_ACTION_DELETED

EMAIL_SUBJECT_TEXT = u'Chime Error Report'
EMAIL_BODY_PREFIX = u'\n\n----- Please add any relevant details above this line -----\n\n'

def common_error_template_args(app_config):
    ''' Return dictionary of template arguments common to error pages.
    '''
    return {
        "activities_path": u'/',
        "support_email": app_config.get('SUPPORT_EMAIL_ADDRESS'),
        "support_phone_number": app_config.get('SUPPORT_PHONE_NUMBER')
    }

def make_email_params(message, path=None):
    ''' Construct email params to send to the template.
    '''
    email_message = EMAIL_BODY_PREFIX + message
    if path:
        email_message = u'\n'.join([email_message, u'path: {}'.format(path)])
    return u'?subject={}&body={}'.format(quote(EMAIL_SUBJECT_TEXT), quote(email_message))

def extract_branch_name_from_path(path):
    ''' If the name of a branch that exists in the passed repo is in the passed URL, return it
    '''
    repo = get_repo(flask_app=current_app)
    for branch_name_candidate in path.split('/'):
        if branch_name_candidate in repo.branches:
            return branch_name_candidate

    return None

def summarize_conflict_details(error):
    ''' Make an object that summarizes the files affected by a merge conflict.

        The object looks like this:
        [
            {'edit_path': u'', 'display_type': u'Article', 'actions': u'Deleted', 'title': u'How to Find Us'},
            {'edit_path': u'/tree/34246e3/edit/contact/hours-of-operation/', 'display_type': u'Article', 'actions': u'Edited', 'title': u'Hours of Operation'},
            {'edit_path': u'/tree/34246e3/edit/contact/driving-directions/', 'display_type': u'Article', 'actions': u'Edited', 'title': u'Driving Directions'},
            {'edit_path': u'/tree/34246e3/edit/contact/', 'display_type': u'Category', 'actions': u'Created', 'title': u'Contact'}
        ]
    '''
    repo = get_repo(flask_app=current_app)
    path = urlparse(request.url).path
    # get the branch name (unless it's the default branch)
    branch_name = repo.active_branch.name
    if branch_name == current_app.config['default_branch']:
        branch_name = extract_branch_name_from_path(path)

    conflict_files = error.files()
    summary = []
    for id_file in conflict_files:
        file_description = {'actions': id_file['actions'].title()}
        edit_path = u''
        display_type = u''
        title = u''
        # construct location info if the file wasn't deleted
        if id_file['actions'] != CONFLICT_ACTION_DELETED:
            file_loc = join(repo.working_dir, id_file['path'])
            dir_path = strip_index_file(id_file['path'])
            dir_loc = join(repo.working_dir, dir_path)
            display_type = path_display_type(dir_loc)
            title = get_value_from_front_matter('title', file_loc)
            edit_path = join(u'/tree/{}/edit/'.format(branch_name), dir_path)

        file_description['edit_path'] = edit_path
        file_description['display_type'] = display_type
        file_description['title'] = title

        summary.append(file_description)

    return summary
