import os

import appdirs
import configparser


class Config(object):
    def __init__(self, logger):
        self.logger = logger
        # TODO Handle File not existing
        config_path = os.path.join(appdirs.user_config_dir(), ".card_auto_add_config.ini")
        parser = configparser.ConfigParser()
        # TODO Handle File not existing
        parser.read(config_path)
        self._config_default = parser['DEFAULT']

    @property
    def acs_data_db_path(self):
        return self._config_default['acs_data_db_path']

    @property
    def log_db_path(self):
        return self._config_default['log_db_path']

    @property
    def ingest_dir(self):
        return self._config_default['ingest_dir']

    @property
    def windsx_path(self):
        return self._config_default['windsx_path']

    @property
    def no_interaction_delay(self):
        return int(self._config_default['no_interaction_delay'])

    @property
    def ingester_api_key(self):
        return self._config_default['ingester_api_key']

    @property
    def ingester_api_url(self):
        return self._config_default['ingester_api_url']

    @property
    def sentry_dsn(self):
        return self._config_default['sentry_dsn']
