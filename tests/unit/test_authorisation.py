"""BR-01 to BR-07 and BR-13: onboarding, purchase and refund checks."""
from datetime import date
from decimal import Decimal as D

import pytest

from bnpl.authorisation import authorise_purchase, authorise_refund
from bnpl.billing import generate_bills
from bnpl.ledger import Ledger
from bnpl.models import LineState
from bnpl.users import onboard
from tests.conftest import ts


def buy(ledger, txn, amount, merchant="M01", user="U01", when="2027-01-03T10:00:00"):
    return authorise_purchase(ledger, ts(when), txn, user, merchant, D(amount))


@pytest.mark.parametrize("kyc, line, approved", [
    ("MIN", "10000.00", True), ("MIN", "10000.01", False),
    ("FULL", "60000.00", True), ("FULL", "60000.01", False),
])
def test_br_01_onboarding_line_limit(kyc, line, approved):
    d = onboard(Ledger(), "U01", kyc, D(line), True, date(2027, 1, 1))
    assert d.approved is approved
    assert d.rule_ids == ([] if approved else ["O01"])


def test_br_02_single_purchase_cap(make_ledger):
    led = make_ledger(("U01", "FULL", "20000.00"), ("U02", "FULL", "40000.00"))
    assert buy(led, "T1", "10000.01").rule_ids == ["P01"]          # 50% of 20,000
    assert buy(led, "T2", "10000.00").approved
    assert buy(led, "T3", "15000.01", user="U02").rule_ids == ["P01"]  # Rs 15,000 ceiling


@pytest.mark.parametrize("merchant", ["M04", "M05"])  # GAMING, CRYPTO
def test_br_03_blocked_categories(make_ledger, merchant):
    led = make_ledger()
    d = buy(led, "T1", "100.00", merchant=merchant)
    assert d.rule_ids == ["M01"]
    assert d.available_after == D("20000.00")  # declined command changes nothing


def test_br_04_fuel_cycle_cap(make_ledger):
    led = make_ledger()
    assert buy(led, "T1", "1500.00", merchant="M03").approved
    assert buy(led, "T2", "500.00", merchant="M03").approved
    assert buy(led, "T3", "0.01", merchant="M03").rule_ids == ["M02"]


def test_br_05_grocery_full_line(make_ledger):
    led = make_ledger(("U01", "MIN", "8000.00"))
    d = buy(led, "T1", "8000.00", merchant="M02")  # above the 50% cap, GROCERY is exempt
    assert d.approved and d.available_after == D("0.00")
    assert buy(led, "T2", "0.01", merchant="M02").rule_ids == ["L01"]


def test_br_06_available_line(make_ledger):
    led = make_ledger(("U01", "FULL", "10000.00"))
    buy(led, "T1", "3000.00")                                       # C1
    generate_bills(led, "2027-01-C1", ts("2027-01-16T00:00:00"))  # 3,000 + 30.00 + 5.40
    buy(led, "T2", "2500.00", when="2027-01-17T10:00:00")           # C2
    authorise_refund(led, ts("2027-01-18T10:00:00"), "T3", "U01", D("500.00"), "T2")
    assert led.available_line("U01") == D("4964.60")
    assert buy(led, "T4", "4964.61", when="2027-01-19T10:00:00").rule_ids == ["L01"]
    d = buy(led, "T5", "4964.60", when="2027-01-19T10:00:00")
    assert d.approved and d.available_after == D("0.00")


@pytest.mark.parametrize("state, rule", [(LineState.SOFT_FREEZE, "S01"),
                                         (LineState.HARD_FREEZE, "S02"),
                                         (LineState.CLOSED, "S03")])
def test_br_07_purchase_only_active(make_ledger, state, rule):
    led = make_ledger()
    assert buy(led, "T1", "1000.00").approved
    led.users["U01"].state = state
    assert buy(led, "T2", "100.00").rule_ids == [rule]
    refund = authorise_refund(led, ts("2027-01-04T10:00:00"), "T3", "U01", D("100.00"), "T1")
    assert refund.approved  # refunds allowed in every state


def test_br_13_refund_limits(make_ledger):
    led = make_ledger(("U01", "FULL", "20000.00"), ("U02", "FULL", "20000.00"))
    buy(led, "T1", "4000.00")
    buy(led, "T2", "1000.00", user="U02")
    when = ts("2027-01-05T10:00:00")
    assert authorise_refund(led, when, "R1", "U01", D("2500.00"), "T1").approved
    assert authorise_refund(led, when, "R2", "U01", D("1500.01"), "T1").rule_ids == ["R01"]
    assert authorise_refund(led, when, "R3", "U01", D("100.00"), "T2").rule_ids == ["R02"]
    assert authorise_refund(led, when, "R4", "U01", D("100.00"), "T999").rule_ids == ["R02"]


def test_all_failed_rule_ids_reported(make_ledger):
    """A-17: every failed rule is reported in evaluation order."""
    led = make_ledger(("U01", "MIN", "1000.00"))
    buy(led, "T1", "400.00", merchant="M03")
    d = buy(led, "T2", "1700.00", merchant="M03")
    assert d.rule_ids == ["P01", "M02", "L01"]
