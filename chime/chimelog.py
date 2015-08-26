from __future__ import absolute_import
import collections
import json
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
    writeable_dirs = [d for d in dirnames if d and os.access(d, os.W_OK | os.X_OK)]

    if not writeable_dirs:
        raise RuntimeError('Unable to pick a writeable directory name for logs.')

    logfile_path = join(realpath(writeable_dirs[0]), 'app.log')
    handler = handlers.RotatingFileHandler(logfile_path, 'a', 10000000, 10)
    formatter = Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    return handler


ERROR_REPORT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


def make_safe_for_json(object, expression):
    '''
    Given an object and a string expression, evals the expression for the object
    and returns the results, but only if the result can be safely represented
    in JSON. Otherwise, return a grumbly error mesasage.
    '''
    try:
        if '{}' in expression:
            to_eval = expression.format("object")
        else:
            to_eval = "object.{}".format(expression)

        result = eval(to_eval)
        json.dumps(result)
        return result
    except Exception as e:
        # traceback.print_exc(file=sys.stderr)
        Logger.error("failure jsonifying {} for {}".format(expression, object))
        return "SERIALIZATION_ERROR: For '{}': {}".format(expression, e.message)


class ChimeErrorReportFormatter(Formatter):
    '''
    To make production debugging easier, this produces extensive output on failure
    '''
    def __init__(self):
        super(ChimeErrorReportFormatter, self).__init__(ERROR_REPORT_FORMAT)

    def format(self, record):
        result = super(ChimeErrorReportFormatter, self).format(record)
        if hasattr(record, 'request') and record.request:
            result += "\n\nRequest info:\n"
            result += "%s" % record.request
            result += "\n\nFull state = \n"
            result += self.state_as_json(record)
        return result

    def state_as_json(self, record):
        '''
        Given a request object, pull out the interesting things, convert them to JSON,
        and return them as a pretty-print string. If an object is not JSON-serializable,
        record the error message instead of blowing up.
        :param request: werkzeug Request object
        :return: pretty-printed JSON-formatted string
        '''
        result = collections.OrderedDict()
        if hasattr(record, 'id') and record.id:
            result['error-id'] = record.id
        if hasattr(record, 'session') and record.session:
            result['email'] = record.session['email']
        if hasattr(record, 'request') and record.request:
            request = record.request
            for expression in ["method", "url", "referrer", "remote_addr",
                               "content_type", "content_length", "form",
                               "dict({}.headers)", "cookies"]:
                result[expression] = make_safe_for_json(request, expression)
        if hasattr(record, 'session') and record.session:
            result['session'] = dict(record.session)

        try:
            return json.dumps(result, indent=4)
        except Exception as e:
            Logger.error("failure dumping state for error report", e)
            return json.dumps({'error', e.message or "failure in json.dumps"})


class SnsHandler(Handler):
    """Logs to the given Amazon SNS topic; meant for errors."""

    def __init__(self, arn, *args, **kwargs):
        super(SnsHandler, self).__init__(*args, **kwargs)
        self.setFormatter(ChimeErrorReportFormatter())

        self.topic_arn = arn
        region_name = arn.split(':')[3]
        self.sns_connection = self.make_connection(region_name)

    def make_connection(self, region_name):
        return sns.connect_to_region(region_name)

    def emit(self, record):
        subject = u'Production alert: {}: {}'.format(record.levelname, record.name)
        subject = subject.encode('ascii', errors='ignore')[:79]
        self.sns_connection.publish(
            self.topic_arn,
            self.format(record),
            subject=subject
        )
