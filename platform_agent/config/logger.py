import logging
import uuid
import json
import os

from logging.config import dictConfig
from pathlib import Path

from platform_agent.lib.ctime import now

logger = logging.getLogger()

class CustomLoggerAdapter(logging.LoggerAdapter):

    def process(self, msg, kwargs):
        """
        Process the Logging message and keyword arguments passed in to
        a logging call to insert contextual information. The extra argument
        of the LoggerAdapter will be merged with the extra argument of the
        logging call where the logging call's argument take precedence.
        """
        try:
            kwargs["extra"] = {**self.extra, **kwargs["extra"]}
        except KeyError as e:
            kwargs["extra"] = self.extra
        return msg, kwargs

class PublishLogToSessionHandler(logging.Handler):
    def __init__(self, session):
        logging.Handler.__init__(self)
        self.session = session
        self.log_id = str(uuid.uuid4())

    def emit(self, record):
        if not self.session.active:
            return
        metadata = getattr(record, "metadata", {})
        self.session.send_log(json.dumps({
            'id': self.log_id,
            'executed_at': now(),
            'type': 'LOGGER',
            'data': {'severity': record.levelname, 'message': record.getMessage(), 'metadata': metadata}
        }))


def configure_logger():

    log_path = "/var/log/syntropy-platform"

    log_file = Path(f"{log_path}/agent.log")

    syntropy_platform_dir = Path(f"{log_path}")

    if not syntropy_platform_dir.is_dir():
        syntropy_platform_dir.mkdir()
    if not log_file.is_file():
        log_file.write_text('')

    if os.environ.get('SYNTROPY_LOG_LEVEL', '20').isdigit():
        loglevel = int(os.environ.get('SYNTROPY_LOG_LEVEL', '20'))
    else:
        loglevel = os.environ.get('SYNTROPY_LOG_LEVEL', 'INFO')

    logging_config = dict(
        version=1,
        formatters={
            'f': {
                'format': '%(asctime)-24s %(levelname)-8s %(message)s'
            }
        },
        handlers={
            'h': {
                'class': 'logging.StreamHandler',
                'formatter': 'f',
                'level': loglevel
            },
            'file': {
                'level': 'DEBUG',
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'f',
                'filename': os.environ.get('SYNTROPY_LOG_FILE', "/var/log/syntropy-platform/agent.log")
            }
        },
        root={
            'handlers': ['h', 'file'],
            'level': loglevel,
        },
    )

    dictConfig(logging_config)

    logging.getLogger("pyroute2").setLevel(logging.ERROR)