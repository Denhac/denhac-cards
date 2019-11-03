import subprocess
import time
from glob import glob
from threading import Thread
from pywinauto.application import Application, ProcessNotFoundError


class DSXApiWatcher(object):
    def __init__(self, dsx_path):
        self.dsx_path = dsx_path

    def start(self):
        thread = Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        while True:
            time.sleep(10)

            api_files = glob(self.dsx_path + "^IMP[0-9]{2}.txt")

            if len(api_files) > 0:
                for api in api_files:
                    print("Found:", api)