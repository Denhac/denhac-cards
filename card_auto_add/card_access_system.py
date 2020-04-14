import json
from threading import Lock

import uuid
from typing import List

import pyodbc

from card_auto_add.config import Config
from card_auto_add.dsx import DSXCommand


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


class CardScan(object):
    def __init__(self,
                 name_id,
                 first_name,
                 last_name,
                 company,
                 card,
                 scan_time,
                 access_allowed):
        self.name_id = name_id
        self.first_name = first_name
        self.last_name = last_name
        self.company = company
        self.card = card
        self.scan_time = scan_time
        self.access_allowed = access_allowed


class Database(object):
    def __init__(self, db_path):
        self._connection = pyodbc.connect((
                r'DRIVER={Microsoft Access Driver (*.mdb)};'
                r'DBQ=' + str(db_path) + ";"
        ))
        self._cursor = self.connection.cursor()

    @property
    def connection(self) -> pyodbc.Connection:
        return self._connection

    @property
    def cursor(self) -> pyodbc.Cursor:
        return self._cursor


class CardAccessSystem(object):
    def __init__(self, config: Config):
        self._db = Database(config.acs_data_db_path)
        self._log_db = Database(config.log_db_path)

        self._company = self._get_company_from_name("denhac")
        self._udf_num = self._get_udf_num()
        self._loc_grp = 3  # TODO Look this up based on the name
        self._db_lock = Lock()

    def new_command(self) -> DSXCommand:
        return DSXCommand(self._loc_grp, self._udf_num)

    def get_card_holders_by_name(self, first_name, last_name, company_name) -> List[CardHolder]:
        with self._db_lock:
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

            names_rows = list(self._db.cursor.execute(names_sql,
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
                cards_rows = list(self._db.cursor.execute(card_sql, row.NameId))

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
        with self._db_lock:
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

            rows = list(self._db.cursor.execute(sql, company_name, card_num.lstrip("0")))

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
                    card=self._strip_card_leading_zeros(row.CardCode),
                    card_active=row.CardStatus
                ))

            return card_holders

    def get_active_card_holders(self, company_name) -> List[CardHolder]:
        with self._db_lock:
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
                        AND CA.Status = true
                """

            rows = list(self._db.cursor.execute(sql, company_name))

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
                    card=self._strip_card_leading_zeros(row.CardCode),
                    card_active=row.CardStatus
                ))

            return card_holders

    def get_card_scans(self, company_name) -> List[CardScan]:
        with self._db_lock:
            sql = \
                """
                    SELECT
                        N.ID AS NameId,
                        N.FName AS FirstName,
                        N.LName AS LastName,
                        CO.Name AS CompanyName,
                        CA.Code AS CardCode,
                        LC.LastDate as ScanTime
                    FROM (
                             (
                                 `NAMES` N
                                     INNER JOIN COMPANY CO
                                     ON CO.Company = N.Company
                                 )
                                INNER JOIN CARDS CA
                                ON CA.NameID = N.ID
                             )
                        LEFT JOIN LocCards LC
                        ON LC.CardId = CA.ID
                        WHERE CO.Name = ?
                        AND CA.Status = true
                """

            rows = list(self._db.cursor.execute(sql, company_name))

            card_scans = []

            for row in rows:
                card_scans.append(CardScan(
                    name_id=row.NameId,
                    first_name=row.FirstName,
                    last_name=row.LastName,
                    company=row.CompanyName,
                    card=self._strip_card_leading_zeros(row.CardCode),
                    scan_time=row.ScanTime,
                    access_allowed=True
                ))

            return card_scans

    def get_scan_events_since(self, timestamp):
        access_allowed_code = 8
        access_denied_unknown_code = 174
        sql = \
        f"""
            SELECT
                TimeDate,
                Event,
                Code AS CardCode,
                Opr AS NameId
            FROM EvnLog
            WHERE Event IN ({access_allowed_code}, {access_denied_unknown_code})
            AND IO = ?
            AND TimeDate > ?
        """

        rows = list(self._log_db.cursor.execute(sql, self._company, timestamp))

        card_scans = []

        for row in rows:
            name_info = self._get_name_info_from_id(row.NameId)
            if name_info is None:
                continue  # We couldn't find the name for this event

            access_allowed = row.Event == access_allowed_code
            card_scans.append(CardScan(
                name_id=row.NameId,
                first_name=name_info.FirstName,
                last_name=name_info.LastName,
                company=name_info.CompanyName,
                card=self._strip_card_leading_zeros(row.CardCode),
                scan_time=row.TimeDate,
                access_allowed=access_allowed
            ))

        return card_scans

    def _strip_card_leading_zeros(self, card_code):
        return ('%f' % card_code).rstrip('0').rstrip('.')

    def _get_name_info_from_id(self, name_id):
        sql = \
            """
                SELECT
                    N.ID AS NameId,
                    N.FName AS FirstName,
                    N.LName AS LastName,
                    CO.Name AS CompanyName
                FROM `NAMES` N
                INNER JOIN `COMPANY` CO
                    ON CO.Company = N.Company
                WHERE N.ID = ?
            """

        name_rows = list(self._db.cursor.execute(sql, name_id))

        if len(name_rows) == 0:
            return None

        return name_rows[0]

    def _get_company_from_name(self, company_name):
        sql = "SELECT Company FROM COMPANY WHERE Name = ?"
        return list(self._db.cursor.execute(sql, company_name))[0].Company

    def _get_udf_num(self):
        sql = "SELECT UdfNum FROM UDFName WHERE Name = ?"
        # TODO Check for no rows being returned
        # TODO Also check for the correct location group
        return list(self._db.cursor.execute(sql, "ID"))[0].UdfNum

    def _insert_udf_id(self, udf_id, name_id):
        if not isinstance(udf_id, str):
            udf_id = str(udf_id)
        sql = "INSERT INTO UDF(LocGrp, NameID, UdfNum, UdfText) VALUES(?, ?, ?, ?)"
        self._db.cursor.execute(sql, self._loc_grp, name_id, self._udf_num, udf_id)
        self._db.connection.commit()