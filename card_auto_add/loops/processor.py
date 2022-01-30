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
                self._handle_existing_commands()

                self._handle_new_commands()
            except Exception as e:
                capture_exception(e)

    def _handle_existing_commands(self):
        command: Command
        for command, file in list(self._command_to_file.items()):
            # self._logger.info(f"Checking {command.id} file: {file}")
            if not os.path.exists(file):
                del self._command_to_file[command]
                self._logger.info(f"File {file} does not exist! This means it was probably processed")
                command_status = command.status  # status has logging, only call it once
                self._server_api.submit_status(command.id, command_status)
                self._logger.info(f"Status set for {command.id}: {command_status}")

    def _handle_new_commands(self):
        try:
            command: Command = self._command_queue.get(block=False)
        except EmptyQueueException:
            return  # We don't care that the queue is empty

        if command is None:
            return  # We pulled nothing off of the queue

        if command.status == Command.STATUS_SUCCESS:
            # This is already done, just tell the server about it
            self._server_api.submit_status(command.id, Command.STATUS_SUCCESS)
            self._command_queue.task_done()
            return

        if command.status != Command.STATUS_NOT_DONE:
            # This command is in some sort of error state and we do not want to try processing it
            self._server_api.submit_status(command.id, Command.STATUS_NOT_DONE)
            self._command_queue.task_done()
            return

        unused_file_name = self._find_unused_file_name()

        # unused_file_name can be None if all 99 file slots are filled for some reason.
        if unused_file_name is not None:
            self._command_to_file[command] = unused_file_name
            self._logger.info(f"Placing command in: {unused_file_name}")

            dsx_command = command.get_dsx_command()
            if dsx_command is not None:
                with open(unused_file_name, 'w') as fh:
                    dsx_command.write(fh)

            self._command_queue.task_done()

    def _find_unused_file_name(self) -> str:
        for first in range(10):
            for second in range(10):
                path = os.path.join(self._dsx_path, f"^IMP{first}{second}.txt")
                if not os.path.exists(path) and path not in self._command_to_file.values():
                    return path