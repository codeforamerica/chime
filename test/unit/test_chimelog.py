import logging
import sys
from os.path import abspath, join, dirname
import time

repo_root = abspath(join(dirname(__file__), '..'))
sys.path.insert(0, repo_root)

import unittest
from unittest import TestCase
from chime import SnsHandler
from mock import Mock
from logging import LogRecord, ERROR

FAKE_ZONE = "us-east-1"
FAKE_ARN = "arn:aws:sns:%s:123456789012:prod-alerts" % FAKE_ZONE


class TestableSnsHandler(SnsHandler):
    # noinspection PyAttributeOutsideInit
    def make_connection(self, region_name):
        self.given_region_name = region_name
        self.mock_connection = Mock()
        return self.mock_connection

    def publish_args(self):
        return self.mock_connection.publish.call_args

    def published_to_sns_topic(self):
        return self.publish_args()[0][0]

    def published_message(self):
        return self.publish_args()[0][1]

    def published_subject(self):
        return self.publish_args()[1]['subject']


class TestSnsHandler(TestCase):

    def setUp(self):
        super(TestSnsHandler, self).setUp()
        self.handler = TestableSnsHandler(FAKE_ARN)
        logging.Formatter.converter = time.gmtime

    def test_setup(self):
        self.assertEqual(self.handler.given_region_name, FAKE_ZONE)

    def test_basic_use(self):
        self.handler.emit(self.fake_record('chime', ERROR, "Foo failed"))
        self.assertEqual(self.handler.published_to_sns_topic(), FAKE_ARN)
        self.assertRegexpMatches(self.handler.published_message(), '2015-01-01 08:00:00,000 - chime - ERROR - Foo failed')
        self.assertEqual(self.handler.published_subject(), 'Production alert: ERROR: chime')

    def test_exception_use(self):
        self.handler.emit(self.fake_record('chime', ERROR, "Foo failed", RuntimeError))
        self.assertRegexpMatches(self.handler.published_message(), '2015-01-01 08:00:00,000 - chime - ERROR - Foo failed')
        self.assertRegexpMatches(self.handler.published_message(), 'Traceback')
        self.assertRegexpMatches(self.handler.published_message(), 'File.*line \d+')

    def fake_record(self, name, level, msg, exception=None):
        record = LogRecord(name, level, '/this/that', 123, msg, None, self.exc_info_for(exception))
        record.created = 1420099200  # 1/1/2015 Pacific
        record.msecs = 0
        return record

    def exc_info_for(self, exception):
        if exception is None:
            return None
        try:
            raise exception
        except Exception:
            return sys.exc_info()

if __name__ == '__main__':
    unittest.main()
