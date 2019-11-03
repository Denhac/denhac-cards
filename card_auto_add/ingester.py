import json
import os
import time
from glob import glob
from threading import Thread

from card_auto_add.cas import CardAccessSystem
from card_auto_add.commands import EnableCardCommand, DisableCardCommand


class Ingester(object):
    def __init__(self, ingest_dir, cas: CardAccessSystem):
        self.cas = cas
        self.ingest_dir = ingest_dir

    def start(self):
        thread = Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        while True:
            time.sleep(1)

            api_files = glob(self.ingest_dir + os.path.sep + "*.json")

            if len(api_files) > 0:
                for api_file in api_files:
                    with open(api_file, 'r') as fh:
                        json_data = json.load(fh)

                    # TODO Write to processor queue
                    command = self._get_dsx_command(json_data)
                    with open("C:/WinDSX/^IMP01.txt", "w") as fh:
                        command.get_dsx_command().write(fh)

                    os.unlink(api_file)

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