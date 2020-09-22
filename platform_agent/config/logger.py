import logging
import uuid
import json
import os

from logging.config import dictConfig
from pathlib import Path

from platform_agent.lib.ctime import now

logger = logging.getLogger()


class PublishLogToSessionHandler(logging.Handler):
    def __init__(self, session):
        logging.Handler.__init__(self)
        self.session = session
        self.log_id = str(uuid.uuid4())

    def emit(self, record):
        if not self.session.active:
            return
        self.session.send_log(json.dumps({
            'id': self.log_id,
            'executed_at': now(),
            'type': 'LOGGER',
            'data': {'severity': record.levelname, 'message': record.getMessage()}
        }))


def configure_logger():

    log_path = "/var/log/noia-platform"

    log_file = Path(f"{log_path}/agent.log")

    noia_platform_dir = Path(f"{log_path}")

    if not noia_platform_dir.is_dir():
        noia_platform_dir.mkdir()
    if not log_file.is_file():
        log_file.write_text('')

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
                'level': int(os.environ.get('NOIA_LOG_LEVEL', 20))
            },
            'file': {
                'level': 'DEBUG',
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'f',
                'filename': os.environ.get('NOIA_LOG_FILE', "/var/log/noia-platform/agent.log")
            }
        },
        root={
            'handlers': ['h', 'file'],
            'level': int(os.environ.get('NOIA_LOG_LEVEL', 20)),
        },
    )

    dictConfig(logging_config)

    logging.getLogger("pyroute2").setLevel(logging.ERROR)