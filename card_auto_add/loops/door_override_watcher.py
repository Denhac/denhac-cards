import json
import time
from dataclasses import dataclass
from threading import Thread, Lock

import requests
from pysherplus.authentication import URLAuthentication
from pysherplus.pusher import PusherHost, Pusher

from card_auto_add.config import Config
from card_auto_add.windsx.door_override import DoorOverride


@dataclass
class Door(object):
    device: int
    duration: int


class DoorOverrideWatcher(object):
    def __init__(self, config: Config):
        self._config = config
        self._logger = config.logger
        self._door_states = {}
        self._update_lock = Lock()

        session = requests.Session()
        session.headers["Authorization"] = f"Bearer {self._config.ingester_api_key}"
        self.auth = URLAuthentication("https://webhooks.denhac.org/broadcasting/auth", session)
        pusher_host = PusherHost.from_url("https://ws.webhooks.denhac.org/app/denhac")

        self._pusher = Pusher(pusher_host, authenticator=self.auth)
        self._pusher["private-doors"]['App\\Events\\DoorControlUpdated'].register(self._on_door_update)

    def start(self):
        thread = Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        self._pusher.connect()

        while True:
            time.sleep(1)
            with self._update_lock:
                for device_id, door in list(self._door_states.items()):
                    door.duration = door.duration - 1

                    if door.duration <= 0:
                        DoorOverride.time_zone(device_id)
                        del self._door_states[device_id]
                        self._logger.info(f"Closed door {device_id}")

    def _on_door_update(self, _,  data):
        data = json.loads(data)
        doors = data['doors']
        duration = data['duration']

        try:
            with self._update_lock:
                for door_update in doors:
                    device_id = door_update["device"]
                    should_open = door_update["open"]

                    if should_open:
                        self._logger.info(f"Opening device {device_id}")
                        DoorOverride.open(device_id)
                    else:
                        self._logger.info(f"Closing device {device_id}")
                        DoorOverride.time_zone(device_id)

                        # If we're closing this door, duration no longer matters, remove it from our list
                        if device_id in self._door_states:
                            del self._door_states[device_id]
                        self._logger.info("Not open, continued")
                        continue

                    if device_id in self._door_states:
                        self._logger.info("We know this device!")
                        door: Door = self._door_states[device_id]
                        door.duration = duration
                    else:
                        self._logger.info("New device, who dis?")
                        door: Door = Door(
                            device=device_id,
                            duration=duration
                        )
                        self._door_states[device_id] = door

        except Exception as ex:
            self._logger.error("Something went wrong in door update", ex)
