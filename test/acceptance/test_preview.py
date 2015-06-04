# -- coding: utf-8 --

import os
from unittest import main, TestCase
import re
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sys


def browser_version(list):
    return map(lambda v: {"browser_version": v}, list)


def add(key, value, list_of_dicts):
    map(lambda d: d.update({key: value}), list_of_dicts)

    return list_of_dicts


def with_os(os_name, list_of_dicts):
    return add('os', os_name, list_of_dicts)


def browser(browser_name, list_of_dicts):
    return add('browser', browser_name, list_of_dicts)


def os_version(version, list_of_dicts):
    return add('os_version', version, list_of_dicts)


def latest_firefox_and_chrome():
    browsers = []
    browsers.extend(browser('Firefox', browser_version(['35.0'])))
    browsers.extend(browser('Chrome', browser_version(['39.0'])))
    return browsers


def windows_8_targets():
    result = []
    browsers = browser('IE', browser_version(["11.0"]))
    browsers.extend(latest_firefox_and_chrome())
    result.extend(with_os('Windows', os_version('8.1', browsers)))
    return result


def windows_targets():
    # TODO: find out actual targets
    result = []
    result.extend(windows_8_targets())
    return result


def macos_targets():
    # TODO: find out actual targets
    return []


def mobile_targets():
    # TODO: find out actual targets
    return []


def all_targets():
    result = []
    result.extend(macos_targets())
    result.extend(windows_targets())
    result.extend(mobile_targets())
    return add('project', 'chime', result)


BROWSERS_TO_TRY = all_targets()


class TestPreview(TestCase):
    def setUp(self):
        self.email = os.environ['TESTING_EMAIL']
        self.password = os.environ['TESTING_PASSWORD']
        self.live_site = 'http://' + self.load_hosts_file()[0]

    def use_driver(self, capabilities=None):
        """
        :param capabilities: If particular capabilities are requested; they are passed along to BrowserStack.
            Otherwise, a local Firefox is used.
        """
        if capabilities:
            sys.stderr.write("Setting up for browser %s\n" % capabilities)
            self.driver = webdriver.Remote(
                command_executor='http://chimetests1:AxRS34k3vrf7mu9zZ2hE@hub.browserstack.com:80/wd/hub',
                desired_capabilities=capabilities)

        else:
            self.driver = webdriver.Firefox()
            sys.stderr.write("Set up for Firefox\n")
        self.waiter = WebDriverWait(self.driver, timeout=60)

    def load_hosts_file(self):
        with open(os.path.dirname(__file__) + '/../../fabfile/hosts.txt', 'rU') as f:
            hosts = f.read().split(',')
        if len(hosts) == 0:
            raise Exception('Please insert a test host')
        return hosts

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

    def test_create_page_and_preview(self, browsercap=None):
        self.use_driver(browsercap)

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
        self.waiter.until(
            EC.visibility_of_element_located((By.XPATH, "//form[@action='.']/input[@type='text']"))).send_keys('foobar')
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
        self.driver.find_element_by_xpath("//form[@action='/merge']/button[@value='abandon']").click()

    def tearDown(self):
        self.driver.quit()


def safe_name(string):
    return re.sub('\W', '', re.sub('[.]', '_', string.lower()))


def safe_browser_name(d):
    return '_'.join([safe_name(d[n]) for n in ['os', 'os_version', 'browser', 'browser_version']])


def rewrite_for_all_browsers(try_these):
    """
        Magically make test methods for all desired browsers. Note that this method cannot contain
        the word 'test' or nose will decide it is worth running.
    """
    # TODO: find test methods and rewrite them all
    name = 'test_create_page_and_preview'
    m = getattr(TestPreview, name)
    for browser in try_these:
        new_name = "{name}_{browser}".format(name=name, browser=safe_browser_name(browser))
        new_function = lambda i, b=browser: m(i, b)
        new_function.__name__ = new_name
        setattr(TestPreview, new_name, new_function)
    delattr(TestPreview, name)


if BROWSERS_TO_TRY:
    rewrite_for_all_browsers(BROWSERS_TO_TRY)

if __name__ == '__main__':
    main()
