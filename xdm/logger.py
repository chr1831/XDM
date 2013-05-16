import datetime

import json
import logging
import logging.handlers
import inspect
from jsonHelper import MyEncoder
from xdm import common
import traceback


lvlNames = {logging.ERROR:          {'c': '   ERROR', 'p': 'ERROR'},
                logging.WARNING:    {'c': ' WARNING', 'p': 'WARING'},
                logging.INFO:       {'c': '    INFO', 'p': 'INFO'},
                logging.DEBUG:      {'c': '   DEBUG', 'p': 'DEBUG'},
                logging.CRITICAL:   {'c': 'CRITICAL', 'p': 'CRITICAL'}
                }


cLogger = logging.getLogger('XDM.Console')
fLogger = logging.getLogger('XDM.File')
cLogger.setLevel(logging.INFO)
fLogger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.handlers.RotatingFileHandler('xdm.log', maxBytes=10 * 1024 * 1024, backupCount=5)
# create console handler with a higher log level
ch = logging.StreamHandler()

# add the handlers to logger
cLogger.addHandler(ch)
fLogger.addHandler(fh)
""" at some point i want the cherrypy stuff logged
cpLogger = logging.getLogger('cherrypy')
cph = logging.StreamHandler()
formatter = logging.Formatter('%(levelname)s| %(asctime)s: %(message)s ')
cph.setFormatter(formatter)
cpLogger.addHandler(cph)
"""


#http://stackoverflow.com/questions/2203424/python-how-to-retrieve-class-information-from-a-frame-object
def get_class_from_frame(fr):
    args, _, _, value_dict = inspect.getargvalues(fr)
    # we check the first parameter for the frame function is
    # named 'self'
    if len(args) and args[0] == 'self':
        # in that case, 'self' will be referenced in value_dict
        instance = value_dict.get('self', None)
        if instance:
            # return its class
            return getattr(instance, '__class__', None)
    # return None otherwise
    return None


class StructuredMessage(object):
    def __init__(self, lvl, message, calframe, **kwargs):
        self.lvl = lvl
        self.message = message
        self.calframe = calframe
        self.kwargs = kwargs
        self.time = datetime.datetime.now()

    def console(self):
        return '%s| %s: %s' % (lvlNames[self.lvl]['c'], self.time, self.message)

    def __str__(self):
        def _json(time, lvl, message, calframe, kwargs={}):
            return json.dumps({'time': time,
                           'lvl': lvlNames[lvl]['p'],
                            'msg': message,
                            'caller': {'file': calframe[2][1], 'line': calframe[2][2], 'fn': calframe[2][3]},
                            'data': kwargs}, cls=MyEncoder)

        try:
            return _json(self.time, self.lvl, self.message, self.calframe, self.kwargs)
        except TypeError:
            return _json(self.time, self.lvl, self.message, self.calframe)


class LogWrapper():

    def _log(self, lvl, msg, **kwargs):
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 0)
        sm = StructuredMessage(lvl, msg, calframe, **kwargs)
        cLogger.log(lvl, sm.console())
        fLogger.log(lvl, sm)
        if lvl in (logging.WARNING, logging.ERROR):
            callerClass = get_class_from_frame(calframe[2][0])
            #was the error/warning send by a notifier ?
            if callerClass and callerClass.__bases__ and callerClass.__bases__[0] is not None and 'Notifier' == callerClass.__bases__[0].__name__:
                sm = StructuredMessage(logging.ERROR, 'Error while sending an error message with a notifier %s' % callerClass, calframe, **kwargs)
                cLogger.log(lvl, sm.console())
                fLogger.log(lvl, sm)
            else:
                self.debug('sending %s with notifiers' % lvlNames[lvl]['p'])
                for n in common.PM.N:
                    if (n.c.on_warning and lvl == logging.WARNING) or (n.c.on_error and lvl == logging.ERROR):
                        n.sendMessage('%s: %s' % (lvlNames[lvl]['p'], msg))

    def error(self, msg, **kwargs):
        tb = traceback.format_exc()
        msg = '%s\nTraceback:\n%s' % (msg, tb)
        self._log(logging.ERROR, msg, **kwargs)

    def info(self, msg, **kwargs):
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg, **kwargs):
        self._log(logging.WARNING, msg, **kwargs)

    def debug(self, msg, **kwargs):
        self._log(logging.DEBUG, msg, **kwargs)

    def critical(self, msg, **kwargs):
        self._log(logging.CRITICAL, msg, **kwargs)

    def __call__(self, msg, **kwargs):
        self._log(logging.DEBUG, msg, **kwargs)

log = LogWrapper()


__all__ = ['log']
