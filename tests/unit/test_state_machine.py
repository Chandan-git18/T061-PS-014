"""BR-20 to BR-24: freeze and restore."""
from datetime import date
from decimal import Decimal as D

from bnpl.authorisation import authorise_purchase
from bnpl.models import Bill, LineState, PaymentSource
from bnpl.payments import post_payment
from bnpl.state_machine import days_overdue, evaluate
from tests.conftest import ts


def add_bill(led, bill_id, bill_date, due, principal, fee="0.00", gst="0.00"):
    bill = Bill(bill_id, "U01", "x", bill_date, due, D(principal), D(fee), D(gst))
    led.bills.append(bill)
    return bill


def pay(led, txn, amount, when):
    return post_payment(led, txn, "U01", D(amount), ts(when), PaymentSource.MANUAL)


def frozen_ledger(make_ledger):
    """U01 (line 20,000) with one bill of 3,035.40 due 20 Jan 2027, never paid."""
    led = make_ledger()
    add_bill(led, "B1", date(2027, 1, 15), date(2027, 1, 20), "3000.00", "30.00", "5.40")
    return led


def test_days_overdue(make_ledger):
    led = frozen_ledger(make_ledger)
    assert days_overdue(led, "U01", date(2027, 1, 20)) == 0   # due date itself is not overdue
    assert days_overdue(led, "U01", date(2027, 1, 23)) == 3


def test_br_20_soft_freeze_at_3_days(make_ledger):
    led = frozen_ledger(make_ledger)
    evaluate(led, date(2027, 1, 22))
    assert led.users["U01"].state == LineState.ACTIVE          # 2 days overdue
    evaluate(led, date(2027, 1, 23))
    assert led.users["U01"].state == LineState.SOFT_FREEZE
    d = authorise_purchase(led, ts("2027-01-23T10:00:00"), "T1", "U01", "M01", D("10.00"))
    assert d.rule_ids == ["S01"]


def test_br_21_hard_freeze_at_30_days_reduces_line(make_ledger):
    led = frozen_ledger(make_ledger)
    evaluate(led, date(2027, 1, 23))
    evaluate(led, date(2027, 2, 18))                           # 29 days
    assert led.users["U01"].state == LineState.SOFT_FREEZE
    evaluate(led, date(2027, 2, 19))                           # 30 days
    user = led.users["U01"]
    assert user.state == LineState.HARD_FREEZE
    assert user.current_line == D("3035.40")                   # = total outstanding
    assert user.original_line == D("20000.00")
    assert led.available_line("U01") == D("0.00")


def test_br_21_data_gap_logs_every_step(make_ledger):
    led = frozen_ledger(make_ledger)
    evaluate(led, date(2027, 2, 19))                           # first check at 30 days
    assert [(s.from_state, s.to_state) for s in led.state_changes] == [
        (LineState.ACTIVE, LineState.SOFT_FREEZE),
        (LineState.SOFT_FREEZE, LineState.HARD_FREEZE)]


def test_br_22_closed_at_90_days_is_terminal(make_ledger):
    led = frozen_ledger(make_ledger)
    evaluate(led, date(2027, 4, 19))                           # 89 days
    assert led.users["U01"].state == LineState.HARD_FREEZE
    evaluate(led, date(2027, 4, 20))                           # 90 days
    assert led.users["U01"].state == LineState.CLOSED
    pay(led, "P1", "3035.40", "2027-04-21T10:00:00")           # payment accepted ...
    assert led.bills[0].is_paid
    assert led.users["U01"].state == LineState.CLOSED          # ... but no way back


def test_br_23_full_payment_in_soft_freeze_restores(make_ledger):
    led = frozen_ledger(make_ledger)
    evaluate(led, date(2027, 1, 23))
    pay(led, "P1", "3000.00", "2027-01-24T10:00:00")           # partial
    assert led.users["U01"].state == LineState.SOFT_FREEZE
    pay(led, "P2", "35.40", "2027-01-24T11:00:00")             # rest of it
    assert led.users["U01"].state == LineState.ACTIVE
    assert led.users["U01"].current_line == D("20000.00")      # SOFT never reduced the line


def test_br_24_three_on_time_bills_restore_line(make_ledger):
    led = frozen_ledger(make_ledger)
    evaluate(led, date(2027, 2, 19))                           # HARD_FREEZE
    pay(led, "P1", "3035.40", "2027-02-20T10:00:00")           # paid late
    user = led.users["U01"]
    assert user.state == LineState.ACTIVE                      # A-05
    assert user.current_line == D("3035.40") and user.on_time_streak == 0

    add_bill(led, "B2", date(2027, 2, 28), date(2027, 3, 5), "500.00")
    pay(led, "P2", "500.00", "2027-03-05T09:00:00")            # on the due date = on time
    add_bill(led, "B3", date(2027, 3, 15), date(2027, 3, 20), "500.00")
    pay(led, "P3", "500.00", "2027-03-18T09:00:00")
    assert user.on_time_streak == 2 and user.current_line == D("3035.40")
    add_bill(led, "B4", date(2027, 3, 31), date(2027, 4, 5), "500.00")
    pay(led, "P4", "500.00", "2027-04-02T09:00:00")
    assert user.current_line == D("20000.00") and not user.line_reduced
    assert led.state_changes[-1].trigger.startswith("BR-24")


def test_br_24_late_bill_resets_streak(make_ledger):
    led = frozen_ledger(make_ledger)
    evaluate(led, date(2027, 2, 19))
    pay(led, "P1", "3035.40", "2027-02-20T10:00:00")
    user = led.users["U01"]
    add_bill(led, "B2", date(2027, 2, 28), date(2027, 3, 5), "500.00")
    pay(led, "P2", "500.00", "2027-03-04T09:00:00")
    assert user.on_time_streak == 1
    add_bill(led, "B3", date(2027, 3, 15), date(2027, 3, 20), "500.00")
    evaluate(led, date(2027, 3, 21))                           # B3 overdue: streak broken
    assert user.on_time_streak == 0
    pay(led, "P3", "500.00", "2027-03-21T09:00:00")            # paid late
    assert user.on_time_streak == 0 and user.line_reduced
