import os

import appdirs
import configparser


class Config(object):
    def __init__(self):
        # TODO Handle File not existing
        config_path = os.path.join(appdirs.user_config_dir(), ".card_auto_add_config.ini")
        parser = configparser.ConfigParser()
        # TODO Handle File not existing
        parser.read(config_path)
        self._config_default = parser['DEFAULT']

    @property
    def db_path(self):
        return self._config_default['db_path']

    @property
    def ingest_dir(self):
        return self._config_default['ingest_dir']

    @property
    def windsx_path(self):
        return self._config_default['windsx_path']
