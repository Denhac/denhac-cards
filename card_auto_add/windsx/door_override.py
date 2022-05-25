import socket
import time
from enum import Enum


class DoorState(Enum):
    OPEN = 1
    SECURE = 2
    TIME_ZONE = 3


class DoorOverride(object):
    _host = "127.0.0.1"
    _port = 22223

    @classmethod
    def set_state(cls, door_num: int, door_state: DoorState):
        # Sometimes the first one doesn't trigger, and we don't know why so do it twice?
        cls._set_state_internal(door_num, door_state)
        cls._set_state_internal(door_num, door_state)

    @classmethod
    def _set_state_internal(cls, door_num, door_state):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect((cls._host, cls._port))
            s.sendall(f"6 80 3 {door_num} 0 {door_state.value} 3830202337 11 *Comm Server\r\n".encode('ascii'))
            s.sendall(b"\r\n")
            s.shutdown(socket.SHUT_WR)
            s.recv(1024)  # Should just return \r\n, but we don't check for it.
        time.sleep(0.5)

    @classmethod
    def open(cls, door_num: int):
        cls.set_state(door_num, DoorState.OPEN)

    @classmethod
    def secure(cls, door_num: int):
        cls.set_state(door_num, DoorState.SECURE)

    @classmethod
    def time_zone(cls, door_num: int):
        cls.set_state(door_num, DoorState.TIME_ZONE)
