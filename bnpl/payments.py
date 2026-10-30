"""Payment allocation and credit balance (BR-19, A-15)."""
from datetime import datetime

from . import rules
from .models import Allocation, Decision, Payment, PaymentSource
from .money import ZERO, fmt, is_valid_amount, money


def allocate(ledger, user_id: str, amount, ts: datetime):
    """Fill components in BR-19 order, oldest bill first within each component.

    Returns (allocations, excess). Bills that become fully paid get paid_on/on_time.
    """
    remaining = money(amount)
    bills = ledger.user_bills(user_id, unpaid_only=True)
    allocations = []
    for component in rules.ALLOCATION_ORDER:
        for bill in bills:
            if remaining <= 0:
                break
            take = min(bill.outstanding(component), remaining)
            if take > 0:
                bill.paid_by_component[component] += take
                remaining -= take
                allocations.append(Allocation(bill.bill_id, component, take))
    for bill in bills:
        if bill.is_paid and bill.paid_on is None:
            bill.paid_on = ts.date()
            bill.on_time = bill.paid_on <= bill.due_date
    return allocations, remaining


def post_payment(ledger, txn_id: str, user_id: str, amount, ts: datetime,
                 source: PaymentSource) -> Payment:
    allocations, excess = allocate(ledger, user_id, amount, ts)
    ledger.users[user_id].credit_balance += excess                  # A-15
    payment = Payment(txn_id, user_id, money(amount), ts, source, allocations)
    ledger.payments.append(payment)
    parts = ", ".join(f"{a.bill_id}.{a.component}={fmt(a.amount)}" for a in allocations)
    extra = f", credit +{fmt(excess)}" if excess > 0 else ""
    ledger.log(user_id, ts, f"PAYMENT {txn_id} {source.value} {fmt(amount)} -> "
                            f"[{parts}{extra}]")
    return payment


def apply_credit(ledger, user_id: str, ts: datetime):
    """A-09: leftover credit pays older unpaid bills, the rest carries forward."""
    user = ledger.users[user_id]
    if user.credit_balance <= 0 or not ledger.user_bills(user_id, unpaid_only=True):
        return None
    credit = user.credit_balance
    user.credit_balance = ZERO
    return post_payment(ledger, f"CR-{user_id}-{ts:%Y%m%d}", user_id, credit, ts,
                        PaymentSource.REFUND_CREDIT)


def process_payment(ledger, ts: datetime, txn_id: str, user_id: str, amount):
    """Manual PAYMENT command. Returns a Decision only when it is declined."""
    failed = []
    if user_id not in ledger.users:
        failed.append(rules.V01)
    if not is_valid_amount(amount):
        failed.append(rules.V02)
    if txn_id in ledger.txn_ids:
        failed.append(rules.V04)
    if failed:
        avail = ledger.available_line(user_id) if user_id in ledger.users else None
        d = Decision(ts.isoformat(), txn_id, user_id, "PAYMENT",
                     fmt(amount) if amount is not None and amount.is_finite() else "",
                     "DECLINED", failed, avail)
        ledger.decisions.append(d)
        return d
    ledger.txn_ids.add(txn_id)
    post_payment(ledger, txn_id, user_id, amount, ts, PaymentSource.MANUAL)
    return None
