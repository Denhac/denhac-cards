import requests
from sentry_sdk import capture_exception

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
            response = self._session.get(self._api_url)

            if response.ok:
                json_response = response.json()

                if "data" not in json_response:
                    return None

                return json_response["data"]

            else:
                self._logger.info("read response was not ok!")
                self._logger.info(response.status_code)
                with open("read_error.html", "w", encoding="utf-8") as fh:
                    fh.write(str(response.content))
                raise Exception(f"Command json returned {response.status_code}")
        except Exception as e:
            self._logger.info(e)
            capture_exception(e)
            pass  # Yeah, we should probably do something about this

    def submit_status(self, command_id, status):
        try:
            url = f"{self._api_url}/{command_id}/status"
            self._logger.info(url)
            response = self._session.post(url, json={
                "status": status
            })

            if response.ok:
                return

            else:
                self._logger.info("status response was not ok!")
                self._logger.info(response.status_code)
                with open("status_error.html", "w", encoding="utf-8") as fh:
                    fh.write(str(response.content))
                raise Exception(f"Submit status returned {response.status_code}")
        except Exception as e:
            self._logger.info(e)
            capture_exception(e)
            pass  # Yeah, we should probably do something about this