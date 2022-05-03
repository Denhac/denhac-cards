from card_auto_add.windsx.database import Database


class CardScan(object):
    def __init__(self,
                 name_id,
                 first_name,
                 last_name,
                 company,
                 card,
                 scan_time,
                 access_allowed,
                 device):
        self.name_id = name_id
        self.first_name = first_name
        self.last_name = last_name
        self.company = company
        self.card = card
        self.scan_time = scan_time
        self.access_allowed = access_allowed
        self.device = device


class WinDSXCardScan(object):
    def __init__(self,
                 acs_db: Database,
                 log_db: Database
                 ):
        self._acs_db: Database = acs_db
        self._log_db: Database = log_db
        self._company = self._get_company_from_name("denhac")

    def get_scan_events_since(self, timestamp):
        access_allowed_code = 8
        access_denied_unknown_code = 174
        sql = \
            f"""
            SELECT
                TimeDate,
                Event,
                Code AS CardCode,
                Opr AS NameId,
                Dev AS Device
            FROM EvnLog
            WHERE Event IN ({access_allowed_code}, {access_denied_unknown_code})
            AND IO = ?
            AND TimeDate > ?
        """

        with self._log_db.lock:
            rows = list(self._log_db.cursor.execute(sql, (self._company, timestamp)))

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
                card=str(row.CardCode).lstrip('0').rstrip('.'),
                scan_time=row.TimeDate,
                access_allowed=access_allowed,
                device=row.Device
            ))

        return card_scans

    def get_devices(self):
        sql = \
            """
                SELECT
                    D.Device as Device,
                    D.Name as Name
                FROM `DEV` D
            """

        with self._acs_db.lock:
            rows = list(self._acs_db.cursor.execute(sql))

        result = {}
        for row in rows:
            result[row.Device] = row.Name

        return result

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

        with self._acs_db.lock:
            name_rows = list(self._acs_db.cursor.execute(sql, name_id))

        if len(name_rows) == 0:
            return None

        return name_rows[0]

    def _get_company_from_name(self, company_name):
        sql = "SELECT Company FROM COMPANY WHERE Name = ?"

        with self._acs_db.lock:
            return list(self._acs_db.cursor.execute(sql, company_name))[0].Company
