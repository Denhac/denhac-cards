import os
import time
from queue import Queue, Empty as EmptyQueueException
from threading import Thread

from sentry_sdk import capture_exception

from card_auto_add.api import WebhookServerApi
from card_auto_add.commands import Command
from card_auto_add.config import Config


class Processor(object):
    def __init__(self, config: Config,
                 server_api: WebhookServerApi):
        self._dsx_path = config.windsx_path
        self._command_queue = Queue()
        self._command_to_file = {}
        self._server_api = server_api
        self._logger = config.logger

    @property
    def command_queue(self):
        return self._command_queue

    def start(self):
        thread = Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        while True:
            time.sleep(10)

            try:
                command: Command
                for command, file in list(self._command_to_file.items()):
                    # self._logger.info(f"Checking {command.id} file: {file}")
                    if not os.path.exists(file):
                        del self._command_to_file[command]
                        self._logger.info(f"File {file} does not exist!")
                        self._server_api.submit_status(command.id, command.status)
                        self._logger.info(f"Status set for {command.id}: {command.status}")

                try:
                    queued_command: Command = self._command_queue.get(block=False)
                except EmptyQueueException:
                    continue  # We don't care that the queue is empty

                if queued_command is None:
                    continue

                unused_file_name = self._find_unused_file_name()

                if unused_file_name is not None:
                    self._command_to_file[queued_command] = unused_file_name
                    self._logger.info(f"Placing command in: {unused_file_name}")

                    with open(unused_file_name, 'w') as fh:
                        queued_command.get_dsx_command().write(fh)

                    self._command_queue.task_done()
            except Exception as e:
                capture_exception(e)

    def _find_unused_file_name(self) -> str:
        for first in range(10):
            for second in range(10):
                path = os.path.join(self._dsx_path, f"^IMP{first}{second}.txt")
                if not os.path.exists(path) and path not in self._command_to_file.values():
                    return path