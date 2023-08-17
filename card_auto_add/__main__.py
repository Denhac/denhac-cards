import atexit
import logging
import signal
import sys
import time
from logging.handlers import RotatingFileHandler

import sentry_sdk

from card_auto_add.api import WebhookServerApi
from card_auto_add.config import Config
from card_auto_add.loops.active_cards_watcher import ActiveCardsWatcher
from card_auto_add.loops.card_scan_watcher import CardScanWatcher
from card_auto_add.loops.comm_server_watcher import CommServerWatcher
from card_auto_add.loops.door_override_watcher import DoorOverrideWatcher
from card_auto_add.loops.ingester import Ingester
from card_auto_add.windsx.activations import WinDSXCardActivations
from card_auto_add.windsx.card_holders import WinDSXActiveCardHolders
from card_auto_add.windsx.card_scan import WinDSXCardScan
from card_auto_add.windsx.database import Database

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

server_api = WebhookServerApi(config)

comm_server_watcher = CommServerWatcher(config)
comm_server_watcher.start()

acs_db = Database(config.acs_data_db_path)
log_db = Database(config.log_db_path)

card_activations = WinDSXCardActivations(config, acs_db, comm_server_watcher)
ingester = Ingester(config, card_activations, server_api)
ingester.start()

card_holders = WinDSXActiveCardHolders(acs_db)
active_cards_watcher = ActiveCardsWatcher(config, server_api, card_holders)
active_cards_watcher.start()

card_scan = WinDSXCardScan(acs_db, log_db)
card_scan_watcher = CardScanWatcher(config, server_api, card_scan)
card_scan_watcher.start()

door_overrides = DoorOverrideWatcher(config)
door_overrides.start()

config.slack_logger.info("denhac card access automation started")


# @atexit.register
# def goodbye():  # TODO Shut down all the threads
#     config.slack_logger.info("denhac card access automation is shutting down")


# When the OS tries to terminate us, make sure we exit cleanly. This ensures goodbye is called as well.
signal.signal(signal.SIGTERM, lambda num, frame: sys.exit(0))

# Main thread runs forever. Theoretically could be avoided if our other threads were non-daemon and were cleaned up
# in goodbye correctly.
while True:
    time.sleep(60)
