# -- coding: utf-8 --
from __future__ import absolute_import

from unittest import main, TestCase
import collections
from tempfile import mkdtemp
from os.path import join, dirname, abspath
from shutil import rmtree, copytree
import random
import logging
import sys
import flask

import werkzeug.datastructures

from chime.chimelog import ChimeErrorReportFormatter, make_safe_for_json

repo_root = abspath(join(dirname(__file__), '..'))
sys.path.insert(0, repo_root)

from httmock import response, HTTMock
from mock import MagicMock

from chime import create_app, repo_functions, google_api_functions

from unit.chime_test_client import ChimeTestClient

#
# LogTestCase and associated classes, for testing logging
# by Antoine Pitrou for Python 3.4, see <https://bugs.python.org/issue18937>
#

_LoggingWatcher = collections.namedtuple("_LoggingWatcher", ["records", "output"])


class _BaseTestCaseContext(object):
    def __init__(self, test_case):
        self.test_case = test_case

    def _raiseFailure(self, standardMsg):
        msg = self.test_case._formatMessage(self.msg, standardMsg)
        raise self.test_case.failureException(msg)


class _CapturingHandler(logging.Handler):
    """
    A logging handler capturing all (raw and formatted) logging output.
    """

    def __init__(self):
        logging.Handler.__init__(self)
        self.watcher = _LoggingWatcher([], [])

    def flush(self):
        pass

    def emit(self, record):
        self.watcher.records.append(record)
        msg = self.format(record)
        self.watcher.output.append(msg)


class _AssertLogsContext(_BaseTestCaseContext):
    """A context manager used to implement TestCase.assertLogs()."""

    LOGGING_FORMAT = "%(levelname)s:%(name)s:%(message)s"

    def __init__(self, test_case, logger_name, level, formatter=None):
        _BaseTestCaseContext.__init__(self, test_case)
        self.logger_name = logger_name
        self.formatter = formatter or logging.Formatter(self.LOGGING_FORMAT)
        if level:
            self.level = logging._levelNames.get(level, level)
        else:
            self.level = logging.INFO
        self.msg = None

    def __enter__(self):
        if isinstance(self.logger_name, logging.Logger):
            logger = self.logger = self.logger_name
        else:
            logger = self.logger = logging.getLogger(self.logger_name)
        handler = _CapturingHandler()
        handler.setFormatter(self.formatter)
        self.watcher = handler.watcher
        self.old_handlers = logger.handlers[:]
        self.old_level = logger.level
        self.old_propagate = logger.propagate
        logger.handlers = [handler]
        logger.setLevel(self.level)
        logger.propagate = False
        return handler.watcher

    def __exit__(self, exc_type, exc_value, tb):
        self.logger.handlers = self.old_handlers
        self.logger.propagate = self.old_propagate
        self.logger.setLevel(self.old_level)
        if exc_type is not None:
            # let unexpected exceptions pass through
            return False
        if len(self.watcher.records) == 0:
            self._raiseFailure(
                "no logs of level {} or higher triggered on {}"
                .format(logging.getLevelName(self.level), self.logger.name))


class LogTestCase(TestCase):
    def assertLogs(self, logger=None, level=None, formatter=None):
        """Fail unless a log message of level *level* or higher is emitted
        on *logger_name* or its children.  If omitted, *level* defaults to
        INFO and *logger* defaults to the root logger.

        This method must be used as a context manager, and will yield
        a recording object with two attributes: `output` and `records`.
        At the end of the context manager, the `output` attribute will
        be a list of the matching formatted log messages and the
        `records` attribute will be a list of the corresponding LogRecord
        objects.

        Example::

            with self.assertLogs('foo', level='INFO') as cm:
                logging.getLogger('foo').info('first message')
                logging.getLogger('foo.bar').error('second message')
            self.assertEqual(cm.output, ['INFO:foo:first message',
                                         'ERROR:foo.bar:second message'])
        """
        return _AssertLogsContext(self, logger, level, formatter)


class TestLogger(LogTestCase):
    def setUp(self):
        # allow logging
        logging.disable(logging.NOTSET)

        self.work_path = mkdtemp(prefix='chime-repo-clones-')

        repo_path = dirname(abspath(__file__)) + '/../test-app.git'
        upstream_repo_dir = mkdtemp(prefix='repo-upstream-', dir=self.work_path)
        upstream_repo_path = join(upstream_repo_dir, 'test-app.git')
        copytree(repo_path, upstream_repo_path)
        self.upstream = repo_functions.ChimeRepo(upstream_repo_path)
        repo_functions.ignore_task_metadata_on_merge(self.upstream)
        self.origin = self.upstream.clone(mkdtemp(prefix='repo-origin-', dir=self.work_path), bare=True)
        repo_functions.ignore_task_metadata_on_merge(self.origin)

        create_app_environ = {}
        create_app_environ['GA_CLIENT_ID'] = 'client_id'
        create_app_environ['GA_CLIENT_SECRET'] = 'meow_secret'

        self.ga_config_dir = mkdtemp(prefix='chime-config-', dir=self.work_path)
        create_app_environ['RUNNING_STATE_DIR'] = self.ga_config_dir
        create_app_environ['WORK_PATH'] = self.work_path
        create_app_environ['REPO_PATH'] = self.origin.working_dir
        create_app_environ['AUTH_DATA_HREF'] = 'http://example.com/auth.csv'
        create_app_environ['BROWSERID_URL'] = 'http://localhost'
        create_app_environ['LIVE_SITE_URL'] = 'http://example.org/'

        self.app = create_app(create_app_environ)

        # write a tmp config file
        config_values = {
            "access_token": "meowser_token",
            "refresh_token": "refresh_meows",
            "profile_id": "12345678",
            "project_domain": ""
        }
        with self.app.app_context():
            google_api_functions.write_ga_config(config_values, self.app.config['RUNNING_STATE_DIR'])

        random.choice = MagicMock(return_value="P")

    def tearDown(self):
        logging.disable(logging.CRITICAL)
        rmtree(self.work_path)

    def auth_csv_example_allowed(self, url, request):
        if url.geturl() == 'http://example.com/auth.csv':
            return response(200, '''Email domain,Organization\nexample.com,Example Org''')

        raise Exception('Asked for unknown URL ' + url.geturl())

    def mock_persona_verify_erica(self, url, request):
        if url.geturl() == 'https://verifier.login.persona.org/verify':
            return response(200, '''{"status": "okay", "email": "erica@example.com"}''')

        else:
            return self.auth_csv_example_allowed(url, request)

    def mock_persona_verify_frances(self, url, request):
        if url.geturl() == 'https://verifier.login.persona.org/verify':
            return response(200, '''{"status": "okay", "email": "frances@example.com"}''')

        else:
            return self.auth_csv_example_allowed(url, request)

    # in TestLogger
    def test_info_logging_404s(self):
        ''' 404 errors log at INFO level
        '''
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in('erica@example.com')

        with self.assertLogs('chime.view_functions', level='INFO') as cm:
            erica.open_link(url='/nothinghere', expected_status_code=404)

        self.assertEqual(cm.output, ['INFO:chime.view_functions:404: Not Found'])

    # in TestLogger
    def test_logging_failure_format(self):
        from chime.view_functions import log_application_errors

        @log_application_errors
        def fail():
            raise ValueError('blow up')

        self.app.app.add_url_rule('/fail', None, fail)
        with HTTMock(self.auth_csv_example_allowed):
            with HTTMock(self.mock_persona_verify_erica):
                erica = ChimeTestClient(self.app.test_client(), self)
                erica.sign_in('erica@example.com')

        with self.assertLogs('chime.view_functions', level='DEBUG', formatter=ChimeErrorReportFormatter()) as cm:
            erica.open_link(url='/fail', expected_status_code=500)

        self.assertEqual(1, len(cm.output))

        self.assertTrue(hasattr(cm.records[0], 'request'))
        self.assertRegexpMatches(cm.output[0], '.*ERROR.*blow up.*')

        self.assertRegexpMatches(cm.output[0], "state =")
        self.assertRegexpMatches(cm.output[0], '"method": "GET"')


class TestChimeErrorReportFormatter(TestCase):
    def test_make_safe_for_json(self):
        class Sample:
            a_property = "prop"

            def a_string(self):
                return "text"

            def a_number(self):
                return 5

            def a_dict(self):
                return {'key': 'value'}

            def an_array(self):
                return [0, 1, 2]

            def a_boolean(self):
                return True

            def headers(self):
                return werkzeug.datastructures.Headers()

            def session(self):
                return flask.sessions.SecureCookieSession({'key': 'value'})

            def fail(self):
                raise ValueError("argh")

        sample = Sample()

        # direct calls
        self.assertEqual("prop", make_safe_for_json(sample, "a_property"))
        self.assertEqual("text", make_safe_for_json(sample, "a_string()"))
        self.assertEqual(5, make_safe_for_json(sample, "a_number()"))
        self.assertEqual("value", make_safe_for_json(sample, "a_dict()['key']"))
        self.assertEqual(1, make_safe_for_json(sample, "an_array()[1]"))
        self.assertEqual(True, make_safe_for_json(sample, "a_boolean()"))
        self.assertEqual('value', make_safe_for_json(sample, "session()['key']"))

        # letting the caller specify where the object goes in the eval
        self.assertEqual({}, make_safe_for_json(sample, "dict({}.headers())"))

        # good failure handling
        self.assertEqual("SERIALIZATION_ERROR: For 'nonexistent': Sample instance has no attribute 'nonexistent'",
                         make_safe_for_json(sample, "nonexistent"))
        self.assertEqual("SERIALIZATION_ERROR: For 'nonexistent()': Sample instance has no attribute 'nonexistent'",
                         make_safe_for_json(sample, "nonexistent()"))
        self.assertEqual("SERIALIZATION_ERROR: For 'a_number()[0]': 'int' object has no attribute '__getitem__'",
                         make_safe_for_json(sample, "a_number()[0]"))
        self.assertRegexpMatches(make_safe_for_json(sample, "fail"),
                                 "^SERIALIZATION_ERROR: For 'fail': .* not JSON serializable$",
                                 )


if __name__ == '__main__':
    main()
