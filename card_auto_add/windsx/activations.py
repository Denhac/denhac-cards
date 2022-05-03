import time
import uuid
from collections import defaultdict
from datetime import datetime
from itertools import groupby
from typing import Union, Optional

from card_auto_add.config import Config
from card_auto_add.windsx.database import Database


class CardInfo(object):
    def __init__(self,
                 first_name,
                 last_name,
                 company,
                 woo_id,
                 card):
        self.first_name = first_name
        self.last_name = last_name
        self.company = company
        self.user_id = woo_id
        self.card = card


class WinDSXCardActivations(object):
    _date_never = datetime(9999, 12, 31)

    def __init__(self,
                 config: Config,
                 acs_db: Database,
                 ):
        self._acs_db: Database = acs_db
        self._default_acl = config.windsx_acl
        self._log = config.logger

        self._loc_grp = 3  # TODO Look this up based on the name
        self._udf_name = "ID"  # TODO Look this up in config

    def activate(self, card_info: CardInfo):
        self._log.info(f"Activating card {card_info.card}")
        acl_name_id = self._get_acl_by_name(self._default_acl)

        name_id = self._find_or_create_name(card_info)

        card_id, card_combo_id = self._get_card_combo_id(card_info.card)

        if card_id is None:
            # This should give us the card combo id with just our acl
            card_combo_id = self._find_or_create_new_combo_id(None, acl_name_id)
            card_id = self._create_card(name_id, card_info.card, card_combo_id)
        else:
            new_card_combo_id = self._get_card_combo_containing_acl(card_combo_id, acl_name_id)

            if card_combo_id != new_card_combo_id:
                self._log.info(f"Updating card combo id from {card_combo_id} to {new_card_combo_id}")
                self._update_card_combo_id(card_id, new_card_combo_id)
                card_combo_id = new_card_combo_id

            self._set_card_active(card_id, name_id)

        acl_ids = self._find_or_create_acl_id(card_combo_id)
        self._log.info(f"Using ACL IDs: {acl_ids}")

        self._create_or_update_loc_cards(card_id, acl_ids)

        self._encourage_system_update()

    def deactivate(self, card_info: CardInfo):
        self._log.info(f"Deactivating card {card_info.card}")
        card_id, _ = self._get_card_combo_id(card_info.card)

        if card_id is None:
            self._log.info(f"Card id not found for {card_info.card}, so it's safe to assume it never was activated")
            return

        self._set_card_inactive(card_id)

        self._encourage_system_update()

    def _find_or_create_name(self, card_info: CardInfo):
        # First, let's try to find it via uuid5
        customer_uuid = str(uuid.uuid5(uuid.NAMESPACE_OID, str(card_info.user_id)))

        udf_num = self._acs_db.cursor.execute("SELECT UdfNum FROM UdfName WHERE Name = ?", self._udf_name).fetchval()

        if udf_num is None:
            raise ValueError(f"Failed to find UDF Name ID {self._udf_name}")

        name_id = self._acs_db.cursor.execute(
            "SELECT NameId FROM UDF WHERE UdfNum = ? AND UdfText = ?",
            (udf_num, customer_uuid)
        ).fetchval()

        if name_id is not None:
            self._log.info(f"Found name id {name_id} based on customer id {card_info.user_id}")
            return name_id

        company_id = self._acs_db.cursor.execute("SELECT Company from COMPANY WHERE Name = ?",
                                                 card_info.company).fetchval()

        if company_id is None:
            raise ValueError(f"No company found for company name '{card_info.company}'")

        name_id = self._acs_db.cursor.execute(
            "SELECT ID FROM NAMES WHERE FName = ? AND LName = ? AND Company = ?",
            (card_info.first_name, card_info.last_name, company_id)
        ).fetchval()

        if name_id is not None:
            self._log.info(f"Found name id {name_id} based on customer's first/last name and company")
            # We couldn't look it up via UUID for some reason, so make sure to update it so we can next time
            self._create_or_update_udf_text(udf_num, name_id, customer_uuid)
            return name_id

        self._log.info(f"No name ID found for customer {card_info.user_id}, will make one")

        self._acs_db.cursor.execute(
            "INSERT INTO NAMES(LocGrp, FName, LName, Company) VALUES (?, ?, ?, ?)",
            (self._loc_grp, card_info.first_name, card_info.last_name, company_id)
        )
        name_id = self._acs_db.cursor.execute("SELECT @@IDENTITY").fetchval()

        if name_id is None:
            raise ValueError("Didn't get name ID on insert")

        self._create_or_update_udf_text(udf_num, name_id, customer_uuid)

    def _create_or_update_udf_text(self, udf_num, name_id, customer_uuid):
        existing_value = self._acs_db.cursor.execute(
            "SELECT UdfText FROM UDF WHERE NameID = ? AND UdfNum = ?",
            (name_id, udf_num)
        ).fetchval()

        if existing_value is not None:
            if existing_value != customer_uuid:
                self._acs_db.cursor.execute(
                    "UPDATE UDF SET UdfText = ? WHERE NameId = ? AND UdfNum = ?",
                    (customer_uuid, name_id, udf_num)
                )
        else:
            self._acs_db.cursor.execute(
                "INSERT INTO UDF(LocGrp, NameID, UdfNum, UdfText) VALUES (?, ?, ?, ?)",
                (self._loc_grp, name_id, udf_num, customer_uuid)
            )

        self._acs_db.connection.commit()

    def _get_acl_by_name(self, acl_name):
        sql = "SELECT ID FROM AclGrpName WHERE Name = ?"

        self._acs_db.cursor.execute(sql, acl_name)
        acl_name_id = self._acs_db.cursor.fetchval()

        if acl_name_id is None:
            raise ValueError(f"Could not find acl named {acl_name}")

        self._log.info(f"Found ACL Name ID: {acl_name_id}")
        return acl_name_id

    def _get_card_combo_id(self, card_num: Union[str, int]):
        if not isinstance(card_num, str):
            card_num = str(card_num)

        sql = "SELECT ID, AclGrpComboId FROM `CARDS` WHERE Code = ?"

        self._acs_db.cursor.execute(sql, card_num.lstrip('0'))
        row = self._acs_db.cursor.fetchone()

        if row is None:
            self._log.info(f"No existing card was found for card {card_num}")
            return None, None
        else:
            card_id = row.ID
            card_combo_id = row.AclGrpComboId
            self._log.info(f"Found card id {card_id} and combo id {card_combo_id} for card {card_num}")

            return card_id, card_combo_id

    def _get_card_combo_containing_acl(self, card_combo_id, acl_name_id):
        if self._combo_contains_name_id(card_combo_id, acl_name_id):
            self._log.info(f"Acl combo id {card_combo_id} does contain desired acl name id {acl_name_id}")
        else:
            self._log.info(f"Acl combo id {card_combo_id} does not contain desired acl name id {acl_name_id}")
            card_combo_id = self._find_or_create_new_combo_id(card_combo_id, acl_name_id)
            self._log.info(f"New acl combo id: {card_combo_id}")

        return card_combo_id

    def _combo_contains_name_id(self, card_combo_id, acl_name_id):
        sql = "SELECT AclGrpNameID FROM AclGrpCombo WHERE ComboID = ?"
        name_ids = [x[0] for x in self._acs_db.cursor.execute(sql, card_combo_id)]

        return acl_name_id in name_ids

    def _find_or_create_new_combo_id(self, base_card_combo_id: Optional[int], acl_name_id):
        if base_card_combo_id is None:
            known_name_ids = set()
        else:
            sql = "SELECT AclGrpNameID FROM AclGrpCombo WHERE ComboID = ?"
            known_name_ids = set([x[0] for x in self._acs_db.cursor.execute(sql, base_card_combo_id)])

        known_name_ids.add(acl_name_id)

        acl_combos = list(self._acs_db.cursor.execute("SELECT AclGrpNameID, ComboID FROM AclGrpCombo"))
        grouped_by_combo_id = groupby(acl_combos, lambda x: x.ComboID)

        for new_combo_id, value in grouped_by_combo_id:
            acl_name_ids = set([x[0] for x in value])
            if acl_name_ids == known_name_ids:
                return new_combo_id

        self._log.info("We didn't find a valid combo id, will create one.")

        # Let's start by inserting a group combo without a known combo id to create and retrieve our new combo id
        self._acs_db.cursor.execute(
            "INSERT INTO AclGrpCombo(AclGrpNameID, LocGrp) VALUES (?, ?)",
            (acl_name_id, self._loc_grp)
        )

        new_combo_id = self._acs_db.cursor.execute("SELECT @@IDENTITY").fetchval()
        for name_id in known_name_ids:
            self._acs_db.cursor.execute(
                "INSERT INTO AclGrpCombo(AclGrpNameID, ComboID, LocGrp) VALUES (?, ?, ?)",
                (name_id, new_combo_id, self._loc_grp)
            )

        self._acs_db.connection.commit()

        return new_combo_id

    def _create_card(self, name_id, card_num, card_combo_id):
        # This function assumes that you're creating a card to be activated, so it sets the start/stop date and status
        # accordingly.

        now = datetime.now()

        self._acs_db.cursor.execute(
            """
                INSERT INTO CARDS(NameID, LocGrp, Code, StartDate, StopDate, Status, CardNum, DlFlag, AclGrpComboId)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name_id, self._loc_grp, card_num.lstrip('0'), now, self._date_never, True, card_num, 0, card_combo_id)
        )

        card_id = self._acs_db.cursor.execute("SELECT @@IDENTITY").fetchval()
        if card_id is None:
            raise ValueError(f"Card ID could not be retrieved on created card for card {card_num}")

        self._acs_db.connection.commit()

        self._log.info(f"Created card with card id {card_id}")

        return card_id

    def _update_card_combo_id(self, card_id, new_card_combo_id):
        self._acs_db.cursor.execute(
            "UPDATE CARDS SET AclGrpComboID = ?, DlFlag = 0 WHERE ID = ?",
            (new_card_combo_id, card_id)
        )
        self._acs_db.connection.commit()

    def _set_card_active(self, card_id, name_id):
        self._acs_db.cursor.execute(
            "UPDATE CARDS SET NameID = ?, StartDate = ?, StopDate = ?, DlFlag = 0, Status = True WHERE ID = ?",
            (name_id, datetime.now(), self._date_never, card_id)
        )
        self._acs_db.connection.commit()

    def _set_card_inactive(self, card_id):
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self._acs_db.cursor.execute(
            "UPDATE CARDS SET StopDate = ?, DlFlag = 0, Status = False WHERE ID = ?",
            (today, card_id)
        )

        self._acs_db.cursor.execute("UPDATE LocCards SET DlFlag = 1, CkSum = 0 WHERE CardID = ?", card_id)
        self._acs_db.connection.commit()

    def _find_or_create_acl_id(self, card_combo_id):
        device_access = self._acs_db.cursor.execute(
            """
                SELECT Dev, Tz1, Tz2, Tz3, Tz4 FROM ACLGrp WHERE AclGrpNameID IN (
                    SELECT AclGrpNameID From AclGrpCombo WHERE ComboId = ?
                )
            """,
            card_combo_id
        ).fetchall()

        tz_to_dev_list = defaultdict(lambda: set())
        for access in device_access:
            if access.Tz1 != 0:
                tz_to_dev_list[access.Tz1].add(access.Dev)
            if access.Tz2 != 0:
                tz_to_dev_list[access.Tz2].add(access.Dev)
            if access.Tz3 != 0:
                tz_to_dev_list[access.Tz3].add(access.Dev)
            if access.Tz4 != 0:
                tz_to_dev_list[access.Tz4].add(access.Dev)

        device_groups = list(self._acs_db.cursor.execute("SELECT * FROM DGRP").fetchall())
        tz_to_device_group = {}
        for tz, dev_list in tz_to_dev_list.items():
            tz_to_device_group[tz] = self._find_or_create_matching_device_group(dev_list, device_groups)

        acls = set()
        for tz, device_group in tz_to_device_group.items():
            acls.add(self._find_or_create_matching_acl(tz, device_group))

        return acls

    def _find_or_create_matching_device_group(self, dev_list, device_groups):
        for group in device_groups:
            valid_group = True
            for dev in range(128):
                device_on = dev in dev_list  # Do we need this device
                group_device_on = getattr(group, f"D{dev}")  # Is this device set to true

                if device_on != group_device_on:  # Those values must match for a valid group
                    valid_group = False
                    break

            if valid_group:
                self._log.info(f"Found a valid device group {group.DGrp}")
                return group.DGrp

        self._log.info("No valid device group found, creating one")

        group_names = self._acs_db.cursor.execute("SELECT DGrp FROM DGRP").fetchall()
        device_group = max([int(x.DGrp) for x in group_names if float.is_integer(x.DGrp)]) + 1  # Grab the next one

        sql = "INSERT INTO DGRP(DGrp, DlFlag, CkSum"
        for i in range(128):
            sql += f", D{i}"

        sql += ") VALUES ("
        for i in range(128 + 3):  # 128 devices + 3 fields above
            sql += f", ?"
        sql += ")"

        values = [device_group, 1, 0]
        for i in range(128):
            values.append(i in dev_list)

        self._acs_db.cursor.execute(sql, values)
        self._acs_db.connection.commit()

    def _find_or_create_matching_acl(self, tz, device_group):
        acl = self._acs_db.cursor.execute("SELECT Acl FROM ACL WHERE Tz = ? AND DGrp = ?",
                                          (tz, device_group)).fetchval()

        if acl is not None:
            return acl

        self._log.info(f"Acl not found for Tz {tz} and device group {device_group}, creating one")

        acl_names = self._acs_db.cursor.execute("SELECT Acl FROM ACL").fetchall()
        acl = max([int(x.DGrp) for x in acl_names if float.is_integer(x.DGrp)]) + 1  # Grab the next one

        self._acs_db.cursor.execute(
            "INSERT INTO ACL(Loc, Acl, Tz, DGrp, DlFlag, CkSum) VALUES (?, ?, ?, ?, ?, ?)",
            (self._loc_grp, acl, tz, device_group, 1, 0)
        )
        self._acs_db.connection.commit()

        return acl

    def _create_or_update_loc_cards(self, card_id, acl_ids):
        loc_card_id = self._acs_db.cursor.execute("SELECT ID FROM LocCards WHERE CardID = ?", card_id).fetchval()

        acl = acl1 = acl2 = acl3 = acl4 = -1
        if acl_ids:
            acl = acl_ids.pop()
        if acl_ids:
            acl1 = acl_ids.pop()
        if acl_ids:
            acl2 = acl_ids.pop()
        if acl_ids:
            acl3 = acl_ids.pop()
        if acl_ids:
            acl4 = acl_ids.pop()

        if loc_card_id is not None:
            self._log.info(f"Found LocCard id {loc_card_id}, updating ACLs")
            self._acs_db.cursor.execute(
                "UPDATE LocCards SET DlFlag = 1, CkSum = 0, Acl = ?, Acl1 = ?, Acl2 = ?, Acl3 = ?, Acl4 = ? WHERE ID = ?",
                (acl, acl1, acl2, acl3, acl4, loc_card_id)
            )
        else:
            self._log.info("LocCard not found, creating one")
            self._acs_db.cursor.execute(
                "INSERT INTO LocCards(Loc, CardId, DlFlag, CkSum, Acl, Acl1, Acl2, Acl3, Acl4) "
                "VAlUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (self._loc_grp, card_id, 1, 0, acl, acl1, acl2, acl3, acl4)
            )

        self._acs_db.connection.commit()

    def _encourage_system_update(self):
        self._acs_db.cursor.execute("UPDATE DEV SET DlFlag=1, CkSum=0")
        self._acs_db.cursor.execute("UPDATE IO SET DlFlag=1")
        self._acs_db.cursor.execute(
            "UPDATE LOC SET PlFlag=True, DlFlag=1, FullDlFlag=True, NodeCs=0, CodeCs=0, AclCs=0, DGrpCs=0"
        )

        self._acs_db.connection.commit()

        self._log.info("Comm Server update requested")
        for i in range(30):
            downloading = self._acs_db.cursor.execute("SELECT FullDlFlag FROM LOC").fetchval()

            if not downloading:
                self._log.info("Looks like everything updated!")
                return

            self._log.info("Update doesn't look like it's gone through yet, waiting 10 seconds")
            time.sleep(10)

        self._log.info("Update timed out")
        raise Exception("Comm Server update timed out")
