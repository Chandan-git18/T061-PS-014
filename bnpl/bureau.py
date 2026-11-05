"""Month-end bureau file (BR-25, BR-26).

Written at 00:00:00 on the 1st, right after the month-end bill is generated and before
that day's late fees and state checks, so it shows every user as of the last day of the
previous month.
"""
from datetime import date

from .models import BureauRow
from .money import ZERO, money
from .state_machine import days_overdue

REPORTED_COMPONENTS = ("principal", "conv_fee", "late_fee", "bounce_total")  # no conv_gst


def amount_reported(ledger, user_id: str):
    """BR-26: unpaid principal + convenience fee + late fees + bounce, GST excluded,
    plus any unbilled balance, minus credit balance, never below 0."""
    owed = sum((b.outstanding(c) for b in ledger.user_bills(user_id)
                for c in REPORTED_COMPONENTS), ZERO)
    owed += ledger.unbilled_net(user_id)
    return max(ZERO, money(owed - ledger.users[user_id].credit_balance))


def bureau_report(ledger, last_day: date) -> list:
    month = f"{last_day.year:04d}-{last_day.month:02d}"
    rows = []
    for user_id in sorted(ledger.users):
        user = ledger.users[user_id]
        if user.onboard_date and user.onboard_date > last_day:
            continue
        rows.append(BureauRow(month, user_id, user.kyc.value, user.original_line,
                              user.current_line, user.state.value,
                              amount_reported(ledger, user_id),
                              days_overdue(ledger, user_id, last_day)))   # BR-25
    if rows:  # no file for a month before anyone was onboarded
        ledger.bureau_reports[month] = rows
    return rows
