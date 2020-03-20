import abc
import logging
import sys
import uuid

from card_auto_add.card_access_system import CardAccessSystem, CardHolder
from card_auto_add.dsx import DSXCommand, DSXName, DSXCard


class Command(object):
    __metaclass__ = abc.ABCMeta

    STATUS_NOT_DONE = "not_done"
    STATUS_SUCCESS = "success"
    # Multiple card holders have the same name/company
    STATUS_ERROR_MULTIPLE_CARD_HOLDERS = "error_multiple_card_holders"
    # Card wasn't found for a deactivation request
    STATUS_DEACTIVATE_CARD_NOT_FOUND = "deactivate_card_not_found"

    @abc.abstractmethod
    def get_dsx_command(self) -> DSXCommand:
        pass

    @property
    @abc.abstractmethod
    def status(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def id(self):
        pass


class EnableCardCommand(Command):
    def __init__(self,
                 command_id,
                 first_name,
                 last_name,
                 company,
                 card_num,
                 cas: CardAccessSystem,
                 logger: logging.Logger):
        self.command_id = command_id
        self.first_name = first_name
        self.last_name = last_name
        self.company = company
        self.card_num = card_num
        self.cas = cas
        self.logger = logger

    @property
    def id(self):
        return self.command_id

    def get_dsx_command(self) -> DSXCommand:
        dsx_command = self.cas.new_command()

        card_holders = self.cas.get_card_holders_by_name(
            self.first_name,
            self.last_name,
            self.company
        )

        if len(card_holders) > 1:
            self.logger.info("ERROR: Card holders > 1")
            sys.exit(1)  # TODO Do NOT exit

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

    @property
    def status(self):
        card_holders = self.cas.get_card_holders_by_name(self.first_name, self.last_name, self.company)
        name_ids = list(dict.fromkeys([card_holder.name_id for card_holder in card_holders]))

        # Different name IDs mean we have different entries for the same name/company
        if len(name_ids) > 1:
            return self.STATUS_ERROR_MULTIPLE_CARD_HOLDERS

        self.logger.info(f"Status check card holders: {len(card_holders)}")
        card_holder: CardHolder
        for card_holder in card_holders:
            self.logger.info(f"Testing {card_holder.last_name}, {card_holder.first_name} with card {card_holder.card}")
            if (card_holder.card == self.card_num or
                card_holder.card == self.card_num.lstrip("0")) \
                    and card_holder.card_active:
                return self.STATUS_SUCCESS

        return self.STATUS_NOT_DONE


class DisableCardCommand(Command):
    def __init__(self,
                 command_id,
                 card_num,
                 company,
                 cas: CardAccessSystem,
                 logger: logging.Logger):
        self.command_id = command_id
        self.card_num = card_num
        self.company = company
        self.cas = cas
        self.logger = logger

    @property
    def id(self):
        return self.command_id

    def get_dsx_command(self) -> DSXCommand:
        dsx_command = self.cas.new_command()

        card_holders = self.cas.get_card_holders_by_card_num(self.company, self.card_num)

        if len(card_holders) > 1:
            self.logger.info("ERROR: Card holders > 1")
            sys.exit(1)  # TODO Do NOT exit

        udf_id = card_holders[0].udf_id if len(card_holders) == 1 else uuid.uuid4()
        dsx_command.set_udf_id(udf_id)
        dsx_card = DSXCard(self.card_num)
        dsx_card.add_acl("MBD Access")
        dsx_card.disable()
        dsx_command.add_card(dsx_card)

        return dsx_command

    @property
    def status(self):
        card_holders = self.cas.get_card_holders_by_card_num(self.company, self.card_num)
        name_ids = list(dict.fromkeys([card_holder.name_id for card_holder in card_holders]))

        # Different name IDs mean we have different entries for the same name/company
        if len(name_ids) > 1:
            return self.STATUS_ERROR_MULTIPLE_CARD_HOLDERS

        card_holder: CardHolder
        for card_holder in card_holders:
            if card_holder.card == self.card_num or card_holder.card == self.card_num.lstrip("0"):
                if not card_holder.card_active:
                    return self.STATUS_SUCCESS
                else:
                    return self.STATUS_NOT_DONE

        return self.STATUS_DEACTIVATE_CARD_NOT_FOUND
