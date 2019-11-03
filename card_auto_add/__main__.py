import time

from card_auto_add.cas import *
from card_auto_add.config import Config
from card_auto_add.dsx_api_watcher import DSXApiWatcher
from card_auto_add.ingester import Ingester

config = Config()

cas = CardAccessSystem(config)

ingester = Ingester(config, cas)
ingester.start()

api_watcher = DSXApiWatcher(config)
api_watcher.start()

time.sleep(60)
