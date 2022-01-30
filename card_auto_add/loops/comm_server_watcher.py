import os
import subprocess
import time
from threading import Thread

import psutil
from sentry_sdk import capture_exception

from card_auto_add.config import Config


class CommServerWatcher(object):
    def __init__(self, config: Config):
        self._config = config

    def start(self):
        thread = Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        while True:
            try:
                cs_processes = [p for p in psutil.process_iter() if p.name() == 'cs.exe']

                if len(cs_processes) == 0:
                    subprocess.Popen(os.path.join(self._config.windsx_path, 'CS.exe'))
            except BaseException as ex:
                capture_exception(ex)

            time.sleep(60)  # 1 minute
