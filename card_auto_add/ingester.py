import json
import os
import time
from glob import glob
from queue import Queue
from threading import Thread

from card_auto_add.cas import CardAccessSystem
from card_auto_add.commands import EnableCardCommand, DisableCardCommand
from card_auto_add.config import Config
from card_auto_add.webhook_server_api import WebhookServerApi


class Ingester(object):
    def __init__(self, config: Config,
                 cas: CardAccessSystem,
                 server_api: WebhookServerApi,
                 command_queue: Queue):
        self.cas = cas
        self.ingest_dir = config.ingest_dir

        self.command_queue = command_queue
        self.requests_from_api_in_queue = set()

        self.server_api = server_api

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

            updates = self.server_api.get_command_json()
            for update in updates:
                update_id = update["id"]

                if update_id not in self.requests_from_api_in_queue:
                    print(f"processing update {update_id}")
                    command = self._get_dsx_command(update)
                    self.command_queue.put(command)
                    self.requests_from_api_in_queue.add(update_id)

            time.sleep(60)

    # TODO Validation
    def _get_dsx_command(self, json_data):
        method = json_data["method"]
        if method == "enable":
            return EnableCardCommand(
                json_data["id"],
                json_data["first_name"],
                json_data["last_name"],
                json_data["company"],
                json_data["card"],
                cas=self.cas
            )
        elif method == "disable":
            return DisableCardCommand(
                json_data["id"],
                json_data["card"],
                json_data["company"],
                cas=self.cas
            )
