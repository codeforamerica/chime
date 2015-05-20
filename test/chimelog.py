import unittest
import sys
from chime import SnsHandler
from mock import patch, Mock
from logging import LogRecord, ERROR, exception

FAKE_ZONE = "us-east-1"
FAKE_ARN = "arn:aws:sns:%s:123456789012:prod-alerts" % FAKE_ZONE


class TestSnsHandler(unittest.TestCase):
    def exc_info_for(self, exception):
        if exception is None:
            return None
        try:
            raise exception
        except Exception:
            return sys.exc_info()


    def fake_record(self, name, level, msg, exception=None):
        record = LogRecord(name, level, '/this/that', 123, msg, None, self.exc_info_for(exception))
        record.created = 1420099200 # 1/1/2015 Pacific
        record.msecs = 0
        return record

    def make_handler(self, mock_connection, mock_make_connection):
        mock_make_connection.return_value = mock_connection
        handler = SnsHandler(FAKE_ARN)
        mock_make_connection.assert_called_with('%s' % FAKE_ZONE)
        return handler

    def test_basic_use(self):
        with patch.object(SnsHandler, 'make_connection') as mock_make_connection:
            mock_connection = Mock()
            handler = self.make_handler(mock_connection, mock_make_connection)

            handler.emit(self.fake_record('chime', ERROR, "Foo failed"))
            publish_args = mock_connection.publish.call_args
            self.assertEqual(publish_args[0][0], FAKE_ARN)
            self.assertRegexpMatches(publish_args[0][1], '2015-01-01 00:00:00,000 - chime - ERROR - Foo failed')
            self.assertDictEqual(publish_args[1], {'subject': 'Production alert: ERROR: chime'})


    def test_exception_use(self):
        with patch.object(SnsHandler, 'make_connection') as mock_make_connection:
            mock_connection = Mock()
            handler = self.make_handler(mock_connection, mock_make_connection)

            handler.emit(self.fake_record('chime', ERROR, "Foo failed", RuntimeError))
            publish_args = mock_connection.publish.call_args
            message = publish_args[0][1]
            self.assertRegexpMatches(message, '2015-01-01 00:00:00,000 - chime - ERROR - Foo failed')
            self.assertRegexpMatches(message, 'Traceback')
            self.assertRegexpMatches(message, 'File.*line \d+')



if __name__ == '__main__':
    unittest.main()
