import os
import subprocess
import time
from ctypes import Structure, windll, c_uint, sizeof, byref
from glob import glob
from threading import Thread

from sentry_sdk import capture_exception
from pywinauto.application import Application, ProcessNotFoundError

from card_auto_add.config import Config


class LASTINPUTINFO(Structure):
    _fields_ = [
        ('cbSize', c_uint),
        ('dwTime', c_uint),
    ]


class DSXApiWatcher(object):
    def __init__(self, config: Config):
        self.dsx_path = config.windsx_path
        self._no_interaction_delay = config.no_interaction_delay
        self.db_path = os.path.join(self.dsx_path, "DB.exe")
        self._need_to_run_windsx = False
        self._logger = config.logger

    def start(self):
        thread = Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        # TODO Prevent thrashing
        # TODO Alert if it's been a very long time and we have cards to issue
        while True:
            time.sleep(10)

            try:
                if not self._need_to_run_windsx:
                    api_files = glob(self.dsx_path + os.path.sep + "^IMP[0-9][0-9].txt")

                    if len(api_files) > 0:
                        for api in api_files:
                            self._logger.info(f"WinDSX Api Found: {api}")

                        self._need_to_run_windsx = True

                no_interaction_time = self._current_no_interaction_time
                if self._need_to_run_windsx:
                    if no_interaction_time > self._no_interaction_delay:
                        self._login_and_close_windsx()
                    else:
                        self._logger.info("We need to run DSX, but someone has interacted with the computer too recently")
            except Exception as e:
                self._logger.info("Oh no, something happened!")
                self._logger.info(e)
                capture_exception(e)

    @property
    def _current_no_interaction_time(self):
        last_input_info = LASTINPUTINFO()
        last_input_info.cbSize = sizeof(last_input_info)
        windll.user32.GetLastInputInfo(byref(last_input_info))
        millis = windll.kernel32.GetTickCount() - last_input_info.dwTime
        return millis / 1000.0

    def _login_and_close_windsx(self):
        # TODO Handle being on the lock screen
        self._logger.info("What's an app?")
        app = self._get_windsx_app()
        self._logger.info(f"Woot the app returned: {app}")

        for window in app.windows():
            self._logger.info(window)

        self._logger.info(f"Them windows printed: {len(app.windows())}")

        # TODO Handle Login window not being open/visible
        app.Login.Edit0.set_edit_text("master")
        app.Login.Edit1.set_edit_text("master")
        app.Login.OK.click()
        time.sleep(10)
        # TODO Handle Database window not being open/visible
        app.Database.close(5)

        self._need_to_run_windsx = False

    def _open_windsx(self):
        subprocess.Popen([self.db_path])
        time.sleep(5)

    def _get_windsx_app(self):
        app = None
        attempts = 0
        TOTAL_ATTEMPTS = 5
        while app is None:
            try:
                attempts = attempts + 1
                self._logger.info("Trying to get an app")
                app = Application().connect(path=self.db_path)
                self._logger.info("Got an app")
            except ProcessNotFoundError:
                attempts_remaining = TOTAL_ATTEMPTS - attempts
                self._logger.info(
                    f"Failed to connect to WinDSX, trying to open, {attempts_remaining} attempt(s) remaining...")
                self._open_windsx()

                if attempts == TOTAL_ATTEMPTS:
                    raise

        return app
