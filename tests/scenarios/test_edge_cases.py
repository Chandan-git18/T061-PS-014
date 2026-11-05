"""The eight edge cases from the brief (E1 to E8, design document section 11).

Each one runs through the real parser and engine from small CSV inputs.
Users with mandate CANCELLED have no debit attempts, which keeps the numbers short.
"""
from datetime import date
from decimal import Decimal as D

from bnpl.models import DebitResult, LineState


def test_e1_cycle_boundary(run_scenario):
    """15th 23:59:59 is in C1 (bill 15 Jan); 16th 00:00:00 is in C2 (bill 31 Jan)."""
    led = run_scenario(
        users=["U01,FULL,20000.00,CANCELLED,2027-01-01"],
        commands=["2027-01-15T23:59:59,PURCHASE,T1,U01,M01,1000.00,",
                  "2027-01-16T00:00:00,PURCHASE,T2,U01,M01,500.00,"],
        until="2027-02-01")
    b1, b2 = led.bills
    assert (b1.cycle_id, b1.principal, b1.bill_date, b1.due_date) == \
        ("2027-01-C1", D("1000.00"), date(2027, 1, 15), date(2027, 1, 20))
    assert (b2.cycle_id, b2.principal, b2.bill_date, b2.due_date) == \
        ("2027-01-C2", D("500.00"), date(2027, 1, 31), date(2027, 2, 5))


def test_e2_fee_threshold(run_scenario):
    led = run_scenario(
        users=["U01,FULL,20000.00,CANCELLED,2027-01-01",
               "U02,FULL,20000.00,CANCELLED,2027-01-01"],
        commands=["2027-01-05T10:00:00,PURCHASE,T1,U01,M01,1000.00,",
                  "2027-01-05T10:00:00,PURCHASE,T2,U02,M01,1000.01,"],
        until="2027-01-16")
    b1, b2 = led.bills
    assert (b1.conv_fee, b1.conv_gst, b1.total) == (D("0.00"), D("0.00"), D("1000.00"))
    assert (b2.conv_fee, b2.conv_gst, b2.total) == (D("10.00"), D("1.80"), D("1011.81"))


def test_e3_refund_in_hard_freeze(run_scenario):
    """Refund of a purchase in a paid bill, after HARD_FREEZE: approved, becomes credit,
    pays the overdue bill at the next generation; the line stays reduced."""
    led = run_scenario(
        users=["U01,FULL,10000.00,CANCELLED,2027-01-01"],
        commands=[
            "2027-01-05T10:00:00,PURCHASE,T1,U01,M01,2000.00,",
            "2027-01-18T10:00:00,PAYMENT,P1,U01,,2023.60,",     # B0001 paid on time
            "2027-01-20T10:00:00,PURCHASE,T2,U01,M01,3000.00,",  # B0002, due 5 Feb, unpaid
            "2027-03-10T10:00:00,REFUND,R1,U01,M01,500.00,T1",   # after HARD (7 Mar)
        ],
        until="2027-03-16")
    user, b2 = led.users["U01"], led.bills[1]
    hard = [s for s in led.state_changes if s.to_state == LineState.HARD_FREEZE][0]
    assert hard.ts.date() == date(2027, 3, 7)
    # 3,000 + 30 fee + 5.40 GST + 150 late fee = 3,185.40
    assert user.current_line == D("3185.40")
    refund = led.decisions[-1]
    assert (refund.txn_id, refund.decision, refund.available_after) == \
        ("R1", "APPROVED", D("0.00"))                     # credit not in available line
    # 16 Mar: credit 500 pays late fee 150, fee 30, GST 5.40, principal 314.60
    assert b2.outstanding() == D("2685.40")
    assert user.credit_balance == D("0.00")
    assert user.state == LineState.HARD_FREEZE and user.current_line == D("3185.40")


def test_e4_mandate_cancel(run_scenario):
    led = run_scenario(
        users=["U01,FULL,20000.00,ACTIVE,2027-01-01"],
        commands=["2027-01-05T10:00:00,PURCHASE,T1,U01,M01,1500.00,",
                  "2027-01-23T12:00:00,MANDATE_CANCEL,MC1,U01,,,"],
        debits=["2027-01-20T08:00:00,U01,B0001,1,FAILED,1517.70",
                "2027-01-22T08:00:00,U01,B0001,2,FAILED,1517.70"],
        until="2027-01-26")
    bill = led.bills[0]
    assert [a.result for a in led.attempts] == \
        [DebitResult.FAILED, DebitResult.FAILED, DebitResult.SKIPPED]
    assert bill.bounce_total == D("50.00")      # only retry 1 charged
    assert bill.late_fee == D("50.00")          # still charged on due + 6


def test_e5_late_fee_cap(run_scenario):
    led = run_scenario(
        users=["U01,MIN,10000.00,CANCELLED,2027-01-01"],
        commands=["2027-01-05T10:00:00,PURCHASE,T1,U01,M01,400.00,"],
        until="2027-01-26")
    assert led.bills[0].late_fee == D("40.00")
    assert led.bills[0].total == D("440.00")


def test_e6_late_fee_boundary(run_scenario):
    """Paid at due + 5 days 23:59 -> no late fee. Paid at due + 6 days 00:00 -> the late
    fee is charged first (system events before commands), then the payment pays it first."""
    led = run_scenario(
        users=["U01,FULL,20000.00,CANCELLED,2027-01-01",
               "U02,FULL,20000.00,CANCELLED,2027-01-01"],
        commands=["2027-01-05T10:00:00,PURCHASE,T1,U01,M01,1500.00,",
                  "2027-01-05T10:00:00,PURCHASE,T2,U02,M01,1500.00,",
                  "2027-01-25T23:59:00,PAYMENT,P1,U01,,1517.70,",
                  "2027-01-26T00:00:00,PAYMENT,P2,U02,,1517.70,"],
        until="2027-01-27")
    b1, b2 = led.bills
    assert b1.late_fee == D("0.00") and b1.is_paid and b1.on_time is False
    assert b2.late_fee == D("50.00")
    assert b2.paid_by_component["late_fee"] == D("50.00")
    assert b2.outstanding() == D("50.00")        # 50 of principal still owed
    assert led.users["U01"].state == LineState.ACTIVE       # BR-23 restored
    assert led.users["U02"].state == LineState.SOFT_FREEZE  # still overdue


def test_e7_restore_with_credit_bill(run_scenario):
    """After HARD_FREEZE: three on-time bills, the second paid by refund credit only."""
    led = run_scenario(
        users=["U01,FULL,10000.00,CANCELLED,2027-01-01"],
        commands=[
            "2027-01-05T10:00:00,PURCHASE,T1,U01,M01,2000.00,",  # B0001, never paid on time
            "2027-02-20T10:00:00,PAYMENT,P1,U01,,2073.60,",      # after HARD (19 Feb)
            "2027-02-21T10:00:00,PURCHASE,T2,U01,M01,1000.00,",  # B0002, due 5 Mar
            "2027-03-02T10:00:00,PURCHASE,T3,U01,M02,600.00,",   # B0003, C1 Mar
            "2027-03-03T10:00:00,PAYMENT,P2,U01,,1000.00,",      # B0002 on time  -> 1
            "2027-03-04T10:00:00,REFUND,R1,U01,M01,600.00,T2",   # credit 600
            "2027-03-20T10:00:00,PURCHASE,T4,U01,M01,500.00,",   # B0004, due 5 Apr
            "2027-04-02T10:00:00,PAYMENT,P3,U01,,500.00,",       # B0004 on time  -> 3
        ],
        until="2027-04-03")
    user = led.users["U01"]
    b3 = led.bills[2]
    assert (b3.principal, b3.total, b3.paid_on, b3.on_time) == \
        (D("0.00"), D("0.00"), date(2027, 3, 15), True)      # paid by credit only -> 2
    restore = [s for s in led.state_changes if s.trigger.startswith("BR-24")]
    assert len(restore) == 1 and restore[0].ts.date() == date(2027, 4, 2)
    assert user.current_line == D("10000.00") and user.state == LineState.ACTIVE
    # line was 2,073.60 (outstanding at the freeze) until then
    line_on = {d: line for d, uid, _, line, _, _ in led.state_rows if uid == "U01"}
    assert line_on[date(2027, 4, 1)] == D("2073.60")
    assert line_on[date(2027, 4, 2)] == D("10000.00")


def test_e8_zero_refund_at_zero_available(run_scenario):
    led = run_scenario(
        users=["U01,MIN,8000.00,CANCELLED,2027-01-01"],
        commands=["2027-01-05T10:00:00,PURCHASE,T1,U01,M02,8000.00,",
                  "2027-01-06T10:00:00,REFUND,R1,U01,M02,0.00,T1"],
        until="2027-01-07")
    purchase, refund = led.decisions
    assert purchase.available_after == D("0.00")
    assert (refund.decision, refund.rule_ids, refund.available_after) == \
        ("DECLINED", ["V02"], D("0.00"))
    assert led.purchases["T1"].refunded_total == D("0.00")
