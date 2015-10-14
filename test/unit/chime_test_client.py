# -- coding: utf-8 --
from __future__ import absolute_import

from bs4 import BeautifulSoup
from urlparse import urlparse, urljoin
from re import search
from chime import repo_functions

class ChimeTestClient:
    ''' Stateful client for Chime Flask test client.
    '''
    def __init__(self, client, test):
        ''' Create a new client, with Flask test client and TestCase instances.
        '''
        self.client = client
        self.test = test

        response = self.client.get('/', follow_redirects=True)
        self.test.assertTrue('Sign in' in response.data)

        self.path, self.soup, self.headers = '/', BeautifulSoup(response.data), response.headers

    def sign_in(self, email):
        ''' Sign in with a given email address.

            Should be used inside an HTTMock that overrides Chime's internal
            call to Persona verifier: https://verifier.login.persona.org/verify
        '''
        response = self.client.post('/sign-in', data={'assertion': email})
        self.test.assertEqual(response.status_code, 200)

        response = self.client.get('/', follow_redirects=True)
        self.test.assertTrue('<!-- template name: articles-list -->' in response.data)

    def reload(self):
        ''' Reload the current path.
        '''
        self.open_link(self.path)

    def open_link(self, url, expected_status_code=200):
        ''' Open a link
        '''
        response = self.client.get(url)
        self.test.assertEqual(response.status_code, expected_status_code)

        if expected_status_code in range(300, 399):
            self.follow_redirect(response, expected_status_code)
        else:
            self.path, self.soup, self.headers = url, BeautifulSoup(response.data), response.headers

    def follow_link(self, href):
        ''' Follow a link after making sure it's present in the page.
        '''
        # Look for the link
        link = self.soup.find(lambda tag: bool(tag.name == 'a' and tag['href'] == href))
        response = self.client.get(link['href'])
        redirect_path = href
        redirect_count = 0
        while response.status_code in range(301, 399) and redirect_count < 3:
            redirect_path = urlparse(response.headers['Location']).path
            response = self.client.get(redirect_path)
            redirect_count = redirect_count + 1

        self.test.assertEqual(response.status_code, 200)

        self.path, self.soup, self.headers = redirect_path, BeautifulSoup(response.data), response.headers

    def follow_redirect(self, response, code):
        ''' Expect and follow a response HTTP redirect.
        '''
        self.test.assertEqual(response.status_code, code, 'Status {} should have been {}'.format(response.status_code, code))

        if code in range(500, 599):
            self.soup, self.headers = BeautifulSoup(response.data), response.headers
        else:
            redirect_path = urlparse(response.headers['Location']).path
            response = self.client.get(redirect_path)
            redirect_count = 0
            while response.status_code in range(301, 399) and redirect_count < 3:
                redirect_path = urlparse(response.headers['Location']).path
                response = self.client.get(redirect_path)
                redirect_count = redirect_count + 1

            self.test.assertEqual(response.status_code, 200)

            self.path, self.soup, self.headers = redirect_path, BeautifulSoup(response.data), response.headers

    def get_branch_name(self):
        ''' Extract and return the branch name from the current soup.
        '''
        # Assumes there is an HTML comment in the format '<!-- branch: 1234567 -->'
        branch_search = search(r'<!-- branch: (.{{{}}}) -->'.format(repo_functions.BRANCH_NAME_LENGTH), unicode(self.soup))
        self.test.assertIsNotNone(branch_search)
        try:
            branch_name = branch_search.group(1)
        except AttributeError:
            raise Exception('No match for generated branch name.')

        return branch_name

    def start_task(self, description):
        ''' Look for form to start a task, submit it.
        '''
        # verify we're on a page that has a start activity link
        start_link = self.soup.find(id='submit-start-activity')
        self.test.assertIsNotNone(start_link, u'No start link on current page')

        # if the modal container's not open, click the start activity link
        if not self.soup.find('div', 'modal-container', 'is-open'):
            self.open_link(start_link['href'])

        # verify that the modal container is now open
        self.test.assertIsNotNone(self.soup.find('div', 'modal-container', 'is-open'), u'No open modal container when expected')

        # find the create task form and submit it
        button = self.soup.find(id='submit-create-activity')
        self.test.assertIsNotNone(button)
        form = button.find_parent('form')
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'') for i in form.find_all(['input', 'button', 'textarea']) if i.has_attr('name')}
        data['task_description'] = description

        start_task_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(start_task_path, data=data)
        if response.status_code == 200:
            self.soup, self.headers = BeautifulSoup(response.data), response.headers
        else:
            self.follow_redirect(response, 303)

    def delete_task(self, branch_name):
        ''' Look for button to delete a task, click it.
        '''
        button = self.soup.select('#{}-delete'.format(branch_name))[0]
        form = button.find_parent('form')

        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'')
                for i in form.find_all(['input', 'button'])}

        delete_task_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(delete_task_path, data=data)
        self.follow_redirect(response, 303)

    def add_category(self, category_name):
        ''' Look for form to add a category, submit it.
        '''
        input = self.soup.find(lambda tag: bool(tag.name == 'input' and tag.get('placeholder') == 'Add topic'))
        form = input.find_parent('form')
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'') for i in form.find_all(['input', 'button'])}
        data[input['name']] = category_name

        add_category_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(add_category_path, data=data)

        # Drop down to where the subcategories are.
        self.follow_redirect(response, 303)

    def add_categories(self, category_list):
        ''' Add many categories.
        '''
        for category_name in category_list:
            self.add_category(category_name)

    def add_subcategory(self, subcategory_name):
        ''' Look for form to add a subcategory, submit it..
        '''
        input = self.soup.find(lambda tag: bool(tag.name == 'input' and tag.get('placeholder') == 'Add subtopic'))
        form = input.find_parent('form')
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'') for i in form.find_all(['input', 'button'])}
        data[input['name']] = subcategory_name

        add_subcategory_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(add_subcategory_path, data=data)

        # Drop down into the subcategory where the articles are.
        self.follow_redirect(response, 303)

    def add_article(self, article_name):
        ''' Look for form to add an article, submit it.
        '''
        # Create a new article.

        input = self.soup.find(lambda tag: bool(tag.name == 'input' and tag.get('placeholder') == 'Add article'))
        form = input.find_parent('form')
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'') for i in form.find_all(['input', 'button'])}
        data[input['name']] = article_name

        add_article_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(add_article_path, data=data)

        # View the new article.
        self.follow_redirect(response, 303)

    def quick_activity_setup(self, description, category_name=u'', subcategory_name=u'', article_name=u''):
        ''' Set up an activity quickly, with topic, sub-topic, and article if requested.
        '''
        # Start a new task
        self.start_task(description=description)
        branch_name = self.get_branch_name()

        # Look for an "other" link that we know about - is it a category?
        self.follow_link(href='/tree/{}/edit/other/'.format(branch_name))

        # Create a new category, subcategory, and article.
        if category_name:
            self.add_category(category_name=category_name)

        if subcategory_name:
            self.add_subcategory(subcategory_name=subcategory_name)

        if article_name:
            self.add_article(article_name=article_name)

        return branch_name

    def submit_edit_article_form(self, title_str, body_str):
        ''' Submit the edit article form and return the response for testing or passing on.

            Note: This will submit the form even if it doesn't have a save/submit button.
        '''
        body = self.soup.find(lambda tag: bool(tag.name == 'textarea' and tag.get('name') == 'en-body'))
        form = body.find_parent('form')
        title = form.find(lambda tag: bool(tag.name == 'input' and tag.get('name') == 'en-title'))
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'')
                for i in form.find_all(['input', 'button', 'textarea'])
                if i.get('type') != 'submit'}

        data[title['name']] = title_str
        data[body['name']] = body_str

        edit_article_path = urlparse(urljoin(self.path, form['action'])).path
        return self.client.post(edit_article_path, data=data)

    def edit_article(self, title_str, body_str):
        ''' Look for form to edit an article, submit it.

            Note: This will submit the form even if it doesn't have a save/submit button.
        '''
        response = self.submit_edit_article_form(title_str, body_str)
        # View the updated article.
        self.follow_redirect(response, 303)

    def edit_article_and_fail(self, title_str, body_str, expected_status_code=400):
        ''' Look for form to edit an article we know to be published, submit it and assert that the sumbission fails.
        '''
        response = self.submit_edit_article_form(title_str, body_str)
        # Assert that the submission failed
        self.test.assertTrue(response.status_code in range(expected_status_code, expected_status_code + 99))

    def preview_article(self, title_str, body_str):
        ''' Look for form to edit an article, preview it.
        '''
        body = self.soup.find(lambda tag: bool(tag.name == 'textarea' and tag.get('name') == 'en-body'))
        form = body.find_parent('form')
        title = form.find(lambda tag: bool(tag.name == 'input' and tag.get('name') == 'en-title'))
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'')
                for i in form.find_all(['input', 'button', 'textarea'])
                if i.get('type') != 'submit' or i.get('value') == 'Preview'}

        data[title['name']] = title_str
        data[body['name']] = body_str

        edit_article_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(edit_article_path, data=data)

        # View the updated article.
        self.follow_redirect(response, 303)

    def follow_modify_category_link(self, title_str):
        ''' Find the (sub-)category edit button in the last soup and follow it.
        '''
        mod_link = self.soup.find(lambda tag: bool(tag.name == 'a' and tag.text == title_str))
        mod_li = mod_link.find_parent('li')
        mod_span = mod_li.find(lambda tag: bool(tag.name == 'span' and 'fa-pencil' in tag.get('class')))
        mod_link = mod_span.find_parent('a')
        self.follow_link(mod_link['href'])

    def delete_category(self):
        ''' Look for the delete button, submit it.
        '''
        body = self.soup.find(lambda tag: bool(tag.name == 'textarea' and tag.get('name') == 'en-description'))
        form = body.find_parent('form')
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'')
                for i in form.find_all(['input', 'button', 'textarea'])
                if i.get('name') != 'save'}

        delete_category_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(delete_category_path, data=data)

        self.follow_redirect(response, 303)

    def delete_article(self, title_str):
        ''' Look for the article delete button, submit it
        '''
        del_link = self.soup.find(lambda tag: bool(tag.name == 'a' and tag.text == title_str))
        del_li = del_link.find_parent('li')
        del_span = del_li.find(lambda tag: bool(tag.name == 'span' and 'fa-trash' in tag.get('class')))
        del_form = del_span.find_parent('form')

        self.test.assertEqual(del_form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'')
                for i in del_form.find_all(['input', 'button', 'textarea'])}

        delete_path = urlparse(urljoin(self.path, del_form['action'])).path
        response = self.client.post(delete_path, data=data)

        self.follow_redirect(response, 303)

    def request_feedback(self, comment_text=u'', task_description=None):
        ''' Look for form to request feedback, submit it.
        '''
        form = self.soup.find('form', {'data-test-id': 'request-feedback-form'})
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'') for i in form.find_all(['input', 'button', 'textarea'])}

        data['comment_text'] = comment_text
        if task_description is not None:
            data['task_description'] = task_description

        save_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(save_path, data=data)

        # View the saved feedback.
        self.follow_redirect(response, 303)

    def rename_activity(self, task_description=None):
        ''' Look for form to rename an activity, submit it.
        '''
        form = self.soup.find('form', {'data-test-id': 'rename-activity-form'})
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'') for i in form.find_all(['input', 'button', 'textarea'])}

        if task_description is not None:
            data['task_description'] = task_description

        save_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(save_path, data=data)

        # View the saved feedback.
        self.follow_redirect(response, 303)

    def leave_feedback(self, comment_text=u''):
        ''' Look for form to leave feedback, submit it.
        '''
        form = self.soup.find('form', {'data-test-id': 'leave-comment-form'})
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'') for i in form.find_all(['input', 'button', 'textarea'])}

        data['comment_text'] = comment_text

        save_feedback_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(save_feedback_path, data=data)

        # View the saved feedback.
        self.follow_redirect(response, 303)

    def approve_activity(self):
        ''' Look for form to approve activity, submit it.
        '''
        button = self.soup.find(lambda tag: bool(tag.name == 'button' and tag.get('value') == 'Endorse Edits'))
        form = button.find_parent('form')
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'')
                for i in form.find_all(['input', 'button', 'textarea'])
                if i.get('value') != 'Leave a Comment'}

        approve_activity_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(approve_activity_path, data=data)

        # View the saved feedback.
        self.follow_redirect(response, 303)

    def publish_activity(self, expected_status_code=303):
        ''' Look for form to publish activity, submit it.
        '''
        button = self.soup.find(lambda tag: bool(tag.name == 'button' and tag.get('value') == 'Publish'))
        form = button.find_parent('form')
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'')
                for i in form.find_all(['input', 'button', 'textarea'])
                if i.get('value') != 'Leave a Comment'}

        publish_activity_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(publish_activity_path, data=data)
        # View the published activity.
        self.follow_redirect(response, expected_status_code)
