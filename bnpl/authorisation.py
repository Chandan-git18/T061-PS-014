"""PURCHASE and REFUND checks (BR-02 to BR-07, BR-11 to BR-13, V01 to V04).

Checks run in a fixed order and every failed rule ID is reported (A-17).
An approved command changes the ledger; a declined one changes nothing.
"""
from datetime import datetime

from . import rules
from .calendar import cycle_of
from .models import Decision, LineState, Purchase, Refund, RefundType
from .money import fmt, is_valid_amount, money

STATE_RULE = {LineState.SOFT_FREEZE: rules.S01,
              LineState.HARD_FREEZE: rules.S02,
              LineState.CLOSED: rules.S03}


def _decide(ledger, ts, txn_id, user_id, kind, amount, failed):
    if failed and not rules.REPORT_ALL_RULE_IDS:
        failed = failed[:1]
    avail = ledger.available_line(user_id) if user_id in ledger.users else None
    amount_text = fmt(amount) if amount is not None and amount.is_finite() else ""
    d = Decision(ts.isoformat(), txn_id, user_id, kind, amount_text,
                 "DECLINED" if failed else "APPROVED", list(failed), avail)
    ledger.decisions.append(d)
    return d


def _validate(ledger, txn_id, user_id, amount, merchant_id=None, check_merchant=False):
    failed = []
    if user_id not in ledger.users:
        failed.append(rules.V01)
    if not is_valid_amount(amount):
        failed.append(rules.V02)
    if check_merchant:
        m = ledger.merchants.get(merchant_id)
        if m is None or not m.category:
            failed.append(rules.V03)
    if txn_id in ledger.txn_ids:
        failed.append(rules.V04)
    return failed


def authorise_purchase(ledger, ts: datetime, txn_id: str, user_id: str,
                       merchant_id: str, amount) -> Decision:
    failed = _validate(ledger, txn_id, user_id, amount, merchant_id, check_merchant=True)
    if failed:
        if rules.V04 not in failed:
            ledger.txn_ids.add(txn_id)
        return _decide(ledger, ts, txn_id, user_id, "PURCHASE", amount, failed)

    ledger.txn_ids.add(txn_id)
    user = ledger.users[user_id]
    category = ledger.merchants[merchant_id].category
    cycle_id = cycle_of(ts)

    if user.state in STATE_RULE:                                    # BR-07
        failed.append(STATE_RULE[user.state])
    if category in rules.BLOCKED_CATEGORIES:                        # BR-03
        failed.append(rules.M01)
    exempt = category == rules.GROCERY_CATEGORY and rules.GROCERY_EXEMPT_FROM_P01
    cap = min(money(user.current_line * rules.SINGLE_PURCHASE_PCT), rules.SINGLE_PURCHASE_ABS)
    if not exempt and amount > cap:                                 # BR-02
        failed.append(rules.P01)
    if category == rules.FUEL_CATEGORY and \
            ledger.fuel_net_in_cycle(user_id, cycle_id) + amount > rules.FUEL_CYCLE_CAP:
        failed.append(rules.M02)                                    # BR-04
    if ledger.available_line(user_id) - amount < 0:                 # BR-06
        failed.append(rules.L01)

    if not failed:
        ledger.purchases[txn_id] = Purchase(txn_id, user_id, merchant_id, category,
                                            money(amount), ts, cycle_id)
    d = _decide(ledger, ts, txn_id, user_id, "PURCHASE", amount, failed)
    ledger.log(user_id, ts, f"PURCHASE {txn_id} {category} {fmt(amount)} "
                            f"{d.decision} {'|'.join(d.rule_ids)}".rstrip())
    return d


def authorise_refund(ledger, ts: datetime, txn_id: str, user_id: str, amount,
                     ref_txn_id: str) -> Decision:
    failed = _validate(ledger, txn_id, user_id, amount)
    if failed:
        if rules.V04 not in failed:
            ledger.txn_ids.add(txn_id)
        return _decide(ledger, ts, txn_id, user_id, "REFUND", amount, failed)

    ledger.txn_ids.add(txn_id)
    purchase = ledger.purchases.get(ref_txn_id)
    if purchase is None or purchase.user_id != user_id:             # BR-13
        failed.append(rules.R02)
    elif purchase.refunded_total + amount > purchase.amount:
        failed.append(rules.R01)

    # No line-state check: refunds are accepted in every state (BR-07).
    if not failed:
        amount = money(amount)
        purchase.refunded_total += amount
        user = ledger.users[user_id]
        if purchase.billed_in is None:                              # BR-11
            purchase.refunded_before_bill += amount
            applied = RefundType.CYCLE_REDUCTION
        else:                                                       # BR-12
            user.credit_balance += amount
            applied = RefundType.CREDIT
        ledger.refunds[txn_id] = Refund(txn_id, ref_txn_id, user_id, amount, ts, applied)
    d = _decide(ledger, ts, txn_id, user_id, "REFUND", amount, failed)
    ledger.log(user_id, ts, f"REFUND {txn_id} of {ref_txn_id} {fmt(amount)} "
                            f"{d.decision} {'|'.join(d.rule_ids)}".rstrip())
    return d
