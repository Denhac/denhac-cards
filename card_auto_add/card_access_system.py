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