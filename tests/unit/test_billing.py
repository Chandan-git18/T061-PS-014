"""BR-08 to BR-12 and BR-14: cycles, bills, fees, refunds and the debit schedule."""
from datetime import date, datetime
from decimal import Decimal as D

import pytest

from bnpl.authorisation import authorise_purchase, authorise_refund
from bnpl.billing import convenience_fee, generate_bills
from bnpl.calendar import cycle_of, debit_schedule, due_date_of
from bnpl.money import money
from tests.conftest import ts


def test_money_rounding():
    assert money("10.005") == D("10.01")   # ROUND_HALF_UP
    assert money("10.004") == D("10.00")


@pytest.mark.parametrize("when, cycle", [("2027-01-15T23:59:59", "2027-01-C1"),
                                         ("2027-01-16T00:00:00", "2027-01-C2"),
                                         ("2027-02-28T12:00:00", "2027-02-C2")])
def test_br_08_cycle_boundary(when, cycle):
    assert cycle_of(ts(when)) == cycle


@pytest.mark.parametrize("bill_date, due", [(date(2027, 1, 15), date(2027, 1, 20)),
                                            (date(2027, 1, 31), date(2027, 2, 5)),
                                            (date(2027, 2, 28), date(2027, 3, 5))])
def test_br_09_due_date(bill_date, due):
    assert due_date_of(bill_date) == due


@pytest.mark.parametrize("principal, fee, gst", [
    ("1000.00", "0.00", "0.00"),
    ("1000.01", "10.00", "1.80"),
    ("5000.00", "50.00", "9.00"),
    ("12000.00", "100.00", "18.00"),
])
def test_br_10_convenience_fee(principal, fee, gst):
    assert convenience_fee(D(principal)) == (D(fee), D(gst))


def test_br_10_bill_total_on_generation(make_ledger):
    led = make_ledger()
    authorise_purchase(led, ts("2027-01-10T10:00:00"), "T1", "U01", "M01", D("1000.01"))
    bill = generate_bills(led, "2027-01-C1", ts("2027-01-16T00:00:00"))[0]
    assert (bill.principal, bill.conv_fee, bill.conv_gst, bill.total) == \
        (D("1000.01"), D("10.00"), D("1.80"), D("1011.81"))
    assert (bill.bill_date, bill.due_date) == (date(2027, 1, 15), date(2027, 1, 20))


def test_br_11_refund_open_cycle(make_ledger):
    led = make_ledger()
    authorise_purchase(led, ts("2027-01-03T10:00:00"), "T1", "U01", "M01", D("4000.00"))
    authorise_refund(led, ts("2027-01-09T10:00:00"), "T2", "U01", D("500.00"), "T1")
    bill = generate_bills(led, "2027-01-C1", ts("2027-01-16T00:00:00"))[0]
    assert bill.principal == D("3500.00")
    assert led.users["U01"].credit_balance == D("0.00")


def test_br_12_refund_after_billing(make_ledger):
    led = make_ledger()
    authorise_purchase(led, ts("2027-01-03T10:00:00"), "T1", "U01", "M01", D("4000.00"))
    generate_bills(led, "2027-01-C1", ts("2027-01-16T00:00:00"))
    authorise_refund(led, ts("2027-01-20T10:00:00"), "T2", "U01", D("500.00"), "T1")
    assert led.users["U01"].credit_balance == D("500.00")
    authorise_purchase(led, ts("2027-01-22T10:00:00"), "T3", "U01", "M01", D("1000.00"))
    c2 = generate_bills(led, "2027-01-C2", ts("2027-02-01T00:00:00"))[0]
    assert c2.principal == D("500.00")
    assert led.users["U01"].credit_balance == D("0.00")


def test_no_activity_no_bill(make_ledger):
    """A-07: a cycle with no purchases produces no bill."""
    led = make_ledger()
    assert generate_bills(led, "2027-01-C1", ts("2027-01-16T00:00:00")) == []


def test_br_14_debit_schedule():
    assert debit_schedule(date(2027, 1, 20)) == [datetime(2027, 1, 20, 8),
                                                 datetime(2027, 1, 22, 8),
                                                 datetime(2027, 1, 25, 8)]
