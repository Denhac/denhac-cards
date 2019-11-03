from card_auto_add.cas import *
from card_auto_add.commands import EnableCardCommand, DisableCardCommand

db_path = "C:/WinDSX/AcsData.mdb"
cas = CardAccessSystem(db_path)
# command = cas.get_command("Foo", "Bar", "DenHac", "06363")
#
# with open("test.txt", "w") as fh:
#     command.write(fh)

# card_holders = cas.get_card_holders("Justin", "Testelrotte", "DenHac")
#
# for holder in card_holders:
#     print(holder.first_name, holder.last_name, holder.company, holder.udf_id, *holder.cards)

ecc = EnableCardCommand(
    "Justin",
    "Testelrotte",
    "DenHac",
    "06363",
    cas
)

dcc = DisableCardCommand("06363", "DenHac", cas)

with open("C:/WinDSX/^IMP01.txt", "w") as fh:
    dcc.get_dsx_command().write(fh)
