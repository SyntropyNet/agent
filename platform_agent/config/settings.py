import configparser
import os
from pathlib import Path


class ConfigException(Exception):
    pass


class Config:

    _data = None
    _file = "/etc/noia-agent/config.ini"

    def __init__(self):

        if os.environ.get("NOIA_API_KEY"):
            return

        if os.environ.get('NOIA_USER_API') == 'DOCKER' and not os.environ.get('NOIA_DOCKER_URL'):
            raise ConfigException(f"For Docker API, you must provide NOIA_DOCKER_URL")

        config_file = Path(self._file)
        if not config_file.is_file():
            print(f"Config file was not found in {self._file}")
            raise ConfigException(f"Config file was not found in {self._file}")

        self._data = configparser.ConfigParser()
        self._data.read([self._file])
        for subject in self._data:
            for param in self._data[subject]:
                os.environ[f"NOIA_{param.upper()}"] = self._data[subject][param]


