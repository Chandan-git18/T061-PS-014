"""Billing cycles, bill dates and due dates (BR-08, BR-09, BR-14)."""
from datetime import date, datetime, time, timedelta

from . import rules


def cycle_of(d: date) -> str:
    """BR-08: C1 = 1st-15th, C2 = 16th-month end. Decided by the date part only."""
    if isinstance(d, datetime):
        d = d.date()
    return f"{d.year:04d}-{d.month:02d}-C{1 if d.day <= 15 else 2}"


def month_end(d: date) -> date:
    first_next = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return first_next - timedelta(days=1)


def cycle_bounds(cycle_id: str) -> tuple:
    """Return (start_date, end_date) of a cycle such as 2027-01-C1."""
    year, month, half = int(cycle_id[0:4]), int(cycle_id[5:7]), cycle_id[8:]
    if half == "C1":
        return date(year, month, 1), date(year, month, 15)
    start = date(year, month, 16)
    return start, month_end(start)


def bill_date_of(cycle_id: str) -> date:
    """BR-09: the bill is dated on the cycle end date."""
    return cycle_bounds(cycle_id)[1]


def due_date_of(bill_date: date) -> date:
    """BR-09: due date = bill date + 5 days."""
    return bill_date + timedelta(days=rules.DUE_DAYS_AFTER_BILL)


def is_bill_generation_day(d: date) -> bool:
    """Bills are generated at 00:00:00 on the day after a cycle ends (16th and 1st)."""
    return d.day in (1, 16)


def debit_schedule(due: date) -> list:
    """BR-14: attempts at due date, due + 2 and due + 5 days, all at 08:00."""
    return [datetime.combine(due + timedelta(days=off), time(rules.DEBIT_HOUR))
            for off in rules.DEBIT_DAY_OFFSETS]
