import logging
from logging import handlers
import os
from os.path import join, realpath
import boto
from boto import sns


class ChimeFileLoggingHandler(handlers.RotatingFileHandler):
    """Logs to /var/log if available; otherwise to the work dir. """
    @staticmethod
    def log_file(config):
        log_dir = '/var/log/chime'
        if not os.access(log_dir,os.W_OK | os.X_OK):
            log_dir = config['WORK_PATH']
        return join(realpath(log_dir), 'app.log')

    def __init__(self, config):
        super(ChimeFileLoggingHandler, self).__init__(self.log_file(config), 'a', 10000000, 10)
        self.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))


class SnsHandler(logging.Handler):
    """Logs to the given Amazon SNS topic; meant for errors."""

    def __init__(self, arn, *args, **kwargs):
        super(SnsHandler, self).__init__(*args, **kwargs)
        self.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

        self.topic_arn = arn
        region_name = arn.split(':')[3]
        self.sns_connection = self.make_connection(region_name)

    @staticmethod
    def make_connection(region_name):
        return sns.connect_to_region(region_name)

    def emit(self, record):
        subject = u'Production alert: {}: {}'.format(record.levelname, record.name)
        subject = subject.encode('ascii', errors='ignore')[:79]
        self.sns_connection.publish(
            self.topic_arn,
            self.format(record),
            subject=subject
        )
