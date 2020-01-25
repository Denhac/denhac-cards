from datetime import datetime
from io import TextIOBase


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
