# -- coding: utf-8 --
from __future__ import print_function

import os
from random import randint
from unittest import main
import sys
import time
import urllib
import json

from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from acceptance.browser import Browser

from datetime import datetime

from acceptance.chime_test_case import ChimeTestCase, rewrite_for_all_browsers

# All of this test magic should move somewhere else, but I'm not sure where the somewhere else is yet.
BROWSERS_TO_TRY = Browser.from_string(os.environ.get('BROWSERS_TO_TEST', "").strip().lower())
TEST_REPETITIONS = int(os.environ.get('TEST_REPETITIONS',"1"))
TEST_RETRY_COUNT = int(os.environ.get('TEST_RETRY_COUNT',"1"))

OUTPUT_FILE = os.environ.get('OUTPUT_FILE')

class TestPreview(ChimeTestCase):
    _multiprocess_can_split_ = True

    def setUp(self):
        self.email = self.mutate_email(os.environ['TESTING_EMAIL'])
        self.password = os.environ['TESTING_PASSWORD']
        self.host = self.load_hosts_file()[0]
        self.live_site = 'http://' + self.host
        if OUTPUT_FILE:
            self.browser = None
            self.started = time.time()
            self.status = dict(ok=True, status='started')

    def mutate_email(self, email):
        return email.replace('@', '+' + self.random_digits() + '@')

    def use_driver(self, browser=None):
        """
        :param browser: If particular browser is requested it is passed along to BrowserStack or SauceLabs.
            Otherwise, a local Firefox is used.
        """
        if browser:
            sys.stderr.write("Setting up for browser %s\n" % browser)
            mode = 'browserstack'
            if mode=='browserstack':
                capabilities = browser.as_browserstack_capabilities({'browserstack.debug': True, 'project': 'chime'})

                if browser.browser == 'IE':
                    capabilities['ignoreProtectedModeSettings'] = True
                self.driver = webdriver.Remote(
                    command_executor='http://chimetests1:AxRS34k3vrf7mu9zZ2hE@hub.browserstack.com:80/wd/hub',
                    desired_capabilities=capabilities)
            elif mode=='saucelabs':
                self.driver = webdriver.Remote(
                    command_executor="http://wpietri:42e45709-70f3-4eb8-9ebd-c85be6dfec7a@ondemand.saucelabs.com:80/wd/hub",
                    desired_capabilities=browser.as_saucelabs_capabilities())
            else:
                raise ValueError

        else:
            self.driver = webdriver.Chrome(executable_path='/usr/lib/chromium-browser/chromedriver')
            sys.stderr.write("Set up for Chrome\n")
        self.waiter = WebDriverWait(self.driver, timeout=60)
        self.driver.implicitly_wait(15) # seconds

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



    def test_create_page_and_preview(self, browser=None):
        self.use_driver(browser)
        if OUTPUT_FILE:
            self.browser = ' '.join([browser.os, browser.os_version, browser.browser, browser.browser_version])

        signin_method = "stubby_js"
        if signin_method=='magic_url':
            signin_link = self.live_site + '/sign-in?assertion={}\n'.format(urllib.quote_plus(self.email))
            sys.stderr.write("connecting to {}".format(signin_link))
            self.driver.get(signin_link)
            time.sleep(1)
        elif signin_method=='stubby_js':
            self.driver.get(self.live_site)
            self.driver.execute_script('window.navigator.id.stubby.setPersonaState("{}")'.format(self.email))
        elif signin_method=='stubby_ui':
            self.driver.get(self.live_site)
            main_window = self.driver.current_window_handle
            self.driver.find_element_by_id('signin').click()
            alert = self.driver.switch_to.alert
            alert.send_keys(self.email)
            alert.accept()
            self.driver.switch_to.window(main_window)
        else:
            raise ValueError

        self.driver.get(self.live_site) # this line works around an IE8 issue where quirks mode is sometimes triggered

        # make sure we have logged in
        # self.assertEqual("Current Activities", self.driver.find_element_by_css_selector('h2.current-tasks__title').text)

        main_url = self.driver.current_url

        sys.stderr.write("at url {}\n".format(main_url))

        # start a new task
        task_description = self.marked_string('task_description')
        self.driver.find_element_by_name('task_description').send_keys(task_description)
        self.driver.find_element_by_name('task_beneficiary').send_keys(self.marked_string('task_beneficiary'))
        main_window = self.driver.current_window_handle
        self.driver.find_element_by_class_name('create').click()

        # create a new page
        self.driver.find_element_by_id("create-category-name").send_keys(self.marked_string('category'))
        self.driver.find_element_by_id("create-category-button").click()
        self.driver.find_element_by_id("create-subcategory-name").send_keys(self.marked_string('subcategory'))
        self.driver.find_element_by_id("create-subcategory-button").click()
        article_title = self.marked_string('article')
        self.driver.find_element_by_id("create-article-name").send_keys(article_title)
        self.driver.find_element_by_id("create-article-button").click()

        # add some content to that page
        body_text_marker = self.marked_string('body_text')
        test_page_content = 'This is some test content.', Keys.RETURN, Keys.RETURN, body_text_marker, \
                            Keys.RETURN, Keys.RETURN, '# This is a test h1', Keys.RETURN, Keys.RETURN, '> This is a test pull-quote'
        self.driver.find_element_by_id('en-body').send_keys(*test_page_content)

        # save the page
        self.driver.find_element_by_xpath("//button[@value='Save']").click()

        # wait until we see the flash notification of the save
        self.waiter.until(
            EC.visibility_of_element_located((By.XPATH, "//li[contains(text(),'Saved changes to the {} article!')]".format(article_title)))
        )

        # preview the page
        self.driver.find_element_by_xpath("//button[@value='Preview']").click()

        # assert that the submitted text is on the preview screen
        self.assertIn(body_text_marker, self.driver.find_element_by_class_name('article-content').text)

        # go back to the main page
        self.driver.get(main_url)

        # delete our activity
        # hide the stubby status bar, it can block the delete button
        self.driver.execute_script('window.navigator.id.stubby.widgetElement.style.visibility="hidden";')
        delete_xpath = "//a[contains(text(),'{}')]/../..//button[@value='Delete']".format(task_description)
        self.scrollTo(self.driver.find_element_by_xpath(delete_xpath))

        # click the button when it's clickable
        # need to do this because the position isn't getting updated immediately after scroll
        self.click_button_when_clickable(delete_xpath)

        # wait until the activity is no longer visible in the list
        self.waiter.until(
            EC.invisibility_of_element_located((By.XPATH, "//a[contains(text(),'{}')]".format(task_description)))
        )

        # show the stubby status bar again
        self.driver.execute_script('window.navigator.id.stubby.widgetElement.style.visibility="visible";')

        # verify the flash notification
        # it's possible that the 'saved' flash from the preview and the 'deleted' flash are showing at
        # the same time, so step through all the flashes looking for the 'deleted' one
        flashes = self.driver.find_elements_by_class_name('flash--notice')
        found_flash = False
        for flash in flashes:
            if 'You deleted the "{}" activity'.format(task_description) in flash.text:
                found_flash = True
                break

        self.assertTrue(found_flash)

    def click_button_when_clickable(self, target_xpath, timeout_after=5):
        ''' Try to click the element at the passed xpath until it's successful, or
            time out after the passed number of seconds
        '''
        clicked = False
        timeout = False
        started = datetime.now()
        while not clicked and not timeout:
            try:
                self.driver.find_element_by_xpath(target_xpath).click()
                clicked = True
            except WebDriverException:
                timeout = (datetime.now() - started).seconds > timeout_after
                pass

        if OUTPUT_FILE:
            self.status = dict(ok=True, status='done')

    def random_digits(self, count=6):
        format_as = "{:0" + str(count) + "d}"
        return format_as.format(randint(0, 10 ** count - 1))

    def marked_string(self, base='string'):
        return "{}-{}".format(base, self.random_digits())


    def log_in_to_persona(self, main_window):
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

    def onFailure(self, exception_info):
        if OUTPUT_FILE:
            self.status = dict(ok=False, status='failed', exception=repr(exception_info))
        super(TestPreview, self).onFailure(exception_info)
        self.screenshot()

    def screenshot(self):
        if self.driver:
            self.driver.save_screenshot("at-{}.png".format(time.strftime('%Y%m%d-%H%M%S', time.localtime())))
        else:
            sys.stderr.write("no driver to take screenshot\n")

    def onError(self, exception_info):
        if OUTPUT_FILE:
            self.status = dict(ok=False, status='errored', exception=repr(exception_info))
        super(TestPreview, self).onError(exception_info)
        self.screenshot()

    def tearDown(self):
        if hasattr(self, 'driver') and self.driver:
            self.driver.quit()
        if OUTPUT_FILE:
            elapsed = time.time() - self.started
            self.status.update(dict(elapsed=elapsed, browser=self.browser))
            line = json.dumps(self.status)
            with open(OUTPUT_FILE, 'a') as file:
                print(line, file=file)

    def scrollTo(self, element):
        ActionChains(self.driver).move_to_element(element).perform()
        element.send_keys(Keys.PAGE_DOWN)



if BROWSERS_TO_TRY:
    rewrite_for_all_browsers(TestPreview, BROWSERS_TO_TRY, TEST_REPETITIONS, TEST_RETRY_COUNT)

if __name__ == '__main__':
    main()
