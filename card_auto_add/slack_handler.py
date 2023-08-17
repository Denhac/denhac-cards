import logging
from datetime import datetime, timezone

import requests


class SlackHandler(logging.Handler):
    def __init__(self, webhook_url):
        super().__init__()
        self._webhook_url = webhook_url

    def emit(self, record: logging.LogRecord) -> None:
        payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{record.msg}"
                    }
                }
            ]
        }

        requests.post(self._webhook_url, json=payload)
