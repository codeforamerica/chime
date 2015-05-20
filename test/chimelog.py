import unittest
from chime import SnsHandler
from mock import patch, Mock
from logging import LogRecord, ERROR

FAKE_ZONE = "us-east-1"
FAKE_ARN = "arn:aws:sns:%s:123456789012:prod-alerts" % FAKE_ZONE


class TestSnsHandler(unittest.TestCase):
    def fake_record(self, name, level, msg):
        record = LogRecord(name, level, '/this/that', 123, msg, None, None)
        record.created = 1420099200 # 1/1/2015 Pacific
        record.msecs = 0
        return record

    def test_basic_use(self):
        with patch.object(SnsHandler, 'make_connection') as mock_make_connection:
            mock_connection = Mock()
            mock_make_connection.return_value = mock_connection
            handler = SnsHandler(FAKE_ARN)
            mock_make_connection.assert_called_with('%s' % FAKE_ZONE)

            handler.emit(self.fake_record('chime', ERROR, "Foo failed"))
            publish_args = mock_connection.publish.call_args
            self.assertEqual(publish_args[0][0], FAKE_ARN)
            self.assertRegexpMatches(publish_args[0][1], '2015-01-01 00:00:00,000 - chime - ERROR - Foo failed')
            self.assertDictEqual(publish_args[1], {'subject': 'Production alert: ERROR: chime'})

    # TODO: test exception output



if __name__ == '__main__':
    unittest.main()
