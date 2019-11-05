import abc
import sys
import uuid

from card_auto_add.cas import DSXCommand, DSXName, DSXCard
from card_auto_add.cas import CardAccessSystem


class Command(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def get_dsx_command(self) -> DSXCommand:
        pass

    @abc.abstractmethod
    @property
    def id(self):
        pass


class Status(object):
    SUCCESS = "success"
    ERROR_MULTIPLE_CARD_HOLDERS = "error_multiple_card_holders"  # Multiple card holders had the same card for the same company
    DEACTIVATE_CARD_NOT_FOUND = "deactivate_card_not_found"  # Card wasn't found for a deactivation request


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
            print("ERROR: Card holders > 1")
            sys.exit(1)

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
            print("ERROR: Card holders > 1")
            sys.exit(1)

        udf_id = card_holders[0].udf_id if len(card_holders) == 1 else uuid.uuid4()
        dsx_command.set_udf_id(udf_id)
        dsx_card = DSXCard(self.card_num)
        dsx_card.add_acl("MBD Access")
        dsx_card.disable()
        dsx_command.add_card(dsx_card)

        return dsx_command
