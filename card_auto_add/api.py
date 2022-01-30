import requests
from sentry_sdk import capture_exception

from card_auto_add.card_access_system import CardScan
from card_auto_add.config import Config


class WebhookServerApi(object):
    def __init__(self, config: Config):
        self._api_url = config.ingester_api_url

        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {config.ingester_api_key}"
        self._session.headers["Accept"] = "application/json"
        self._logger = config.logger

    def get_command_json(self):
        try:
            response = self._session.get(f"{self._api_url}/card_updates")

            if response.ok:
                json_response = response.json()

                if "data" not in json_response:
                    return None

                return json_response["data"]

            else:
                self._logger.info(f"read response from API server was {response.status_code} which is not ok!")
                with open("read_error.html", "w", encoding="utf-8") as fh:
                    fh.write(str(response.content))
                raise Exception(f"Command json returned {response.status_code}")
        except Exception as e:
            self._logger.info(e)
            capture_exception(e)
            pass  # Yeah, we should probably do something about this

    def submit_status(self, command_id, status):
        try:
            url = f"{self._api_url}/card_updates/{command_id}/status"
            response = self._session.post(url, json={
                "status": status
            })

            if response.ok:
                return

            else:
                self._logger.info(f"status response from API server was {response.status_code} which is not ok!")
                with open("status_error.html", "w", encoding="utf-8") as fh:
                    fh.write(str(response.content))
                raise Exception(f"Submit status returned {response.status_code}")
        except Exception as e:
            self._logger.info(e)
            capture_exception(e)
            pass  # Yeah, we should probably do something about this

    def submit_active_card_holders(self, active_card_holders):
        try:
            url = f"{self._api_url}/active_card_holders"
            self._logger.info("Posting active card holders")
            response = self._session.post(url, json={
                "card_holders": active_card_holders
            })

            if response.ok:
                return
            else:
                self._logger.info(f"status response from API server was {response.status_code} which is not ok!")
                raise Exception(f"Submit status returned {response.status_code}")
        except Exception as e:
            self._logger.info(e)
            capture_exception(e)
            pass  # Yeah, we should probably do something about this

    def submit_card_scan_event(self, card_scan: CardScan):
        try:
            url = f"{self._api_url}/events/card_scanned"
            self._logger.info(url)
            response = self._session.post(url, json={
                "first_name": card_scan.first_name,
                "last_name": card_scan.last_name,
                "card_num": card_scan.card,
                "scan_time": card_scan.scan_time.isoformat(),
                "access_allowed": card_scan.access_allowed,
                "device": card_scan.device,
            })

            if response.ok:
                return
            else:
                self._logger.info(f"card scanned response from API server was {response.status_code} which is not ok!")
                raise Exception(f"Submit status returned {response.status_code}")
        except Exception as e:
            self._logger.info(e)
            capture_exception(e)
            pass  # Yeah, we should probably do something about this