import time
from threading import Thread

from sentry_sdk import capture_exception

from card_auto_add.api import WebhookServerApi
from card_auto_add.card_access_system import CardAccessSystem, CardHolder
from card_auto_add.config import Config


class ActiveCardsWatcher(object):
    def __init__(self, config: Config,
                 server_api: WebhookServerApi,
                 cas: CardAccessSystem):
        self._config = config
        self._server_api = server_api
        self._cas = cas

    def start(self):
        thread = Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        while True:
            # TODO remove hardcoded value
            active_card_holders = self._cas.get_active_card_holders("denhac")
            active_card_holders_dictionary = list(map(self._holder_to_dictionary, active_card_holders))

            try:
                self._server_api.submit_active_card_holders(active_card_holders_dictionary)
            except Exception as e:
                capture_exception(e)

            time.sleep(8 * 60 * 60)  # 8 hours

    @staticmethod
    def _holder_to_dictionary(card_holder: CardHolder) -> dict:
        return {
            "first_name": card_holder.first_name,
            "last_name": card_holder.last_name,
            "card_num": card_holder.card,
            "company": card_holder.company,
        }
