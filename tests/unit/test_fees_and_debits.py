"""BR-15 bounce charges, BR-16 mandate cancel, BR-17 late fee tiers, BR-18 late fee cap."""
from datetime import date
from decimal import Decimal as D

import pytest

from bnpl.authorisation import authorise_purchase
from bnpl.autodebit import run_attempt
from bnpl.billing import generate_bills
from bnpl.fees import charge_late_fees, late_fee_for
from bnpl.models import DebitResult
from tests.conftest import ts


def billed(led, amount="1500.00"):
    """One C1 purchase, billed on 16 Jan (due 20 Jan) with three debit attempts scheduled."""
    authorise_purchase(led, ts("2027-01-05T10:00:00"), "T1", "U01", "M01", D(amount))
    return generate_bills(led, "2027-01-C1", ts("2027-01-16T00:00:00"))[0]


def test_br_15_bounce_only_after_first_attempt(make_ledger):
    led = make_ledger()
    bill = billed(led)
    results = {(bill.bill_id, 1): "FAILED", (bill.bill_id, 2): "FAILED",
               (bill.bill_id, 3): "FAILED"}
    run_attempt(led, led.attempts[0], results)
    assert bill.bounce_total == D("0.00")          # first failure is free
    run_attempt(led, led.attempts[1], results)
    assert bill.bounce_total == D("50.00")
    run_attempt(led, led.attempts[2], results)
    assert bill.bounce_total == D("100.00")
    assert [a.bounce_charged for a in led.attempts] == [False, True, True]


def test_br_15_no_response_counts_as_failed(make_ledger):
    """A-14: a scheduled attempt with no result line is treated as FAILED."""
    led = make_ledger()
    bill = billed(led)
    run_attempt(led, led.attempts[1], {})
    assert led.attempts[1].result == DebitResult.NO_RESPONSE
    assert bill.bounce_total == D("50.00")


def test_br_16_no_attempt_after_mandate_cancel(make_ledger):
    led = make_ledger()
    bill = billed(led)
    led.users["U01"].mandate_active = False
    run_attempt(led, led.attempts[1], {(bill.bill_id, 2): "FAILED"})
    assert led.attempts[1].result == DebitResult.SKIPPED
    assert bill.bounce_total == D("0.00")


def test_br_16_no_schedule_when_mandate_cancelled(make_ledger):
    led = make_ledger()
    led.users["U01"].mandate_active = False
    billed(led)
    assert led.attempts == []


@pytest.mark.parametrize("principal, fee", [
    ("2000.00", "50.00"),    # top of tier 1
    ("2000.01", "150.00"),   # tier 2
    ("5000.00", "150.00"),   # top of tier 2
    ("5000.01", "300.00"),   # tier 3
    ("12000.00", "300.00"),
])
def test_br_17_late_fee_tiers(principal, fee):
    assert late_fee_for(D(principal)) == D(fee)


@pytest.mark.parametrize("principal, fee", [
    ("400.00", "40.00"),     # edge case E5: min(50, 40)
    ("100.00", "10.00"),
    ("250.05", "25.01"),     # 25.005 rounded half-up
    ("499.99", "50.00"),     # 49.999 rounds to 50.00, same as the tier
    ("500.00", "50.00"),     # cap no longer bites from here on
])
def test_br_18_late_fee_cap(principal, fee):
    assert late_fee_for(D(principal)) == D(fee)


def test_br_17_late_fee_charged_once_after_due_plus_5(make_ledger):
    led = make_ledger()
    led.users["U01"].mandate_active = False
    bill = billed(led, "3000.00")
    charge_late_fees(led, date(2027, 1, 25))       # due + 5: still inside the grace
    assert bill.late_fee == D("0.00")
    charge_late_fees(led, date(2027, 1, 26))       # due + 6, 00:00
    assert bill.late_fee == D("150.00")
    charge_late_fees(led, date(2027, 1, 27))
    assert bill.late_fee == D("150.00")            # charged once only


def test_br_17_no_late_fee_on_paid_bill(make_ledger):
    from bnpl.payments import process_payment
    led = make_ledger()
    led.users["U01"].mandate_active = False
    bill = billed(led, "3000.00")
    process_payment(led, ts("2027-01-22T10:00:00"), "P1", "U01", bill.total)
    charge_late_fees(led, date(2027, 1, 26))
    assert bill.late_fee == D("0.00")
