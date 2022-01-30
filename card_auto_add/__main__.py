import logging
import time
from logging.handlers import RotatingFileHandler

import sentry_sdk
from splunk_handler import SplunkHandler

from card_auto_add.api import WebhookServerApi
from card_auto_add.card_access_system import CardAccessSystem
from card_auto_add.config import Config
from card_auto_add.loops.active_cards_watcher import ActiveCardsWatcher
from card_auto_add.loops.card_scan_watcher import CardScanWatcher
from card_auto_add.loops.comm_server_watcher import CommServerWatcher
from card_auto_add.loops.dsx_api_watcher import DSXApiWatcher
from card_auto_add.loops.ingester import Ingester
from card_auto_add.loops.processor import Processor

logger = logging.getLogger("card_access")
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Console logging handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# File logging handler
max_bytes = 1 * 1024 * 1024
file_handler = RotatingFileHandler("C:/Users/700 Kalamath/.cards/card_access.log", maxBytes=max_bytes, backupCount=10)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

config = Config(logger)
sentry_sdk.init(config.sentry_dsn)

# Splunk logging handler
splunk = SplunkHandler(
    host=config.splunk_host,
    port=8088,
    token=config.splunk_token,
    index=config.splunk_index,
    source=config.splunk_source,
    sourcetype=config.splunk_sourcetype,
    verify=False
)
splunk.setLevel(logging.INFO)
splunk.setFormatter(formatter)
logger.addHandler(splunk)

cas = CardAccessSystem(config)
server_api = WebhookServerApi(config)

comm_server_watcher = CommServerWatcher(config)
comm_server_watcher.start()

processor = Processor(config, server_api)
processor.start()

ingester = Ingester(config, cas, server_api, processor.command_queue)
ingester.start()

api_watcher = DSXApiWatcher(config)
api_watcher.start()

active_cards_watcher = ActiveCardsWatcher(config, server_api, cas)
active_cards_watcher.start()

card_scan_watcher = CardScanWatcher(config, server_api, cas)
card_scan_watcher.start()

while True:
    time.sleep(60)
