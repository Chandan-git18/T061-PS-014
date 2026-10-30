from datetime import date, datetime
from decimal import Decimal as D

import pytest

from bnpl.ledger import Ledger
from bnpl.models import Merchant
from bnpl.users import onboard

MERCHANTS = {"M01": "ELECTRONICS", "M02": "GROCERY", "M03": "FUEL",
             "M04": "GAMING", "M05": "CRYPTO"}


def ts(text: str) -> datetime:
    return datetime.fromisoformat(text)


@pytest.fixture
def make_ledger():
    """make_ledger(("U01", "FULL", "20000.00"), ...) -> Ledger with users and merchants."""
    def _make(*users):
        users = users or (("U01", "FULL", "20000.00"),)
        ledger = Ledger()
        for mid, cat in MERCHANTS.items():
            ledger.merchants[mid] = Merchant(mid, cat)
        for uid, kyc, line in users:
            assert onboard(ledger, uid, kyc, D(line), True, date(2027, 1, 1)).approved
        return ledger
    return _make
