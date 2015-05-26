import sys
from os.path import abspath, join, dirname

repo_root = abspath(join(dirname(__file__), '..'))
sys.path.insert(0, repo_root)

import unittest
from unittest import TestCase
from chime import SnsHandler
from mock import patch, Mock
from logging import LogRecord, ERROR

FAKE_ZONE = "us-east-1"
FAKE_ARN = "arn:aws:sns:%s:123456789012:prod-alerts" % FAKE_ZONE


class SnsHandlerTestFixture:
    def __enter__(self):
        # noinspection PyUnresolvedReferences
        self.delegate = patch.object(SnsHandler, 'make_connection')
        self.mock_make_connection = self.delegate.__enter__()
        self.mock_connection = Mock()
        self.mock_make_connection.return_value = self.mock_connection
        self.handler = SnsHandler(FAKE_ARN)
        return self

    def publish_main_args(self):
        return self.mock_connection.publish.call_args[0]

    def publish_keyword_args(self):
        return self.mock_connection.publish.call_args[1]

    def published_to_sns_topic(self):
        return self.publish_main_args()[0]

    def published_message(self):
        return self.publish_main_args()[1]

    def published_subject(self):
        return self.publish_keyword_args()['subject']

    def __exit__(self, type, value, traceback):
        self.delegate.__exit__(type, value, traceback)


class TestSnsHandler(TestCase):
    def exc_info_for(self, exception):
        if exception is None:
            return None
        try:
            raise exception
        except Exception:
            return sys.exc_info()

    def fake_record(self, name, level, msg, exception=None):
        record = LogRecord(name, level, '/this/that', 123, msg, None, self.exc_info_for(exception))
        record.created = 1420099200  # 1/1/2015 Pacific
        record.msecs = 0
        return record

    def test_setup(self):
        with SnsHandlerTestFixture() as f:
            f.mock_make_connection.assert_called_with('%s' % FAKE_ZONE)

    def test_basic_use(self):
        with SnsHandlerTestFixture() as f:
            f.handler.emit(self.fake_record('chime', ERROR, "Foo failed"))
            self.assertEqual(f.published_to_sns_topic(), FAKE_ARN)
            self.assertRegexpMatches(f.published_message(), '2015-01-01 00:00:00,000 - chime - ERROR - Foo failed')
            self.assertEqual(f.published_subject(), 'Production alert: ERROR: chime')

    def test_exception_use(self):
        with SnsHandlerTestFixture() as f:
            f.handler.emit(self.fake_record('chime', ERROR, "Foo failed", RuntimeError))
            self.assertRegexpMatches(f.published_message(), '2015-01-01 00:00:00,000 - chime - ERROR - Foo failed')
            self.assertRegexpMatches(f.published_message(), 'Traceback')
            self.assertRegexpMatches(f.published_message(), 'File.*line \d+')


if __name__ == '__main__':
    unittest.main()
