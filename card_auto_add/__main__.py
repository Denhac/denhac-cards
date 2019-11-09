import time

from card_auto_add.cas import *
from card_auto_add.config import Config
from card_auto_add.dsx_api_watcher import DSXApiWatcher
from card_auto_add.ingester import Ingester
from card_auto_add.processor import Processor
from card_auto_add.webhook_server_api import WebhookServerApi

config = Config()

cas = CardAccessSystem(config)
server_api = WebhookServerApi(config)

processor = Processor(config, server_api)
processor.start()

ingester = Ingester(config, cas, server_api, processor.command_queue)
ingester.start()

api_watcher = DSXApiWatcher(config)
api_watcher.start()

print("Ready to go!")

time.sleep(180)
