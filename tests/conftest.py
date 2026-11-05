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
def run_scenario(tmp_path):
    """run_scenario(users=[...], commands=[...], debits=[...], until="YYYY-MM-DD") -> Ledger.

    Rows are CSV lines without the header. Runs through the real parser and engine.
    """
    from bnpl.engine import run_files

    def _run(users, commands, debits=(), until=None):
        files = {
            "users.csv": ["user_id,kyc,line,mandate,onboard_date", *users],
            "merchants.csv": ["merchant_id,category",
                              *(f"{m},{c}" for m, c in MERCHANTS.items())],
            "commands.csv": ["ts,type,txn_id,user_id,merchant_id,amount,ref_txn_id", *commands],
            "debits.csv": ["ts,user_id,bill_id,attempt_no,result,amount", *debits],
        }
        for name, lines in files.items():
            (tmp_path / name).write_text("\n".join(lines) + "\n")
        return run_files(tmp_path / "users.csv", tmp_path / "merchants.csv",
                         tmp_path / "commands.csv", tmp_path / "debits.csv",
                         date.fromisoformat(until) if until else None)
    return _run


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
