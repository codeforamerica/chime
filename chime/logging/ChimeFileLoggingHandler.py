from __future__ import absolute_import
import os
from os.path import join, realpath

import logging
from logging import handlers


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

