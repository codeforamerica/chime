import os
from unittest import TestCase, SkipTest
from unittest.case import _ExpectedFailure, _UnexpectedSuccess
import sys
import warnings
from acceptance.browser import Browser

class ChimeTestCase(TestCase):
    def run(self, result=None):
        """
        This code is copy-pasted from the parent because it's not really set up
        for overriding. This is terrible, but perhaps not as terrible as other
        solutions.

        :param result:
        :return:
        """
        orig_result = result
        if result is None:
            result = self.defaultTestResult()
            startTestRun = getattr(result, 'startTestRun', None)
            if startTestRun is not None:
                startTestRun()

        self._resultForDoCleanups = result
        result.startTest(self)

        testMethod = getattr(self, self._testMethodName)
        if (getattr(self.__class__, "__unittest_skip__", False) or
                getattr(testMethod, "__unittest_skip__", False)):
            # If the class or method was skipped.
            try:
                skip_why = (getattr(self.__class__, '__unittest_skip_why__', '')
                            or getattr(testMethod, '__unittest_skip_why__', ''))
                self._addSkip(result, skip_why)
            finally:
                result.stopTest(self)
            return
        try:
            success = False
            try:
                self.setUp()
            except SkipTest as e:
                self._addSkip(result, str(e))
            except KeyboardInterrupt:
                raise
            except:
                result.addError(self, sys.exc_info())
            else:
                try:
                    testMethod()
                except KeyboardInterrupt:
                    raise
                except self.failureException:
                    result.addFailure(self, sys.exc_info())
                    self.onFailure(sys.exc_info())
                except _ExpectedFailure as e:
                    addExpectedFailure = getattr(result, 'addExpectedFailure', None)
                    if addExpectedFailure is not None:
                        addExpectedFailure(self, e.exc_info)
                    else:
                        warnings.warn("TestResult has no addExpectedFailure method, reporting as passes",
                                      RuntimeWarning)
                        result.addSuccess(self)
                except _UnexpectedSuccess:
                    addUnexpectedSuccess = getattr(result, 'addUnexpectedSuccess', None)
                    if addUnexpectedSuccess is not None:
                        addUnexpectedSuccess(self)
                    else:
                        warnings.warn("TestResult has no addUnexpectedSuccess method, reporting as failures",
                                      RuntimeWarning)
                        result.addFailure(self, sys.exc_info())
                except SkipTest as e:
                    self._addSkip(result, str(e))
                except:
                    result.addError(self, sys.exc_info())
                    self.onError(sys.exc_info())
                else:
                    success = True

                try:
                    self.tearDown()
                except KeyboardInterrupt:
                    raise
                except:
                    result.addError(self, sys.exc_info())
                    success = False

            cleanUpSuccess = self.doCleanups()
            success = success and cleanUpSuccess
            if success:
                result.addSuccess(self)
                self.onSuccess()
        finally:
            result.stopTest(self)
            if orig_result is None:
                stopTestRun = getattr(result, 'stopTestRun', None)
                if stopTestRun is not None:
                    stopTestRun()

    def onSuccess(self):
        pass

    def onError(self, exception_info):
        pass

    def onFailure(self, exception_info):
        pass


def rewrite_for_all_browsers(test_class, browser_list, times=1, retry_count=1):
    """
        Magically make test methods for all desired browsers. Note that this method cannot contain
        the word 'test' or nose will decide it is worth running.
    """
    for name in [n for n in dir(test_class) if n.startswith('test_')]:
        test_method = getattr(test_class, name)
        for count in range(1,times+1):
            for browser in browser_list:
                new_name = "{name}_{browser}".format(name=name, browser=browser.safe_name())
                if times > 1:
                    new_name+= "-{}".format(count)
                if retry_count<=1:
                    new_function = lambda instance, browser_to_use=browser: test_method(instance, browser_to_use)
                else:
                    def auto_retry(instance, test_method, browser_to_use):
                        failure_type, failure_value, failure_traceback = None, None, None
                        for _ in xrange(retry_count):
                            if failure_type:
                                sys.stderr.write("ignoring failure {} for {}\n".format(failure_type, test_method))
                            try:
                                test_method(instance, browser_to_use)
                                return # test success means we return doing nothing
                            except:
                                failure_type, failure_value, failure_traceback = sys.exc_info()
                                instance.tearDown()
                                instance.setUp()
                                pass
                        # reaching here means repeated failure, so let's raise the last failure
                        raise failure_type, failure_value, failure_traceback
                    new_function = lambda instance, browser_to_use=browser: auto_retry(instance, test_method, browser_to_use)

                new_function.__name__ = new_name
                setattr(test_class, new_name, new_function)
        delattr(test_class, name)


