# -- coding: utf-8 --
import time
import os
from unittest import main, TestCase
from selenium import webdriver
from selenium.webdriver.common.keys import Keys

class TestSelenium(TestCase):
    def setUp(self):
        self.driver = webdriver.Firefox()
        self.email = os.environ.get('TESTING_EMAIL')
        self.password = os.environ.get('TESTING_PASSWORD')
        with open(os.path.dirname(__file__) + '/../../fabfile/hosts.txt', 'rU') as f:
            hosts = f.read().split(',')
        if len(hosts) == 0:
            raise Exception('Please insert a test host')
        self.live_site = 'http://' + hosts[0]

    def test_create_page_and_preview(self):
        driver = self.driver
        driver.get(self.live_site)
        main_window = driver.current_window_handle
        driver.find_element_by_id('signin').click()

        # have to loop because the persona link doesn't have a target
        for window in driver.window_handles:
            if window == main_window:
                pass
            else:
                persona_window = window

        driver.switch_to_window(persona_window)
        email = driver.find_element_by_id('authentication_email')
        email.send_keys(self.email)

        # there are many possible submit buttons on this page
        # so grab the whole row and then click the first button
        submit_row = driver.find_element_by_css_selector('.submit.cf.buttonrow')
        submit_row.find_element_by_css_selector('.isStart.isAddressInfo').click()

        password = driver.find_element_by_id('authentication_password')
        password.send_keys(self.password)

        submit_row.find_element_by_css_selector('.isReturning.isTransitionToSecondary').click()

        # give the server a few seconds to respond
        time.sleep(5)

        # switch back to the main window
        driver.switch_to_window(main_window)

        self.assertEquals(driver.title, 'Tasks | Chime')

        # start a new task
        driver.find_element_by_xpath("//input[@type='text'][@name='branch']").send_keys('foobar')
        driver.find_element_by_xpath("//form[@action='/start']").find_element_by_tag_name('button').click()

        # create a new page
        driver.find_element_by_xpath("//form[@action='.']/input[@type='text']").send_keys('foobar')
        driver.find_element_by_xpath("//form[@action='.']/input[@type='submit']").click()

        # add some content to that page
        driver.find_element_by_name('en-title').send_keys('foo')
        driver.find_element_by_id('en-body markItUp').send_keys(
            'This is some test content.',
            Keys.RETURN, Keys.RETURN,
            '# This is a test h1',
            Keys.RETURN, Keys.RETURN,
            '> This is a test pull-quote'
        )

        # save the page
        driver.find_element_by_xpath("//div[@class='button-group']/input[@value='Save']").click()

        # preview the page
        driver.find_element_by_xpath("//div[@class='button-group']/a[@target='_blank']").click()

    def tearDown(self):
        self.driver.close()

if __name__ == '__main__':
    main()
