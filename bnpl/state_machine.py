"""Line state machine: freeze and restore (BR-20 to BR-24, A-05, A-06).

    ACTIVE --3 days overdue--> SOFT_FREEZE --30 days--> HARD_FREEZE --90 days--> CLOSED

Forward moves are checked once a day at 00:00:00 (`evaluate`).
Backward moves are checked after every payment or refund credit (`after_payment`):
  - SOFT_FREEZE -> ACTIVE when no bill is overdue any more (BR-23).
  - HARD_FREEZE -> ACTIVE when no bill is overdue, but the line stays reduced (A-05).
  - The original line comes back after 3 consecutive on-time bills (BR-24).
CLOSED is terminal.
"""
from datetime import date, datetime, time

from . import rules
from .models import LineState, StateChange
from .money import ZERO, fmt, money


def days_overdue(ledger, user_id: str, on: date) -> int:
    """Days past the earliest due date among unpaid bills; 0 if nothing is overdue."""
    dues = [b.due_date for b in ledger.user_bills(user_id, unpaid_only=True)]
    if not dues:
        return 0
    return max(0, (on - min(dues)).days)


def total_outstanding(ledger, user_id: str):
    """Everything the user owes: unpaid bill components (GST included) + unbilled purchases."""
    billed = sum((b.outstanding() for b in ledger.user_bills(user_id)), ZERO)
    return money(billed + ledger.unbilled_net(user_id))


def _move(ledger, user, to: LineState, ts: datetime, trigger: str):
    ledger.state_changes.append(StateChange(ts, user.user_id, user.state, to,
                                            user.current_line, trigger))
    ledger.log(user.user_id, ts, f"STATE {user.state.value} -> {to.value} ({trigger}) "
                                 f"line={fmt(user.current_line)}")
    user.state = to


def evaluate(ledger, day: date):
    """Forward transitions at 00:00:00 of `day` (BR-20, BR-21, BR-22)."""
    ts = datetime.combine(day, time())
    for user_id in sorted(ledger.users):
        user = ledger.users[user_id]
        if user.state == LineState.CLOSED:
            continue
        dpd = days_overdue(ledger, user_id, day)
        if dpd > 0 and user.line_reduced:
            user.on_time_streak = 0  # an overdue bill breaks the BR-24 streak
        # Each step is logged even if a gap in the data makes the user skip a state.
        if dpd >= rules.SOFT_FREEZE_DAYS and user.state == LineState.ACTIVE:
            _move(ledger, user, LineState.SOFT_FREEZE, ts, f"BR-20 {dpd} days overdue")
        if dpd >= rules.HARD_FREEZE_DAYS and user.state == LineState.SOFT_FREEZE:
            hard_freeze(ledger, user, ts, dpd)
        if dpd >= rules.CLOSED_DAYS and user.state == LineState.HARD_FREEZE:
            _move(ledger, user, LineState.CLOSED, ts, f"BR-22 {dpd} days overdue")


def hard_freeze(ledger, user, ts: datetime, dpd: int):
    """BR-21: line reduced to the current outstanding, so available line becomes 0."""
    user.current_line = total_outstanding(ledger, user.user_id)
    user.line_reduced = True
    user.on_time_streak = 0
    _move(ledger, user, LineState.HARD_FREEZE, ts, f"BR-21 {dpd} days overdue")


def mark_paid(ledger, bill, when: date):
    """Record that a bill is fully paid and update the BR-24 on-time streak."""
    bill.paid_on = when
    bill.on_time = when <= bill.due_date
    user = ledger.users[bill.user_id]
    if user.line_reduced:
        user.on_time_streak = user.on_time_streak + 1 if bill.on_time else 0


def after_payment(ledger, user_id: str, ts: datetime):
    """Backward transitions after a payment or refund credit (BR-23, A-05, BR-24)."""
    user = ledger.users[user_id]
    if user.state == LineState.CLOSED:
        return
    overdue = days_overdue(ledger, user_id, ts.date()) > 0
    if user.state == LineState.SOFT_FREEZE and not overdue:
        _move(ledger, user, LineState.ACTIVE, ts, "BR-23 overdue bills paid in full")
    elif user.state == LineState.HARD_FREEZE and not overdue:
        _move(ledger, user, LineState.ACTIVE, ts, "A-05 overdue cleared, line stays reduced")
    check_restore(ledger, user, ts)


def check_restore(ledger, user, ts: datetime):
    """BR-24: after 3 consecutive on-time bills, the original line comes back."""
    if (user.state == LineState.ACTIVE and user.line_reduced
            and user.on_time_streak >= rules.RESTORE_ON_TIME_BILLS):
        user.current_line = user.original_line
        user.line_reduced = False
        user.on_time_streak = 0
        ledger.state_changes.append(StateChange(ts, user.user_id, user.state, user.state,
                                                user.current_line, "BR-24 original line restored"))
        ledger.log(user.user_id, ts, f"LINE_RESTORED line={fmt(user.current_line)} (BR-24)")


def snapshot(ledger, day: date):
    """End-of-day line state for every onboarded user (line_states.csv)."""
    for user_id in sorted(ledger.users):
        user = ledger.users[user_id]
        if user.onboard_date and user.onboard_date > day:
            continue
        ledger.state_rows.append((day, user_id, user.state.value, user.current_line,
                                  ledger.available_line(user_id),
                                  days_overdue(ledger, user_id, day)))
