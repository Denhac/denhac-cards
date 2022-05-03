import threading
import time
from threading import Thread

from sentry_sdk import capture_exception

from card_auto_add.api import WebhookServerApi
from card_auto_add.config import Config
from card_auto_add.windsx.activations import WinDSXCardActivations, CardInfo


class Ingester(object):
    STATUS_SUCCESS = "success"
    STATUS_NOT_DONE = "not_done"

    def __init__(self, config: Config,
                 win_dsx_card_activations: WinDSXCardActivations,
                 server_api: WebhookServerApi):
        self._win_dsx_card_activations = win_dsx_card_activations

        self._request_lock = threading.Lock()
        self._known_requests = set()

        self._server_api = server_api

        self._logger = config.logger

    def start(self):
        thread = Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        while True:
            updates = []
            try:
                updates = self._server_api.get_command_json()
                self._logger.info(f"Got {len(updates)} updates to process")
            except Exception as e:
                self._logger.exception("Failed getting updates", exc_info=True)
                capture_exception(e)

            for update in updates or []:
                self._maybe_handle_request(update)

            time.sleep(60)

    def _maybe_handle_request(self, update):
        with self._request_lock:
            update_id = update["id"]

            if update_id in self._known_requests:
                return

            self._known_requests.add(update_id)

            try:
                self._logger.info(f"Processing update {update_id}")

                method = update["method"]
                card_info = CardInfo(
                    first_name=update["first_name"].replace("'", ""),
                    last_name=update["last_name"].replace("'", ""),
                    company=update["company"],
                    woo_id=update["woo_id"],
                    card=update["card"]
                )

                if method == "enable":
                    self._win_dsx_card_activations.activate(card_info)
                elif method == "disable":
                    self._win_dsx_card_activations.deactivate(card_info)
                else:
                    raise ValueError(f"Method {method} for update {update_id} is unknown")

                self._submit_status(update_id, self.STATUS_SUCCESS)

            except Exception as e:
                self._logger.exception(f"Could not process update {update_id}", exc_info=True)
                capture_exception(e)
                self._submit_status(update_id, self.STATUS_NOT_DONE)

    def _submit_status(self, update_id, status):
        try:
            self._server_api.submit_status(update_id, status)
        except Exception as e:
            capture_exception(e)
