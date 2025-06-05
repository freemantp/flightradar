import logging
import logging.handlers
from sys import stdout

LOGGER_NAME = "Radar"
def init_logging(logging_conf):

    if logging_conf and logging_conf.syslogHost and logging_conf.syslogFormat:
        SYSLOG_PORT = 514

        syslog_handler = logging.handlers.SysLogHandler(address=(logging_conf.syslogHost, SYSLOG_PORT))
        formater = logging.Formatter(logging_conf.syslogFormat)
        syslog_handler.setFormatter(formater)

        handlers = [syslog_handler]
        if logging_conf.logToConsole:
            console_handler = logging.StreamHandler(stdout)
            console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(console_formatter)
            handlers.append(console_handler)

        logging.basicConfig(level=logging_conf.logLevel, handlers=handlers)
    elif logging_conf and logging_conf.logLevel:
        logging.basicConfig(
            level=logging_conf.logLevel,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )