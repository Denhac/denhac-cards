from threading import Lock

import pyodbc


class Database(object):
    def __init__(self, db_path):
        self._connection = pyodbc.connect((
                r'DRIVER={Microsoft Access Driver (*.mdb)};'
                r'DBQ=' + str(db_path) + ";"
        ))
        self._cursor = self.connection.cursor()
        self._db_lock = Lock()

    @property
    def lock(self) -> Lock:
        return self._db_lock

    @property
    def connection(self) -> pyodbc.Connection:
        return self._connection

    @property
    def cursor(self) -> pyodbc.Cursor:
        return self._cursor
