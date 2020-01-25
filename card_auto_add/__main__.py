import logging
import time

import sentry_sdk

from card_auto_add.api import WebhookServerApi
from card_auto_add.card_access_system import CardAccessSystem
from card_auto_add.config import Config
from card_auto_add.loops.dsx_api_watcher import DSXApiWatcher
from card_auto_add.loops.ingester import Ingester
from card_auto_add.loops.processor import Processor

logger = logging.getLogger("card_access")
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)

file_handler = logging.FileHandler("C:/Users/700 Kalamath/.cards/card_access.log")
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)

config = Config(logger)
sentry_sdk.init(config.sentry_dsn)

cas = CardAccessSystem(config)
server_api = WebhookServerApi(config)

processor = Processor(config, server_api)
processor.start()

ingester = Ingester(config, cas, server_api, processor.command_queue)
ingester.start()

api_watcher = DSXApiWatcher(config)
api_watcher.start()

while True:
    time.sleep(60)
