# -- coding: utf-8 --
from __future__ import absolute_import

import re
import json
from os.path import join
from collections import Counter
from datetime import datetime
from . import constants, repo_functions

class ChimeActivity:
    ''' A representation of an activity in Chime
    '''
    def __init__(self, repo, branch_name, default_branch_name, actor_email):
        ''' Create a new activity.
        '''
        self.repo = repo
        self.safe_branch = branch_name
        self.default_branch_name = default_branch_name

        task_metadata = repo_functions.get_task_metadata_for_branch(self.repo, self.safe_branch)
        self.author_email = task_metadata['author_email'] if 'author_email' in task_metadata else u''
        self.task_description = task_metadata['task_description'] if 'task_description' in task_metadata else self.safe_branch

        self.review_state, self.review_authorized = repo_functions.get_review_state_and_authorized(
            repo=self.repo, default_branch_name=self.default_branch_name,
            working_branch_name=self.safe_branch, actor_email=actor_email
        )

        self.date_created = self.repo.git.log('--format=%ad', '--date=relative', '--', repo_functions.TASK_METADATA_FILENAME).split('\n')[-1]
        self.date_updated = self.repo.git.log('--format=%ad', '--date=relative').split('\n')[0]

        # the email of the last person who edited the activity
        self.last_edited_email = repo_functions.get_last_edited_email(
            repo=repo, default_branch_name=self.default_branch_name,
            working_branch_name=self.safe_branch
        )

        self.edit_path = u'/tree/{}/edit/'.format(self.safe_branch)
        self.overview_path = u'/tree/{}/'.format(self.safe_branch)
        self.view_path = u'/tree/{}/view/'.format(self.safe_branch)

        # only build history and working state if requested
        self._history = None
        self._history_summary = None
        self._working_state = None

    @property
    def history(self):
        ''' Get the activity history.
        '''
        if not self._history:
            self._history = self._make_history()

        return self._history

    @property
    def history_summary(self):
        ''' Get the activity history summary.
        '''
        if not self._history_summary:
            self._history_summary = self._make_history_summary()

        return self._history_summary

    @property
    def working_state(self):
        ''' Get the activity working state.
        '''
        if not self._working_state:
            self._working_state = repo_functions.get_activity_working_state(self.repo, self.default_branch_name, self.safe_branch)

        return self._working_state

    def _make_history(self):
        ''' Make an easily-parsable history of the activity since it was created.
        '''
        # see <http://git-scm.com/docs/git-log> for placeholders
        log_format = '%x00Name: %an\tEmail: %ae\tDate: %ad\tSubject: %s\tBody: %b%x00'
        log = self.repo.git.log('--format={}'.format(log_format), '--date=relative')

        history = []
        pattern = re.compile(r'\x00Name: (.*?)\tEmail: (.*?)\tDate: (.*?)\tSubject: (.*?)\tBody: (.*?)\x00', re.DOTALL)
        for log_details in pattern.findall(log):
            name, email, date, subject, body = tuple([item for item in log_details])
            commit_category, commit_type, commit_action = repo_functions.get_commit_classification(subject, body)
            log_item = dict(author_name=name, author_email=email, commit_date=date, commit_subject=subject,
                            commit_body=body, commit_category=commit_category, commit_type=commit_type,
                            commit_action=commit_action)
            history.append(log_item)
            # don't get any history beyond the creation of the task metadata file, which is the beginning of the activity
            if re.search(r'{}$'.format(repo_functions.ACTIVITY_CREATED_MESSAGE), subject):
                break

        return history

    def _make_history_summary(self):
        ''' Make an object that summarizes the activity's history.

            The object looks like this:
            {
                'summary': u'3 articles and 1 category have been changed',
                'changes': [
                    {'edit_path': u'', 'display_type': u'Article', 'actions': u'Created, Edited, Deleted', 'title': u'How to Find Us'},
                    {'edit_path': u'/tree/34246e3/edit/contact/hours-of-operation/', 'display_type': u'Article', 'actions': u'Created, Edited', 'title': u'Hours of Operation'},
                    {'edit_path': u'/tree/34246e3/edit/contact/driving-directions/', 'display_type': u'Article', 'actions': u'Created, Edited', 'title': u'Driving Directions'},
                    {'edit_path': u'/tree/34246e3/edit/contact/', 'display_type': u'Category', 'actions': u'Created', 'title': u'Contact'}
                ]
            }
        '''
        # an empty summary object
        history_summary = dict(summary=u'', changes=[])

        ed_lookup = {'create': u'created', 'edit': u'edited', 'delete': u'deleted'}
        change_lookup = {}
        display_types_encountered = []
        # we only care about edits
        edit_history = [action for action in reversed(self.history) if action['commit_category'] == constants.COMMIT_CATEGORY_EDIT]
        for action in edit_history:
            # get the list of changed files from the commit body
            try:
                commit_body = json.loads(action['commit_body'])
            except:
                # could't parse json in the commit body, keep moving
                continue

            # step through the changed files
            for file_change in commit_body:
                # the passed title or the filename if no title is there
                title = file_change['title'] or file_change['file_path'].split('/')[-1]
                # the passed display type or Unknown if no type is there
                display_type = file_change['display_type'].title() or u'Unknown'
                try:
                    action = ed_lookup[file_change['action']].title()
                except:
                    action = file_change['action'].title()
                file_path = file_change['file_path']
                # if the last action is delete, we don't want an edit_path to a file that no longer exists
                edit_path = join(u'/tree/{}/edit/'.format(self.safe_branch), repo_functions.strip_index_file(file_path)) if action != u'Deleted' else u''
                sort_time = datetime.now()
                if file_path in change_lookup:
                    change_lookup[file_path]['sort_time'] = sort_time
                    # add the action to the end of the list if it's different from the last action added
                    if not re.search(r'{}$'.format(action), change_lookup[file_path]['actions']):
                        change_lookup[file_path]['actions'] = change_lookup[file_path]['actions'] + u', {}'.format(action)
                    # add the other variables, which may've changed
                    change_lookup[file_path]['edit_path'] = edit_path
                    change_lookup[file_path]['title'] = title
                    change_lookup[file_path]['display_type'] = display_type
                else:
                    change_lookup[file_path] = dict(title=title, display_type=display_type, actions=action, edit_path=edit_path, sort_time=sort_time)
                    display_types_encountered.append(display_type)

        # flatten and sort the changes
        changes = [change_lookup[item] for item in change_lookup]
        if len(changes):
            changes.sort(key=lambda k: k['sort_time'], reverse=True)
            history_summary['changes'] = changes

            # now construct the summary sentence
            summary_sentence_parts = []
            display_type_tally = Counter(display_types_encountered)
            display_lookup = (
                (display_type_tally[constants.ARTICLE_LAYOUT.title()], unicode(constants.ARTICLE_LAYOUT), unicode(constants.LAYOUT_PLURAL_LOOKUP[constants.ARTICLE_LAYOUT])),
                (display_type_tally[constants.CATEGORY_LAYOUT.title()], unicode(constants.CATEGORY_LAYOUT), unicode(constants.LAYOUT_PLURAL_LOOKUP[constants.CATEGORY_LAYOUT]))
            )
            for tally, singular, plural in display_lookup:
                if tally:
                    summary_sentence_parts.append("{} {}".format(tally, singular if tally == 1 else plural))
            has_have = u''
            has_have = u'have' if len(changes) > 1 else u'has'
            summary_sentence = u'{} {} been changed'.format(u', '.join(summary_sentence_parts[:-2] + [u' and '.join(summary_sentence_parts[-2:])]), has_have)
            history_summary['summary'] = summary_sentence

        return history_summary
