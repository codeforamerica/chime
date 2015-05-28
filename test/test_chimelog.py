import sys
from os.path import abspath, join, dirname
from flask import Request

repo_root = abspath(join(dirname(__file__), '..'))
sys.path.insert(0, repo_root)

import unittest
from unittest import TestCase
from chime import SnsHandler
from mock import Mock
from logging import Logger, ERROR

FAKE_ZONE = "us-east-1"
FAKE_ARN = "arn:aws:sns:%s:123456789012:prod-alerts" % FAKE_ZONE


def fake_request(scheme='http', host='example.org', path='/'):
    return Request({
        'wsgi.url_scheme': scheme,
        'HTTP_HOST': host,
        'SERVER_NAME': host,
        'SERVER_PORT': '80',
        'PATH_INFO': path,
        'SCRIPT_NAME': '',
        'QUERY_STRING': '',
        'SERVER_PROTOCOL': 'HTTP/1.1',
    })


def fake_record(name, level, msg, exception=None, extra=None):
    record = Logger("ignored").makeRecord( name, level, '/this/that', 123, msg, None, exc_info_for(exception), None, extra)
    record.created = 1420099200  # 1/1/2015 Pacific
    record.msecs = 0
    return record


def exc_info_for(exception):
    if exception is None:
        return None
    try:
        raise exception
    except Exception:
        return sys.exc_info()


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

    def test_setup(self):
        self.assertEqual(FAKE_ZONE, self.handler.given_region_name)

    def test_basic_use(self):
        self.handler.emit(fake_record('chime', ERROR, "Foo failed"))
        self.assertEqual(FAKE_ARN, self.handler.published_to_sns_topic())
        self.assertEqual('Production alert: ERROR: chime', self.handler.published_subject())
        self.assertIn('2015-01-01 00:00:00,000 - chime - ERROR - Foo failed', self.handler.published_message())

    def test_exception_use(self):
        self.handler.emit(fake_record('chime', ERROR, "Foo failed", RuntimeError))
        message = self.handler.published_message()
        self.assertIn('2015-01-01 00:00:00,000 - chime - ERROR - Foo failed', message)
        self.assertIn('Traceback', message)
        self.assertRegexpMatches(message, 'File.*line \d+')

    def test_include_request_info(self):
        request = fake_request('http', 'chime.chimecms.org', '/')
        self.handler.emit(fake_record('chime', ERROR, "Foo failed", None, {"request": request}))
        message = self.handler.published_message()
        self.assertIn('GET', message)
        self.assertIn('http://chime.chimecms.org/', message)

    def test_include_request_info_on_exception(self):
        request = fake_request('http', 'chime.chimecms.org', '/')
        self.handler.emit(fake_record('chime', ERROR, "Foo failed", RuntimeError, {"request": request}))
        message = self.handler.published_message()
        self.assertIn('GET', message)
        self.assertIn('http://chime.chimecms.org/', message)


if __name__ == '__main__':
    unittest.main()
