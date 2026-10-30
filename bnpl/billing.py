"""Bill generation, convenience fee and GST (BR-08 to BR-12, A-07, A-09)."""
from datetime import datetime

from . import rules
from .autodebit import schedule_attempts
from .calendar import bill_date_of, due_date_of
from .models import Bill
from .money import ZERO, fmt, money
from .payments import apply_credit


def convenience_fee(principal):
    """BR-10: 0 if bill <= Rs 1,000; else 1% of the bill, max Rs 100.
    The fee is rounded first, then 18% GST is computed on the rounded fee."""
    principal = money(principal)
    if principal <= rules.CONV_FEE_THRESHOLD:
        return ZERO, ZERO
    fee = min(money(principal * rules.CONV_FEE_RATE), rules.CONV_FEE_MAX)
    gst = money(fee * rules.GST_RATE)
    return fee, gst


def generate_bills(ledger, cycle_id: str, gen_ts: datetime) -> list:
    """Generate one bill per user who had purchases in the cycle.

    Runs at 00:00:00 on the day after the cycle ends, before any command at that instant.
    """
    bill_date = bill_date_of(cycle_id)
    created = []
    for user_id in sorted(ledger.users):
        user = ledger.users[user_id]
        purchases = [p for p in ledger.purchases.values()
                     if p.user_id == user_id and p.cycle_id == cycle_id
                     and p.billed_in is None]
        if not purchases:                                           # A-07
            continue
        gross = sum((p.net_unbilled for p in purchases), ZERO)      # BR-11
        credit_used = min(user.credit_balance, gross)               # BR-12
        user.credit_balance -= credit_used
        principal = money(gross - credit_used)
        fee, gst = convenience_fee(principal)                       # BR-10
        bill = Bill(ledger.next_bill_id(), user_id, cycle_id, bill_date,
                    due_date_of(bill_date), principal, fee, gst)    # BR-09
        for p in purchases:
            p.billed_in = bill.bill_id
        ledger.bills.append(bill)
        created.append(bill)
        credit_note = f" credit used {fmt(credit_used)}" if credit_used > 0 else ""
        ledger.log(user_id, gen_ts,
                   f"BILL {bill.bill_id} {cycle_id} principal={fmt(principal)} "
                   f"fee={fmt(fee)} gst={fmt(gst)} total={fmt(bill.total)} "
                   f"due={bill.due_date.isoformat()}{credit_note}")
        apply_credit(ledger, user_id, gen_ts)                       # A-09
        if bill.total == 0 and bill.paid_on is None:
            bill.paid_on, bill.on_time = bill_date, True            # A-07
        if not bill.is_paid and user.mandate_active:
            schedule_attempts(ledger, bill)
    return created
