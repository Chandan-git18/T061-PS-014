"""V01 to V05 input validation."""
from decimal import Decimal as D

import pytest

from bnpl.authorisation import authorise_purchase, authorise_refund
from bnpl.io.parser import read_commands
from tests.conftest import ts


def test_v01_unknown_user(make_ledger):
    led = make_ledger()
    d = authorise_purchase(led, ts("2027-01-03T10:00:00"), "T1", "U99", "M01", D("100.00"))
    assert d.rule_ids == ["V01"]


@pytest.mark.parametrize("amount", ["0.00", "-5.00", "10.001"])
def test_v02_amount(make_ledger, amount):
    led = make_ledger()
    d = authorise_purchase(led, ts("2027-01-03T10:00:00"), "T1", "U01", "M01", D(amount))
    assert d.rule_ids == ["V02"]
    assert led.available_line("U01") == D("20000.00")  # no state change


def test_v02_zero_refund(make_ledger):
    led = make_ledger()
    authorise_purchase(led, ts("2027-01-03T10:00:00"), "T1", "U01", "M01", D("100.00"))
    assert authorise_refund(led, ts("2027-01-04T10:00:00"), "T2", "U01", D("0"), "T1").rule_ids == ["V02"]


def test_v03_unknown_merchant(make_ledger):
    led = make_ledger()
    d = authorise_purchase(led, ts("2027-01-03T10:00:00"), "T1", "U01", "M99", D("100.00"))
    assert d.rule_ids == ["V03"]


def test_v04_duplicate_txn(make_ledger):
    led = make_ledger()
    assert authorise_purchase(led, ts("2027-01-03T10:00:00"), "T1", "U01", "M01", D("100.00")).approved
    d = authorise_purchase(led, ts("2027-01-03T11:00:00"), "T1", "U01", "M01", D("100.00"))
    assert d.rule_ids == ["V04"]


def test_v05_time_order_and_malformed(tmp_path):
    f = tmp_path / "commands.csv"
    f.write_text(
        "ts,type,txn_id,user_id,merchant_id,amount,ref_txn_id\n"
        "2027-01-05T10:00:00,PURCHASE,T1,U01,M01,100.00,\n"
        "2027-01-04T10:00:00,PURCHASE,T2,U01,M01,100.00,\n"   # earlier than previous
        "not-a-date,PURCHASE,T3,U01,M01,100.00,\n"            # bad timestamp
        "2027-01-06T10:00:00,PURCHASE,T4,U01\n"               # missing fields
        "2027-01-07T10:00:00,PURCHASE,T5,U01,M01,100.00,\n")
    commands, rejected = read_commands(f)
    assert [c.txn_id for c in commands] == ["T1", "T5"]
    assert [r.rule_id for r in rejected] == ["V05", "V05", "V05"]
