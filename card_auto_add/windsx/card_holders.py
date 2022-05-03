from typing import List

from card_auto_add.windsx.database import Database


class CardHolder(object):
    def __init__(self,
                 name_id,
                 first_name,
                 last_name,
                 company,
                 card,
                 card_active):
        self.name_id = name_id
        self.first_name = first_name
        self.last_name = last_name
        self.company = company
        self.card = card
        self.card_active = card_active


class WinDSXActiveCardHolders(object):
    def __init__(self, acs_db: Database):
        self._acs_db: Database = acs_db

    def get_active_card_holders(self, company_name) -> List[CardHolder]:
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

        with self._acs_db.lock:
            rows = list(self._acs_db.cursor.execute(sql, company_name))

            card_holders = []
            for row in rows:
                card_holders.append(CardHolder(
                    name_id=row.NameId,
                    first_name=row.FirstName,
                    last_name=row.LastName,
                    company=row.CompanyName,
                    card=str(row.CardCode).lstrip('0').rstrip('.'),
                    card_active=row.CardStatus
                ))

            return card_holders
