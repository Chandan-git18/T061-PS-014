"""Auto-debit attempts (BR-14 to BR-16, A-13, A-14)."""
from . import rules
from .calendar import debit_schedule
from .models import DebitAttempt, DebitResult, PaymentSource
from .money import fmt


def schedule_attempts(ledger, bill):
    for n, at in enumerate(debit_schedule(bill.due_date), start=1):
        ledger.attempts.append(DebitAttempt(bill.bill_id, bill.user_id, n, at))


def run_attempt(ledger, attempt: DebitAttempt, results: dict):
    """Run one scheduled attempt. `results` maps (bill_id, attempt_no) -> 'SUCCESS'/'FAILED'."""
    from .payments import post_payment  # local import avoids a cycle

    bill = ledger.bill(attempt.bill_id)
    user = ledger.users[attempt.user_id]
    at = attempt.scheduled_at
    if bill.is_paid or not user.mandate_active:                     # skip rules, BR-16
        attempt.result = DebitResult.SKIPPED
        reason = "bill paid" if bill.is_paid else "mandate cancelled"
        ledger.log(user.user_id, at, f"DEBIT {bill.bill_id} #{attempt.attempt_no} "
                                     f"SKIPPED ({reason})")
        return attempt
    outcome = results.get((bill.bill_id, attempt.attempt_no))
    if outcome == "SUCCESS":
        amount = bill.outstanding()                                 # A-13
        attempt.result = DebitResult.SUCCESS
        ledger.log(user.user_id, at, f"DEBIT {bill.bill_id} #{attempt.attempt_no} "
                                     f"SUCCESS {fmt(amount)}")
        post_payment(ledger, f"AD-{bill.bill_id}-{attempt.attempt_no}", user.user_id,
                     amount, at, PaymentSource.AUTO_DEBIT)
        return attempt
    attempt.result = DebitResult.FAILED if outcome == "FAILED" else DebitResult.NO_RESPONSE
    if attempt.attempt_no > 1:                                      # BR-15
        bill.bounce_total += rules.BOUNCE_CHARGE
        attempt.bounce_charged = True
    ledger.log(user.user_id, at, f"DEBIT {bill.bill_id} #{attempt.attempt_no} "
                                 f"{attempt.result.value}"
                                 f"{' +bounce ' + fmt(rules.BOUNCE_CHARGE) if attempt.bounce_charged else ''}")
    return attempt
