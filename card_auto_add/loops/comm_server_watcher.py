import os
import signal
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
                    self._config.slack_logger.info("CS.exe was not running, so we will attempt to restart.")
                    self._start_comm_server()
            except BaseException as ex:
                capture_exception(ex)

            time.sleep(60)  # 1 minute

    def restart_comm_server(self):
        self._config.slack_logger.info("Attempting to restart Comm Server")
        self._kill_comm_server()

        self._config.slack_logger.info("Starting Comm Server")
        self._start_comm_server()

    def _kill_comm_server(self):
        cs_processes = [p for p in psutil.process_iter() if p.name() == 'cs.exe']

        if len(cs_processes) == 0:
            self._config.slack_logger.info("Could not find CS.exe process to kill")
            return

        pid = cs_processes[0].pid

        os.kill(pid, signal.SIGTERM)

        self._config.slack_logger.info("Killed CS.exe process")

    def _start_comm_server(self):
        subprocess.Popen(os.path.join(self._config.windsx_path, 'CS.exe'))
