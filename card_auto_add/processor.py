import os
import time
from queue import Queue
from threading import Thread

from card_auto_add.commands import Command
from card_auto_add.config import Config


class Processor(object):
    def __init__(self, config: Config):
        self._dsx_path = config.windsx_path
        self._command_queue = Queue()

    @property
    def command_queue(self):
        return self._command_queue

    def start(self):
        thread = Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        while True:
            time.sleep(1)

            item: Command = self._command_queue.get()

            if item is None:
                continue

            unused_file_name = self._find_unused_file_name()

            if unused_file_name is not None:
                print("Placing command in:", unused_file_name)

                with open(unused_file_name, 'w') as fh:
                    item.get_dsx_command().write(fh)

                self._command_queue.task_done()

    def _find_unused_file_name(self) -> str:
        for first in range(10):
            for second in range(10):
                path = os.path.join(self._dsx_path, f"^IMP{first}{second}.txt")
                if not os.path.exists(path):
                    return path
