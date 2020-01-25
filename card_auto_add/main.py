import abc
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime
from glob import glob
from io import TextIOBase
from queue import Queue, Empty as EmptyQueueException
from threading import Thread
from typing import List
from ctypes import Structure, windll, c_uint, sizeof, byref

import sentry_sdk
from pywinauto.application import Application, ProcessNotFoundError

import appdirs
import configparser

import pyodbc
import requests
import win32serviceutil

import servicemanager
import win32event
import win32service
from sentry_sdk import capture_exception
import logging

logger = logging.getLogger("card_access")
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)

file_handler = logging.FileHandler("C:/Users/700 Kalamath/.cards/card_access.log")
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)


class Config(object):
    def __init__(self):
        # TODO Handle File not existing
        config_path = os.path.join(appdirs.user_config_dir(), ".card_auto_add_config.ini")
        parser = configparser.ConfigParser()
        # TODO Handle File not existing
        parser.read(config_path)
        self._config_default = parser['DEFAULT']

    @property
    def db_path(self):
        return self._config_default['db_path']

    @property
    def ingest_dir(self):
        return self._config_default['ingest_dir']

    @property
    def windsx_path(self):
        return self._config_default['windsx_path']

    @property
    def no_interaction_delay(self):
        return int(self._config_default['no_interaction_delay'])

    @property
    def ingester_api_key(self):
        return self._config_default['ingester_api_key']

    @property
    def ingester_api_url(self):
        return self._config_default['ingester_api_url']

    @property
    def sentry_dsn(self):
        return self._config_default['sentry_dsn']


class DSXName(object):
    def __init__(self, first_name, last_name, company):
        self._first_name = first_name
        self._last_name = last_name
        self._company = company

    def get_lines(self):
        return [
            "T Names",
            f"F FName ^{self._first_name}^^^",
            f"F LName ^{self._last_name}^^^",
            f"F Company ^{self._company}^^^",
            "W"
        ]


class DSX_UDF(object):
    def __init__(self, num, text):
        self._num = num
        self._text = text

    def get_lines(self):
        return [
            "T UDF",
            f"F UdfNum ^{self._num}^^^",
            f"F UdfText ^{self._text}^^^",
            "W"
        ]


class DSXCard(object):
    def __init__(self, card_num):
        self._code = card_num.lstrip("0")
        self._card_num = card_num
        self._forever = datetime(9999, 12, 31, 0, 0)
        self._end_date = self._forever
        self._acls = []

    @property
    def _now(self):
        return datetime.now().replace(microsecond=0)

    def enable(self):
        self._end_date = self._forever

    def disable(self):
        self._end_date = self._now

    def add_acl(self, acl_name):
        self._acls.append(acl_name)

    def get_lines(self, ):
        return [
            "T Cards",
            f"F Code ^{self._code}^^^",
            f"F CardNum ^{self._card_num}^^^",
            f"F StopDate ^{self._format_date(self._end_date)}^^^",
            *[f"F AddAcl ^{acl}^^^" for acl in self._acls],
            "W"
        ]

    @staticmethod
    def _format_date(date):
        return date.__format__("%m/%d/%Y %H:%M")


class DSXCommand(object):
    def __init__(self, loc_grp, udf_num):
        self._loc_grp = loc_grp
        self._udf_num = udf_num
        self._udf_id = None
        self._name = None
        self._udf_table = []
        self._card_table = []

    def set_udf_id(self, udf_id: str):
        self._udf_id = udf_id
        self.add_udf(DSX_UDF(self._udf_num, self._udf_id))

    def set_name(self, name: DSXName):
        self._name = name

    def add_card(self, card: DSXCard):
        self._card_table.append(card)

    def add_udf(self, udf: DSX_UDF):
        self._udf_table.append(udf)

    def write(self, fh: TextIOBase):
        lines = [
            f"I L{self._loc_grp} U{self._udf_num} ^{self._udf_id}^^^",
            *[line for line in (self._name.get_lines() if self._name is not None else [])],
            *[line for udf_table in self._udf_table for line in udf_table.get_lines()],
            *[line for card_table in self._card_table for line in card_table.get_lines()],
            "P"
        ]

        for line in lines:
            fh.write(line)
            fh.write("\n")


class CardHolder(object):
    def __init__(self,
                 name_id,
                 first_name,
                 last_name,
                 company,
                 udf_id,
                 card,
                 card_active):
        self.name_id = name_id
        self.first_name = first_name
        self.last_name = last_name
        self.company = company
        self.udf_id = udf_id
        self.card = card
        self.card_active = card_active


class CardAccessSystem(object):
    def __init__(self, config: Config):
        self._db_path = config.db_path
        connection_string = (
                r'DRIVER={Microsoft Access Driver (*.mdb)};'
                r'DBQ=' + str(self._db_path) + ";"
        )
        self._connection = pyodbc.connect(connection_string)
        self._cursor = self._connection.cursor()

        self._udf_num = self._get_udf_num()
        self._loc_grp = 3  # TODO Look this up based on the name

    def new_command(self) -> DSXCommand:
        return DSXCommand(self._loc_grp, self._udf_num)

    def get_card_holders(self, first_name, last_name, company_name) -> List[CardHolder]:
        names_sql = \
            f"""
                SELECT
                    N.ID AS NameId,
                    N.FName AS FirstName,
                    N.LName AS LastName,
                    C.Name AS CompanyName,
                    U.UdfText AS UdfId
                FROM (
                    `NAMES` N
                    INNER JOIN COMPANY C
                        ON C.Company = N.Company
                    ) LEFT JOIN UDF U
                    ON U.NameID = N.ID
                WHERE N.FName = ?
                AND   N.LName = ?
                AND   C.Name = ?
            """

        names_rows = list(self._cursor.execute(names_sql,
                                               first_name,
                                               last_name,
                                               company_name))
        card_holders = []

        for row in names_rows:
            card_sql = \
                """
                    SELECT CARDS.Code, CARDS.Status
                    FROM CARDS
                    WHERE CARDS.NameId = ?
                """
            cards_rows = list(self._cursor.execute(card_sql, row.NameId))

            udf_id = row.UdfId
            if udf_id is None:
                udf_id = uuid.uuid4()
                self._insert_udf_id(udf_id, row.NameId)

            card_holders.extend([CardHolder(
                name_id=row.NameId,
                first_name=row.FirstName,
                last_name=row.LastName,
                company=row.CompanyName,
                udf_id=udf_id,
                card=('%f' % card.Code).rstrip('0').rstrip('.'),
                card_active=card.Status
            ) for card in cards_rows])

        return card_holders

    def get_card_holders_by_card_num(self, company_name, card_num) -> List[CardHolder]:
        sql = \
            """
                SELECT
                    N.ID AS NameId,
                    N.FName AS FirstName,
                    N.LName AS LastName,
                    CO.Name AS CompanyName,
                    U.UdfText AS UdfId,
                    CA.Code AS CardCode,
                    CA.Status as CardStatus
                FROM (
                         (
                             `NAMES` N
                                 INNER JOIN COMPANY CO
                                 ON CO.Company = N.Company
                             )
                            INNER JOIN CARDS CA
                            ON CA.NameID = N.ID
                         )
                    LEFT JOIN UDF U
                    ON U.NameID = N.ID
                    WHERE CO.Name = ?
                    AND CA.Code = ?
            """

        rows = list(self._cursor.execute(sql, company_name, card_num.lstrip("0")))

        name_to_udf = {}
        card_holders = []
        for row in rows:
            udf_id = row.UdfId
            if udf_id is None:
                if row.NameId in name_to_udf:
                    udf_id = name_to_udf[row.NameId]
                else:
                    udf_id = uuid.uuid4()
                    self._insert_udf_id(udf_id, row.NameId)
                    name_to_udf[row.NameId] = udf_id

            card_holders.append(CardHolder(
                name_id=row.NameId,
                first_name=row.FirstName,
                last_name=row.LastName,
                company=row.CompanyName,
                udf_id=udf_id,
                card=('%f' % row.CardCode).rstrip('0').rstrip('.'),
                card_active=row.CardStatus
            ))

        return card_holders

    def _get_udf_num(self):
        sql = "SELECT UdfNum FROM UDFName WHERE Name = ?"
        # TODO Check for no rows being returned
        # TODO Also check for the correct location group
        return list(self._cursor.execute(sql, "ID"))[0].UdfNum

    def _insert_udf_id(self, udf_id, name_id):
        if not isinstance(udf_id, str):
            udf_id = str(udf_id)
        sql = "INSERT INTO UDF(LocGrp, NameID, UdfNum, UdfText) VALUES(?, ?, ?, ?)"
        self._cursor.execute(sql, self._loc_grp, name_id, self._udf_num, udf_id)
        self._connection.commit()


class Command(object):
    __metaclass__ = abc.ABCMeta

    STATUS_NOT_DONE = "not_done"
    STATUS_SUCCESS = "success"
    # Multiple card holders have the same name/company
    STATUS_ERROR_MULTIPLE_CARD_HOLDERS = "error_multiple_card_holders"
    # Card wasn't found for a deactivation request
    STATUS_DEACTIVATE_CARD_NOT_FOUND = "deactivate_card_not_found"

    @abc.abstractmethod
    def get_dsx_command(self) -> DSXCommand:
        pass

    @property
    @abc.abstractmethod
    def status(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def id(self):
        pass


class EnableCardCommand(Command):
    def __init__(self,
                 command_id,
                 first_name,
                 last_name,
                 company,
                 card_num,
                 cas: CardAccessSystem):
        self.command_id = command_id
        self.first_name = first_name
        self.last_name = last_name
        self.company = company
        self.card_num = card_num
        self.cas = cas

    @property
    def id(self):
        return self.command_id

    def get_dsx_command(self) -> DSXCommand:
        dsx_command = self.cas.new_command()

        card_holders = self.cas.get_card_holders(
            self.first_name,
            self.last_name,
            self.company
        )

        if len(card_holders) > 1:
            logger.info("ERROR: Card holders > 1")
            sys.exit(1)  # TODO Do NOT exit

        dsx_command.set_name(DSXName(
            self.first_name,
            self.last_name,
            self.company
        ))
        udf_id = card_holders[0].udf_id if len(card_holders) == 1 else uuid.uuid4()
        dsx_command.set_udf_id(udf_id)
        dsx_card = DSXCard(self.card_num)
        dsx_card.add_acl("MBD Access")
        dsx_command.add_card(dsx_card)

        return dsx_command

    @property
    def status(self):
        card_holders = self.cas.get_card_holders(self.first_name, self.last_name, self.company)
        name_ids = list(dict.fromkeys([card_holder.name_id for card_holder in card_holders]))

        # Different name IDs mean we have different entries for the same name/company
        if len(name_ids) > 1:
            return self.STATUS_ERROR_MULTIPLE_CARD_HOLDERS

        logger.info(f"Status check card holders: {len(card_holders)}")
        card_holder: CardHolder
        for card_holder in card_holders:
            logger.info(f"Testing {card_holder.last_name}, {card_holder.first_name} with card {card_holder.card}")
            if (card_holder.card == self.card_num or
                card_holder.card == self.card_num.lstrip("0")) \
                    and card_holder.card_active:
                return self.STATUS_SUCCESS

        return self.STATUS_NOT_DONE


class DisableCardCommand(Command):
    def __init__(self,
                 command_id,
                 card_num,
                 company,
                 cas: CardAccessSystem):
        self.command_id = command_id
        self.card_num = card_num
        self.company = company
        self.cas = cas

    @property
    def id(self):
        return self.command_id

    def get_dsx_command(self) -> DSXCommand:
        dsx_command = self.cas.new_command()

        card_holders = self.cas.get_card_holders_by_card_num(self.company, self.card_num)

        if len(card_holders) > 1:
            logger.info("ERROR: Card holders > 1")
            sys.exit(1)  # TODO Do NOT exit

        udf_id = card_holders[0].udf_id if len(card_holders) == 1 else uuid.uuid4()
        dsx_command.set_udf_id(udf_id)
        dsx_card = DSXCard(self.card_num)
        dsx_card.add_acl("MBD Access")
        dsx_card.disable()
        dsx_command.add_card(dsx_card)

        return dsx_command

    @property
    def status(self):
        card_holders = self.cas.get_card_holders_by_card_num(self.company, self.card_num)
        name_ids = list(dict.fromkeys([card_holder.name_id for card_holder in card_holders]))

        # Different name IDs mean we have different entries for the same name/company
        if len(name_ids) > 1:
            return self.STATUS_ERROR_MULTIPLE_CARD_HOLDERS

        card_holder: CardHolder
        for card_holder in card_holders:
            if card_holder.card == self.card_num or card_holder.card == self.card_num.lstrip("0"):
                if not card_holder.card_active:
                    return self.STATUS_SUCCESS
                else:
                    return self.STATUS_NOT_DONE

        return self.STATUS_DEACTIVATE_CARD_NOT_FOUND


class WebhookServerApi(object):
    def __init__(self, config: Config):
        self._api_url = config.ingester_api_url

        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {config.ingester_api_key}"
        self._session.headers["Accept"] = "application/json"

    def get_command_json(self):
        try:
            response = self._session.get(self._api_url)

            if response.ok:
                json_response = response.json()

                if "data" not in json_response:
                    return None

                return json_response["data"]

            else:
                logger.info("read response was not ok!")
                logger.info(response.status_code)
                with open("read_error.html", "w", encoding="utf-8") as fh:
                    fh.write(str(response.content))
                raise Exception(f"Command json returned {response.status_code}")
        except Exception as e:
            logger.info(e)
            capture_exception(e)
            pass  # Yeah, we should probably do something about this

    def submit_status(self, command_id, status):
        try:
            url = f"{self._api_url}/{command_id}/status"
            logger.info(url)
            response = self._session.post(url, json={
                "status": status
            })

            if response.ok:
                return

            else:
                logger.info("status response was not ok!")
                logger.info(response.status_code)
                with open("status_error.html", "w", encoding="utf-8") as fh:
                    fh.write(str(response.content))
                raise Exception(f"Submit status returned {response.status_code}")
        except Exception as e:
            logger.info(e)
            capture_exception(e)
            pass  # Yeah, we should probably do something about this


class Processor(object):
    def __init__(self, config: Config,
                 server_api: WebhookServerApi):
        self._dsx_path = config.windsx_path
        self._command_queue = Queue()
        self._command_to_file = {}
        self._server_api = server_api

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
                command: Command
                for command, file in list(self._command_to_file.items()):
                    # logger.info(f"Checking {command.id} file: {file}")
                    if not os.path.exists(file):
                        del self._command_to_file[command]
                        logger.info(f"File {file} does not exist!")
                        self._server_api.submit_status(command.id, command.status)
                        logger.info(f"Status set for {command.id}: {command.status}")

                try:
                    queued_command: Command = self._command_queue.get(block=False)
                except EmptyQueueException:
                    continue  # We don't care that the queue is empty

                if queued_command is None:
                    continue

                unused_file_name = self._find_unused_file_name()

                if unused_file_name is not None:
                    self._command_to_file[queued_command] = unused_file_name
                    logger.info(f"Placing command in: {unused_file_name}")

                    with open(unused_file_name, 'w') as fh:
                        queued_command.get_dsx_command().write(fh)

                    self._command_queue.task_done()
            except Exception as e:
                capture_exception(e)

    def _find_unused_file_name(self) -> str:
        for first in range(10):
            for second in range(10):
                path = os.path.join(self._dsx_path, f"^IMP{first}{second}.txt")
                if not os.path.exists(path) and path not in self._command_to_file.values():
                    return path


class Ingester(object):
    def __init__(self, config: Config,
                 cas: CardAccessSystem,
                 server_api: WebhookServerApi,
                 command_queue: Queue):
        self.cas = cas
        self.ingest_dir = config.ingest_dir

        self.command_queue = command_queue
        self.requests_from_api_in_queue = set()

        self.server_api = server_api

    def start(self):
        thread = Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        while True:
            try:
                api_files = glob(self.ingest_dir + os.path.sep + "*.json")

                if len(api_files) > 0:
                    for api_file in api_files:
                        logger.info(f"Ingest Found: {api_file}")
                        with open(api_file, 'r') as fh:
                            json_data = json.load(fh)

                        command = self._get_dsx_command(json_data)
                        self.command_queue.put(command)

                        os.unlink(api_file)

                updates = self.server_api.get_command_json()
                for update in updates or []:
                    update_id = update["id"]

                    if update_id not in self.requests_from_api_in_queue:
                        logger.info(f"processing update {update_id}")
                        command = self._get_dsx_command(update)
                        self.command_queue.put(command)
                        self.requests_from_api_in_queue.add(update_id)
            except Exception as e:
                capture_exception(e)

            time.sleep(60)

    # TODO Validation
    def _get_dsx_command(self, json_data):
        method = json_data["method"]
        if method == "enable":
            return EnableCardCommand(
                json_data["id"],
                json_data["first_name"],
                json_data["last_name"],
                json_data["company"],
                json_data["card"],
                cas=self.cas
            )
        elif method == "disable":
            return DisableCardCommand(
                json_data["id"],
                json_data["card"],
                json_data["company"],
                cas=self.cas
            )


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
                            logger.info(f"WinDSX Api Found: {api}")

                        self._need_to_run_windsx = True

                no_interaction_time = self._current_no_interaction_time
                if self._need_to_run_windsx:
                    if no_interaction_time > self._no_interaction_delay:
                        self._login_and_close_windsx()
                    else:
                        logger.info("We need to run DSX, but someone has interacted with the computer too recently")
            except Exception as e:
                logger.info("Oh no, something happened!")
                logger.info(e)
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
        logger.info("What's an app?")
        app = self._get_windsx_app()
        logger.info(f"Woot the app returned: {app}")

        for window in app.windows():
            logger.info(window)

        logger.info(f"Them windows printed: {len(app.windows())}")

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
                logger.info("Trying to get an app")
                app = Application().connect(path=self.db_path)
                logger.info("Got an app")
            except ProcessNotFoundError:
                attempts_remaining = TOTAL_ATTEMPTS - attempts
                logger.info(
                    f"Failed to connect to WinDSX, trying to open, {attempts_remaining} attempt(s) remaining...")
                self._open_windsx()

                if attempts == TOTAL_ATTEMPTS:
                    raise

        return app


if __name__ == '__main__':
    config = Config()
    sentry_sdk.init(config.sentry_dsn)

    cas = CardAccessSystem(config)
    server_api = WebhookServerApi(config)

    processor = Processor(config, server_api)
    processor.start()

    ingester = Ingester(config, cas, server_api, processor.command_queue)
    ingester.start()

    api_watcher = DSXApiWatcher(config)
    api_watcher.start()

    while True:
        time.sleep(60)
