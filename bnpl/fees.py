"""Late fee (BR-17, BR-18, A-02)."""
from datetime import date, datetime, time, timedelta

from . import rules
from .money import ZERO, fmt, money


def late_fee_for(principal) -> "Decimal":
    """BR-17 tier by bill principal, then BR-18 cap at 10% of the bill.

    Rs 50 for bills <= 2,000, Rs 150 up to 5,000, Rs 300 above.
    Example: a Rs 400 bill gets min(50, 40) = Rs 40.
    """
    principal = money(principal)
    tier = rules.LATE_FEE_ABOVE
    for limit, fee in rules.LATE_FEE_TIERS:
        if principal <= limit:
            tier = fee
            break
    cap = money(principal * rules.LATE_FEE_CAP_PCT)
    return min(tier, cap)


def late_fee_day(bill) -> date:
    """The late fee is charged at 00:00:00 on due + 6 days, i.e. once due + 5 days is over."""
    return bill.due_date + timedelta(days=rules.LATE_FEE_DAYS_AFTER_DUE)


def charge_late_fees(ledger, day: date) -> list:
    """Charge each bill once, if any amount of it is still unpaid on its late-fee day."""
    charged = []
    at = datetime.combine(day, time())
    for bill in ledger.bills:
        if bill.late_fee_charged or bill.is_paid or day < late_fee_day(bill):
            continue
        bill.late_fee_charged = True
        fee = late_fee_for(bill.principal)
        if fee <= ZERO:
            continue
        bill.late_fee = fee
        charged.append(bill)
        ledger.log(bill.user_id, at, f"LATE_FEE {bill.bill_id} {fmt(fee)} "
                                     f"(principal {fmt(bill.principal)})")
    return charged
