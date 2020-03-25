import time
from threading import Thread
from typing import List

from sentry_sdk import capture_exception

from card_auto_add.api import WebhookServerApi
from card_auto_add.card_access_system import CardAccessSystem, CardHolder, CardScan
from card_auto_add.config import Config


class CardScanWatcher(object):
    def __init__(self, config: Config,
                 server_api: WebhookServerApi,
                 cas: CardAccessSystem):
        self._config = config
        self._server_api = server_api
        self._cas = cas
        self._known_card_scans = {}

    def start(self):
        thread = Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        while True:
            # TODO remove hardcoded value
            card_scans: List[CardScan] = self._cas.get_card_scans("denhac")

            for scan in card_scans:
                if scan.name_id not in self._known_card_scans:
                    self._known_card_scans[scan.name_id] = {}
                    continue

                scans_for_name = self._known_card_scans[scan.name_id]
                if scan.card not in scans_for_name:
                    # We don't care about previous scans or if the card was just added to the system
                    scans_for_name[scan.card] = scan
                    continue

                previous_scan: CardScan = scans_for_name[scan.card]

                if previous_scan.scan_time != scan.scan_time:
                    scans_for_name[scan.card] = scan

                    try:
                        self._server_api.submit_card_scan_event(scan)
                    except Exception as e:
                        capture_exception(e)

            time.sleep(60)  # 1 minute
