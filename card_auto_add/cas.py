import uuid
from datetime import datetime
from io import TextIOBase
from typing import List

import pyodbc


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
                 cards):
        self.name_id = name_id
        self.first_name = first_name
        self.last_name = last_name
        self.company = company
        self.udf_id = udf_id
        self.cards = cards


class CardAccessSystem(object):
    def __init__(self, db_path):
        self._db_path = db_path
        connection_string = (
                r'DRIVER={Microsoft Access Driver (*.mdb)};'
                r'DBQ=' + str(db_path) + ";"
        )
        self._connection = pyodbc.connect(connection_string)
        self._cursor = self._connection.cursor()

        self._udf_num = self._get_udf_num()
        self._loc_grp = 3  # TODO Look this up based on the name

    # TODO Implement a get command type thing with just a card_num that does a lookup
    # or throws/returns None if that card doesn't have an associated name.

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
                    SELECT CARDS.Code
                    FROM CARDS
                    WHERE CARDS.NameId = ?
                """
            cards_rows = list(self._cursor.execute(card_sql, row.NameId))
            cards = [str(card.Code) for card in cards_rows]

            udf_id = row.UdfId
            if udf_id is None:
                udf_id = uuid.uuid4()
                self._insert_udf_id(udf_id, row.NameId)

            card_holders.append(CardHolder(
                name_id=row.NameId,
                first_name=row.FirstName,
                last_name=row.LastName,
                company=row.CompanyName,
                udf_id=udf_id,
                cards=cards
            ))

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
                    CA.Code AS CardCode
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

        card_holders = []
        for row in rows:
            udf_id = row.UdfId
            if udf_id is None:
                # TODO Can a person have more than one card? If so, this will break if they have no udf id
                udf_id = uuid.uuid4()
                self._insert_udf_id(udf_id, row.NameId)

            card_holders.append(CardHolder(
                name_id=row.NameId,
                first_name=row.FirstName,
                last_name=row.LastName,
                company=row.CompanyName,
                udf_id=udf_id,
                cards=[row.CardCode]
            ))

        return card_holders

    def get_command(self, first_name, last_name, company, card_num):
        card_num = str(card_num)
        name = DSXName(first_name, last_name, company)
        _id = self._get_id(first_name, last_name, company)
        command = DSXCommand(3, 1, _id)
        command.set_name(name)
        command.add_udf(DSX_UDF(self._udf_num, _id))
        card = DSXCard(card_num)
        card.disable()
        card.add_acl("MBD Access")
        command.add_card(card)

        return command

    # Ensures that the ID is in the database and returns it, or just creates one
    def _get_id(self, first_name, last_name, company):
        rows = self._find_by_name_and_company(first_name, last_name, company)
        if len(rows) == 0:
            return uuid.uuid4()
        else:  # TODO Handle more than one row
            name_id = rows[0].ID
            _id = self._get_udf_id_from_db(name_id)
            if _id is None:
                _id = str(uuid.uuid4())
                self._insert_udf_id(_id, name_id)
            return _id

    def _get_udf_num(self):
        sql = "SELECT UdfNum FROM UDFName WHERE Name = ?"
        # TODO Check for no rows being returned
        # TODO Also check for the correct location group
        return list(self._cursor.execute(sql, "ID"))[0].UdfNum

    def _find_by_name_and_company(self, first_name, last_name, company):
        if isinstance(company, str):
            company = self._find_company_id(company)
        sql = "SELECT ID, FName, LName,  FROM NAMES WHERE FName = ? AND LName = ? AND Company = ?"
        return list(self._cursor.execute(sql, first_name, last_name, company))

    def _get_udf_id_from_db(self, name_id):
        sql = "SELECT UdfText FROM UDF Where NameId = ? AND UdfNum = ?"
        rows = list(self._cursor.execute(sql, name_id, self._udf_num))
        if len(rows) == 1:
            return rows[0].UdfText
        return None

    def _insert_udf_id(self, udf_id, name_id):
        if not isinstance(udf_id, str):
            udf_id = str(udf_id)
        sql = "INSERT INTO UDF(LocGrp, NameID, UdfNum, UdfText) VALUES(?, ?, ?, ?)"
        self._cursor.execute(sql, self._loc_grp, name_id, self._udf_num, udf_id)
        self._connection.commit()

    def _find_by_card_number(self, card_num):
        sql = """
            SELECT ID, NameID, Code, StartDate, StopDate FROM CARDS
            WHERE Code = ?
            """
        return list(self._cursor.execute(sql, card_num))

    def _find_company_id(self, company):
        sql = "SELECT Company FROM COMPANY WHERE Name = ?"
        # TODO Check for no rows being returned
        # TODO Also check for the correct location group
        return list(self._cursor.execute(sql, company))[0].Company
