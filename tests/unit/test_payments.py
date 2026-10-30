"""BR-19 allocation, A-15 overpayment and auto-debit success / skip."""
from datetime import date
from decimal import Decimal as D

from bnpl.authorisation import authorise_purchase
from bnpl.autodebit import run_attempt
from bnpl.billing import generate_bills
from bnpl.models import Bill, DebitResult, PaymentSource
from bnpl.payments import post_payment, process_payment
from tests.conftest import ts


def test_br_19_allocation(make_ledger):
    led = make_ledger()
    b1 = Bill("B1", "U01", "2027-01-C1", date(2027, 1, 15), date(2027, 1, 20),
              D("2000.00"), D("20.00"), D("3.60"), late_fee=D("150.00"), bounce_total=D("50.00"))
    b2 = Bill("B2", "U01", "2027-01-C2", date(2027, 1, 31), date(2027, 2, 5),
              D("1000.00"), D("0.00"), D("0.00"))
    led.bills += [b1, b2]
    p = post_payment(led, "P1", "U01", D("300.00"), ts("2027-02-02T10:00:00"),
                     PaymentSource.MANUAL)
    assert [(a.bill_id, a.component, a.amount) for a in p.allocations] == [
        ("B1", "bounce_total", D("50.00")),
        ("B1", "late_fee", D("150.00")),
        ("B1", "conv_fee", D("20.00")),
        ("B1", "conv_gst", D("3.60")),
        ("B1", "principal", D("76.40")),
    ]
    assert b2.outstanding() == D("1000.00")  # untouched
    assert sum(a.amount for a in p.allocations) == D("300.00")


def test_br_19_overpayment_credit(make_ledger):
    led = make_ledger()
    authorise_purchase(led, ts("2027-01-03T10:00:00"), "T1", "U01", "M02", D("800.00"))
    bill = generate_bills(led, "2027-01-C1", ts("2027-01-16T00:00:00"))[0]
    assert process_payment(led, ts("2027-01-18T10:00:00"), "P1", "U01", D("1000.00")) is None
    assert bill.is_paid and bill.on_time and bill.paid_on == date(2027, 1, 18)
    assert led.users["U01"].credit_balance == D("200.00")


def test_auto_debit_success_pays_bill(make_ledger):
    led = make_ledger()
    authorise_purchase(led, ts("2027-01-03T10:00:00"), "T1", "U01", "M01", D("7000.00"))
    bill = generate_bills(led, "2027-01-C1", ts("2027-01-16T00:00:00"))[0]
    first = led.attempts[0]
    run_attempt(led, first, {(bill.bill_id, 1): "SUCCESS"})
    assert first.result == DebitResult.SUCCESS
    assert bill.is_paid and bill.on_time
    assert led.available_line("U01") == D("20000.00")
    run_attempt(led, led.attempts[1], {})
    assert led.attempts[1].result == DebitResult.SKIPPED  # bill already paid, no charge
    assert bill.bounce_total == D("0.00")
