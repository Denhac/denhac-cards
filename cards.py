from datetime import datetime
import json
import pyodbc
import sys

input = json.dumps([{"method":"add","card":"50241","first_name":"Justin","last_name":"Testelrotte-2","company":14}])


class CardAccessSystem(object):
    def __init__(self, db_path):
        self.db_path = db_path
        connection_string = (
            r'DRIVER={Microsoft Access Driver (*.mdb)};'
            r'DBQ=' + str(db_path) + ";"
        )
        self.connection = pyodbc.connect(connection_string)
        self.cursor = self.connection.cursor()
        self.forever = datetime(9999, 12, 31, 0, 0)

    @property
    def now(self):
        return datetime.now().replace(microsecond=0)

    def find_by_name_and_company(self, first_name, last_name, company):
        sql = "SELECT ID, FName, LName, Company FROM NAMES WHERE FName = ? AND LName = ? AND Company = ?"
        return list(self.cursor.execute(sql, first_name, last_name, company))

    def insert_name(self, first_name, last_name, company):
        sql = "INSERT INTO NAMES(FName, LName, Company, LocGrp) VALUES (?, ?, ?, 3)"
        self.cursor.execute(sql, first_name, last_name, company)
        self.connection.commit()

    def find_by_card_number(self, card_num):
        card_num = card_num.lstrip("0")
        sql = """
            SELECT ID, NameID, Code, StartDate, StopDate FROM CARDS
            WHERE Code = ?
            """
        return list(self.cursor.execute(sql, card_num))

    def insert_card(self, name_id, card_num):
        card_num = card_num.lstrip("0")
        sql = """
            INSERT INTO CARDS(NameID, Code, CardNum, StartDate, StopDate, LocGrp, AclGrpComboId, Status)
            VALUES(?, ?, ?, ?, ?, 3, -2091141154, true)
            """
        self.cursor.execute(sql, name_id, card_num, card_num, self.now, self.forever)
        self.connection.commit()

    def disable_card(self, card_id):
        self.__update_card_stop_date(card_id, self.now)

    def enable_card(self, card_id):
        self.__update_card_stop_date(card_id, self.forever)

    def __update_card_stop_date(self, card_id, stop_date):
        status = self.now < stop_date
        sql = """
            UPDATE CARDS
            SET StopDate = ?,
            	Status = ?
            WHERE ID = ?
            """
        self.cursor.execute(sql, stop_date, status, card_id)
        self.connection.commit()

    def find_loc_card(self, card_id):
        sql = "SELECT ID, CardID FROM LocCards WHERE CardID = ?"
        return list(self.cursor.execute(sql, card_id))

    def insert_loc_card(self, card_id):
        sql = """
            INSERT INTO LocCards(CardID, Loc, Acl)
            VALUES(?, 3, 5)
            """
        self.cursor.execute(sql, card_id)
        self.connection.commit()

cas = CardAccessSystem("C:\WinDSX\AcsData.mdb")

all_complete = True

commands = json.loads(input)

if not isinstance(commands, list):
    print("Input was not a JSON list. Exiting")
    sys.exit(1)

for command in commands:
    print()
    print("Processing command:", command)

    if "method" not in command:
        print("Command has no method. Skipping")
        all_complete = False
        continue

    method = command["method"]

    if method == "add":
        if "first_name" not in command or "last_name" not in command or "company" not in command or "card" not in command:
            print("Add command is missing parameters. Skipping")
            all_complete = False
            continue

        first_name = command["first_name"]
        last_name = command["last_name"]
        company = command["company"]
        card_num = command["card"]

        print(f"Adding {card_num} for {first_name} {last_name}")
        rows = cas.find_by_name_and_company(first_name, last_name, company)
        if len(rows) == 0:
            print("Didn't find anyone. Adding!")
            sys.exit(1)
            cas.insert_name(first_name, last_name, company)
        elif len(rows) == 1:
            print("Looks like that name already exists")
        else:
            print("Found more than one person with that name/company. Skipping")
            all_complete = False
            continue

        sys.exit(1)

        name_id = cas.find_by_name_and_company(first_name, last_name, company)[0].ID
        print("Name ID:", name_id)

        rows = cas.find_by_card_number(card_num)
        if len(rows) == 0:
            print("That card wasn't found. Adding!")
            cas.insert_card(name_id, card_num)
        elif len(rows) == 1:
            print("Looks like that card already exists")
            if rows[0].NameID != name_id:
                print("Name ID doesn't match the specified person. Skipping")
                all_complete = False
                continue
        else:
            print("More than one card found. Skipping")
            all_complete = False
            continue

        card_id = cas.find_by_card_number(card_num)[0].ID
        print("Card ID:", card_id)

        rows = cas.find_loc_card(card_id)
        if len(rows) == 0:
            print("That card wasn't find in LocCards. Adding!")
            cas.insert_loc_card(card_id)
        else:
            print("Looks like that card was already in LocCards.")

        loc_id = cas.find_loc_card(card_id)[0].ID
        print("Loc ID:", loc_id)

        continue

        cas.cursor.execute("DELETE FROM LocCards WHERE ID = ?", loc_id)
        cas.cursor.execute("DELETE FROM CARDS WHERE ID = ?", card_id)
        cas.cursor.execute("DELETE FROM NAMES WHERE ID = ?", name_id)
        cas.connection.commit()

    elif method == "disable":
        if "card" not in command:
            print("Disable command is missing parameters. Skipping")
            all_complete = False
            continue

        card_num = command["card"]

        print(f"Disabling {card_num}")

        rows = cas.find_by_card_number(card_num)

        if len(rows) == 0:
            print("That card was not found. Skipping")
            all_complete = False
            continue
        elif len(rows) > 1:
            print("More than one card found. Skipping")
            all_complete = False
            continue

        card_id = rows[0].ID
        print("Card ID:", card_id)
        cas.disable_card(card_id)

    elif method == "enable":
        if "card" not in command:
            print("Enable command is missing parameters. Skipping")
            all_complete = False
            continue

        card_num = command["card"]

        print(f"Enabling {card_num}")

        rows = cas.find_by_card_number(card_num)

        if len(rows) == 0:
            print("That card was not found. Skipping")
            all_complete = False
            continue
        elif len(rows) > 1:
            print("More than one card found. Skipping")
            all_complete = False
            continue

        card_id = rows[0].ID
        print("Card ID:", card_id)
        cas.enable_card(card_id)

if not all_complete:
    print("Something went wrong!!")
    sys.exit(1)