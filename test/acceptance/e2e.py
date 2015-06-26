# -- coding: utf-8 --

import os
from unittest import main, TestCase
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class TestSelenium(TestCase):
    def setUp(self):
        self.driver = webdriver.Firefox()
        self.waiter = WebDriverWait(self.driver, timeout=60)
        self.email = os.environ['TESTING_EMAIL']
        self.password = os.environ['TESTING_PASSWORD']
        with open(os.path.dirname(__file__) + '/../../fabfile/hosts.txt', 'rU') as f:
            hosts = f.read().split(',')
        if len(hosts) == 0:
            raise Exception('Please insert a test host')
        self.live_site = 'http://' + hosts[0]

    def switch_to_other_window(self, in_handle):
        ''' Switch to the first window found with a handle that's not in_handle
        '''
        def predicate(driver):
            for check_handle in driver.window_handles:
                if check_handle != in_handle:
                    driver.switch_to_window(check_handle)
                    return True

            return False

        return predicate

    def test_create_page_and_preview(self):
        self.driver.get(self.live_site)
        main_window = self.driver.current_window_handle
        self.driver.find_element_by_id('signin').click()

        # wait until the persona window's available and switch to it
        self.waiter.until(self.switch_to_other_window(main_window))

        self.waiter.until(EC.visibility_of_element_located((By.ID, 'authentication_email'))).send_keys(self.email)

        # there are many possible submit buttons on this page
        # so grab the whole row and then click the first button
        submit_row = self.driver.find_element_by_css_selector('.submit.cf.buttonrow')
        submit_row.find_element_by_css_selector('.isStart.isAddressInfo').click()

        # ajax, wait until the element is visible
        self.waiter.until(EC.visibility_of_element_located((By.ID, 'authentication_password'))).send_keys(self.password)

        submit_row.find_element_by_css_selector('.isReturning.isTransitionToSecondary').click()

        # switch back to the main window
        self.driver.switch_to.window(main_window)

        # make sure we're back to Chime
        # self.assertEquals(self.driver.title, 'Tasks | Chime')

        main_url = self.driver.current_url

        # start a new task
        self.waiter.until(EC.visibility_of_element_located((By.NAME, 'task_description'))).send_keys('foobar')
        self.driver.find_element_by_name('task_beneficiary').send_keys('raboof')
        self.driver.find_element_by_class_name('create').click()

        # create a new page
        self.waiter.until(EC.visibility_of_element_located((By.XPATH, "//form[@action='.']/input[@type='text']"))).send_keys('foobar')
        self.driver.find_element_by_xpath("//form[@action='.']/input[@type='submit']").click()

        # add some content to that page
        self.waiter.until(EC.visibility_of_element_located((By.NAME, 'en-title'))).send_keys('foo')
        test_page_content = 'This is some test content.', Keys.RETURN, Keys.RETURN, '# This is a test h1', Keys.RETURN, Keys.RETURN, '> This is a test pull-quote'
        self.driver.find_element_by_id('en-body markItUp').send_keys(*test_page_content)

        # save the page
        self.driver.find_element_by_xpath("//input[@value='Save']").click()

        # preview the page
        self.waiter.until(EC.presence_of_element_located((By.XPATH, "//a[@target='_blank']"))).click()

        # wait until the preview window's available and switch to it
        self.waiter.until(self.switch_to_other_window(main_window))

        self.waiter.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        self.driver.close()
        self.driver.switch_to.window(main_window)

        # go back to the main page
        self.driver.get(main_url)
        # delete our branch
        self.driver.find_element_by_xpath("//form[@action='/update']/button[@value='abandon']").click()

    def tearDown(self):
        self.driver.close()


if __name__ == '__main__':
    main()
