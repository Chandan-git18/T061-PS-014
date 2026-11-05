"""BR-25 DPD and BR-26 amount reported (GST excluded)."""
from datetime import date
from decimal import Decimal as D

from bnpl.bureau import amount_reported, bureau_report
from bnpl.models import Bill, PaymentSource
from bnpl.payments import post_payment
from tests.conftest import ts


def two_bills(led):
    b1 = Bill("B1", "U01", "2027-01-C1", date(2027, 1, 15), date(2027, 1, 20),
              D("3000.00"), D("30.00"), D("5.40"))
    b2 = Bill("B2", "U01", "2027-01-C2", date(2027, 1, 31), date(2027, 2, 5),
              D("1000.00"), D("0.00"), D("0.00"))
    led.bills += [b1, b2]
    return b1, b2


def test_br_25_dpd_from_earliest_unpaid_due_date(make_ledger):
    led = make_ledger()
    two_bills(led)
    post_payment(led, "P1", "U01", D("1000.00"), ts("2027-01-25T10:00:00"),
                 PaymentSource.MANUAL)                       # B1 part-paid
    row = bureau_report(led, date(2027, 1, 31))[0]
    assert row.dpd == 11                                     # 31 Jan - 20 Jan


def test_br_25_dpd_zero_when_nothing_overdue(make_ledger):
    led = make_ledger()
    two_bills(led)
    post_payment(led, "P1", "U01", D("3035.40"), ts("2027-01-19T10:00:00"),
                 PaymentSource.MANUAL)                       # B1 paid, B2 not yet due
    row = bureau_report(led, date(2027, 1, 31))[0]
    assert row.dpd == 0
    assert row.amount_reported == D("1000.00")               # not overdue, still owed


def test_br_26_amount_excludes_gst(make_ledger):
    led = make_ledger()
    b1, _ = two_bills(led)
    b1.late_fee, b1.bounce_total = D("150.00"), D("50.00")
    # 3,000 + 30 fee + 150 late + 50 bounce + 1,000 = 4,230.00; the 5.40 GST is left out
    assert amount_reported(led, "U01") == D("4230.00")
    led.users["U01"].credit_balance = D("230.00")
    assert amount_reported(led, "U01") == D("4000.00")       # credit is netted off


def test_bureau_file_written_on_the_1st(run_scenario):
    led = run_scenario(
        users=["U01,FULL,20000.00,CANCELLED,2027-01-01"],
        commands=["2027-01-05T10:00:00,PURCHASE,T1,U01,M01,3000.00,"],
        until="2027-02-01")
    assert list(led.bureau_reports) == ["2027-01"]
    row = led.bureau_reports["2027-01"][0]
    # 3,000 principal + 30 fee + 150 late fee (26 Jan); GST 5.40 excluded
    assert (row.line_state, row.dpd, row.amount_reported) == ("SOFT_FREEZE", 11, D("3180.00"))
