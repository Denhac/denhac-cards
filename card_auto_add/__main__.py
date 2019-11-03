from card_auto_add.cas import *
from card_auto_add.commands import EnableCardCommand, DisableCardCommand

db_path = "C:/WinDSX/AcsData.mdb"
cas = CardAccessSystem(db_path)

ecc = EnableCardCommand(
    "Justin",
    "Testelrotte",
    "DenHac",
    "06363",
    cas
)

dcc = DisableCardCommand("06363", "DenHac", cas)

with open("C:/WinDSX/^IMP01.txt", "w") as fh:
    ecc.get_dsx_command().write(fh)
