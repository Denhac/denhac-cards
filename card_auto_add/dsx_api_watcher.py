import os
import subprocess
import time
from glob import glob
from threading import Thread
from pywinauto.application import Application, ProcessNotFoundError


class DSXApiWatcher(object):
    def __init__(self, config):
        self.dsx_path = config.windsx_path
        self.db_path = os.path.join(self.dsx_path, "DB.exe")

    def start(self):
        thread = Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        while True:
            time.sleep(1)

            api_files = glob(self.dsx_path + os.path.sep + "^IMP[0-9][0-9].txt")

            if len(api_files) > 0:
                for api in api_files:
                    print("WinDSX Api Found:", api)

                self._login_and_close_windsx()

    def _login_and_close_windsx(self):
        app = self._get_windsx_app()

        # TODO Handle Login window not being open/visible
        app.Login.Edit0.set_edit_text("master")
        app.Login.Edit1.set_edit_text("master")
        app.Login.OK.click()
        time.sleep(10)
        # TODO Handle Database window not being open/visible
        app.Database.close(5)

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
                app = Application().connect(path=self.db_path)
            except ProcessNotFoundError:
                attempts_remaining = TOTAL_ATTEMPTS - attempts
                print(f"Failed to connect to WinDSX, trying to open, {attempts_remaining} attempt(s) remaining...")
                self._open_windsx()

                if attempts == TOTAL_ATTEMPTS:
                    raise

        return app