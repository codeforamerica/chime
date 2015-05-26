from __future__ import absolute_import
from logging import getLogger, Handler, Formatter
Logger = getLogger('chime.chimelog')

import os
from logging import handlers
from os.path import join, realpath
from boto import sns

def get_filehandler(dirnames):
    ''' Make a new RotatingFileHandler.
    
        Choose a logfile path based on priority-ordered list of directories.
    '''
    writeable_dirs = [d for d in dirnames if os.access(d, os.W_OK | os.X_OK)]
    
    if not writeable_dirs:
        raise RuntimeError('Unable to pick a writeable directory name')
    
    logfile_path = join(realpath(writeable_dirs[0]), 'app.log')
    handler = handlers.RotatingFileHandler(logfile_path, 'a', 10000000, 10)
    formatter = Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    return handler

class SnsHandler(Handler):
    """Logs to the given Amazon SNS topic; meant for errors."""

    def __init__(self, arn, *args, **kwargs):
        super(SnsHandler, self).__init__(*args, **kwargs)
        self.setFormatter(Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

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
