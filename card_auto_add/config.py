import logging
import os
from logging import Logger
from typing import Optional, Callable, TypeVar, Generic

import appdirs
import configparser

from card_auto_add.slack_handler import SlackHandler

T = TypeVar('T')


class ConfigProperty(Generic[T]):
    def __init__(self, section, key, transform: Optional[Callable[[str], T]] = None):
        self._section = section
        self._key = key
        if transform is None:
            def transform(x):
                return x
        self._transform = transform

    def __get__(self, instance, owner) -> T:
        return self._transform(instance[self._section][self._key])


class Config(object):
    def __init__(self, logger: Logger):
        self.logger: Logger = logger
        # TODO Handle File not existing
        config_path = os.path.join(appdirs.user_config_dir(), ".card_auto_add_config.ini")
        parser = configparser.ConfigParser()
        parser.read(config_path)
        self._config = parser

        # Slack specific logging
        slack_formatter = logging.Formatter('%(levelname)s - %(message)s')

        self.slack_logger = logging.getLogger("slack_card_access")
        self.slack_logger.setLevel(logging.INFO)

        slack_handler = SlackHandler(self.slack_log_url)
        slack_handler.setLevel(logging.INFO)
        slack_handler.setFormatter(slack_formatter)
        self.slack_logger.addHandler(slack_handler)

    def __getitem__(self, item):
        return self._config[item]

    acs_data_db_path = ConfigProperty('WINDSX', 'acs_data_db_path')
    log_db_path = ConfigProperty('WINDSX', 'log_db_path')
    windsx_path = ConfigProperty('WINDSX', 'root_path')
    windsx_username = ConfigProperty('WINDSX', 'username')
    windsx_password = ConfigProperty('WINDSX', 'password')
    windsx_acl = ConfigProperty('WINDSX', 'acl')

    ingest_path = ConfigProperty('INGEST', 'root_path')
    no_interaction_delay = ConfigProperty('INGEST', 'no_interaction_delay', transform=lambda x: int(x))
    ingester_api_key = ConfigProperty('INGEST', 'api_key')
    ingester_api_url = ConfigProperty('INGEST', 'api_url')

    sentry_dsn = ConfigProperty('SENTRY', 'dsn')

    slack_log_url = ConfigProperty('SLACK', 'webhook_url')

    dsxpi_host = ConfigProperty('DSXPI', 'host')
    dsxpi_signing_secret = ConfigProperty('DSXPI', 'signing_secret')
