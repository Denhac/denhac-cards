import time

import appdirs
import configparser
import os

from card_auto_add.cas import *
from card_auto_add.dsx_api_watcher import DSXApiWatcher
from card_auto_add.ingester import Ingester

config_path = os.path.join(appdirs.user_config_dir(), ".card_auto_add_config.ini")
config = configparser.ConfigParser()
# TODO Handle File not existing
config.read(config_path)

# TODO Refactor this into a class or something
default_key = 'DEFAULT'
cas = CardAccessSystem(config[default_key]['db_path'])

ingester = Ingester(config[default_key]['ingest_dir'], cas)
ingester.start()

api_watcher = DSXApiWatcher(config[default_key]['windsx_path'])
api_watcher.start()

time.sleep(60)

# db_path = "C:/WinDSX/AcsData.mdb"
# cas = CardAccessSystem(db_path)
#
# ecc = EnableCardCommand(
#     "Justin",
#     "Testelrotte",
#     "DenHac",
#     "06363",
#     cas
# )
#
# dcc = DisableCardCommand("06363", "DenHac", cas)
#
# with open("C:/WinDSX/^IMP01.txt", "w") as fh:
#     ecc.get_dsx_command().write(fh)
