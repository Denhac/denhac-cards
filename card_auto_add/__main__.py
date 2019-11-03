import time

from card_auto_add.cas import *
from card_auto_add.config import Config
from card_auto_add.dsx_api_watcher import DSXApiWatcher
from card_auto_add.ingester import Ingester
from card_auto_add.processor import Processor

config = Config()

cas = CardAccessSystem(config)

processor = Processor(config)
processor.start()

ingester = Ingester(config, cas, processor.command_queue)
ingester.start()

api_watcher = DSXApiWatcher(config)
api_watcher.start()

print("Ready to go!")

time.sleep(120)
