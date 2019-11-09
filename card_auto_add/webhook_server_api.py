import requests

from card_auto_add.config import Config


class WebhookServerApi(object):
    def __init__(self, config: Config):
        self._api_url = config.ingester_api_url

        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {config.ingester_api_key}"

    def get_command_json(self):
        try:
            response = self._session.get(self._api_url)

            if response.ok:
                json_response = response.json()

                if "data" not in json_response:
                    return None

                return json_response["data"]

            else:
                print("read response was not ok!")
                print(response.status_code)
                with open("read_error.html", "w", encoding="utf-8") as fh:
                    fh.write(str(response.content))
        except Exception as e:
            print(e)
            pass  # Yeah, we should probably do something about this

    def submit_status(self, command_id, status):
        try:
            url = f"{self._api_url}/{command_id}/status"
            print(url)
            response = self._session.post(url, json={
                "status": status
            })

            if response.ok:
                return

            else:
                print("status response was not ok!")
                print(response.status_code)
                with open("status_error.html", "w", encoding="utf-8") as fh:
                    fh.write(str(response.content))
        except Exception as e:
            print(e)
            pass  # Yeah, we should probably do something about this