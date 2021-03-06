import time
from datetime import datetime
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
        self._last_scan_time = datetime.now()

    def start(self):
        thread = Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        while True:
            # TODO remove hardcoded value
            card_scans: List[CardScan] = self._cas.get_scan_events_since(self._last_scan_time)

            for scan in card_scans:
                self._last_scan_time = max(self._last_scan_time, scan.scan_time)

                try:
                    self._server_api.submit_card_scan_event(scan)
                except Exception as e:
                    capture_exception(e)

            time.sleep(60)  # 1 minute
