import json
import os
import time
from glob import glob
from queue import Queue
from threading import Thread

import requests

from card_auto_add.cas import CardAccessSystem
from card_auto_add.commands import EnableCardCommand, DisableCardCommand
from card_auto_add.config import Config


class Ingester(object):
    def __init__(self, config: Config, cas: CardAccessSystem, command_queue: Queue):
        self.cas = cas
        self.ingest_dir = config.ingest_dir
        self.api_url = config.ingester_api_url

        self.command_queue = command_queue
        self.requests_from_api_in_queue = set()

        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {config.ingester_api_key}"

    def start(self):
        thread = Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        while True:
            api_files = glob(self.ingest_dir + os.path.sep + "*.json")

            if len(api_files) > 0:
                for api_file in api_files:
                    print("Ingest Found:", api_file)
                    with open(api_file, 'r') as fh:
                        json_data = json.load(fh)

                    command = self._get_dsx_command(json_data)
                    self.command_queue.put(command)

                    os.unlink(api_file)

            try:
                print(f"Making a request to {self.api_url}!")
                response = self.session.get(self.api_url)

                if response.ok:
                    json_response = response.json()

                    if "data" not in json_response:
                        continue  # We should probably log this or something

                    updates = json_response["data"]

                    for update in updates:
                        update_id = update["id"]

                        if update_id not in self.requests_from_api_in_queue:
                            print(f"processing update {update_id}")
                            command = self._get_dsx_command(update)
                            self.command_queue.put(command)
                            self.requests_from_api_in_queue.add(update_id)
                else:
                    print("response was not ok!")
                    print(response.status_code)
                    with open("error.html", "w", encoding="utf-8") as fh:
                        fh.write(str(response.content))

            except Exception as e:
                print(e)
                pass  # Yeah, we should probably do something about this

            time.sleep(60)

    # TODO Validation
    def _get_dsx_command(self, json_data):
        method = json_data["method"]
        if method == "enable":
            return EnableCardCommand(
                json_data["first_name"],
                json_data["last_name"],
                json_data["company"],
                json_data["card"],
                cas=self.cas
            )
        elif method == "disable":
            return DisableCardCommand(
                json_data["card"],
                json_data["company"],
                cas=self.cas
            )
