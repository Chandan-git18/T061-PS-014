"""Single simulated clock: walks day by day and runs events in a fixed order.

For each day D (design document, section 12):
  1. 00:00:00  if D is the 16th or the 1st, generate bills for the cycle that just ended.
  2. 00:00:00  if D is the 1st, write the bureau file for the previous month.
  3. 00:00:00  charge late fees on bills whose due + 5 days is over (BR-17).
  4. 00:00:00  check forward line-state moves for every user (BR-20 to BR-22).
  5. Debit attempts (08:00) and commands for D, in timestamp order.
     System events at an instant run before commands at the same instant.
     Every payment re-checks restoration (BR-23, BR-24).
  6. End of day: record each user's line state (line_states.csv).
"""
from datetime import date, datetime, time, timedelta

from .authorisation import authorise_purchase, authorise_refund
from .autodebit import run_attempt
from .billing import generate_bills
from .bureau import bureau_report
from .calendar import cycle_of, is_bill_generation_day
from .fees import charge_late_fees, late_fee_day
from .io.parser import read_commands, read_debit_results, read_merchants, read_users
from .ledger import Ledger
from .models import Merchant
from .payments import process_payment
from .state_machine import evaluate, snapshot
from .users import onboard


def next_generation_day(d: date) -> date:
    d += timedelta(days=1)
    while not is_bill_generation_day(d):
        d += timedelta(days=1)
    return d


def first_of_next_month(d: date) -> date:
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


class Engine:
    def __init__(self, ledger: Ledger, commands: list, debit_results: dict):
        self.ledger = ledger
        self.commands = commands
        self.results = debit_results

    def run(self, start: date, end: date):
        by_day = {}
        for c in self.commands:
            by_day.setdefault(c.ts.date(), []).append(c)
        day = start
        while day <= end:
            self.run_day(day, by_day.get(day, []))
            day += timedelta(days=1)
        return self.ledger

    def run_day(self, day: date, commands: list):
        led = self.ledger
        midnight = datetime.combine(day, time())
        yesterday = day - timedelta(days=1)
        if is_bill_generation_day(day):                              # step 1
            generate_bills(led, cycle_of(yesterday), midnight)
        if day.day == 1:                                             # step 2
            bureau_report(led, yesterday)
        charge_late_fees(led, day)                                   # step 3
        evaluate(led, day)                                           # step 4
        events = [(a.scheduled_at, 0, i, a) for i, a in enumerate(led.attempts)
                  if a.result is None and a.scheduled_at.date() == day]
        events += [(c.ts, 1, i, c) for i, c in enumerate(commands)]
        for _, kind, _, item in sorted(events, key=lambda e: e[:3]):   # step 5
            if kind == 0:
                run_attempt(led, item, self.results)
            else:
                self.apply(item)
        snapshot(led, day)                                           # step 6

    def apply(self, c):
        led = self.ledger
        if c.type == "PURCHASE":
            authorise_purchase(led, c.ts, c.txn_id, c.user_id, c.merchant_id, c.amount)
        elif c.type == "REFUND":
            authorise_refund(led, c.ts, c.txn_id, c.user_id, c.amount, c.ref_txn_id)
        elif c.type == "PAYMENT":
            process_payment(led, c.ts, c.txn_id, c.user_id, c.amount)
        elif c.type == "MANDATE_CANCEL":
            if c.user_id in led.users:
                led.users[c.user_id].mandate_active = False          # BR-16
                led.log(c.user_id, c.ts, f"MANDATE_CANCEL {c.txn_id}")


def build_ledger(users: list, merchants: list) -> Ledger:
    ledger = Ledger()
    for merchant_id, category in merchants:
        ledger.merchants[merchant_id] = Merchant(merchant_id, category)
    for u in users:
        d = onboard(ledger, u["user_id"], u["kyc"], u["line"], u["mandate_active"],
                    u["onboard_date"])
        if not d.approved:
            ledger.decisions.append(d)
    return ledger


def pending_until(ledger) -> date:
    """Last date on which something is still scheduled: a debit attempt or a late fee."""
    dates = [a.scheduled_at.date() for a in ledger.attempts if a.result is None]
    dates += [late_fee_day(b) for b in ledger.bills
              if not b.is_paid and not b.late_fee_charged]
    return max(dates) if dates else None


def run_files(users_path, merchants_path, commands_path, debits_path=None, until=None):
    ledger = build_ledger(read_users(users_path), read_merchants(merchants_path))
    commands, rejected = read_commands(commands_path)
    ledger.rejected = rejected
    results = read_debit_results(debits_path)

    dates = [c.ts.date() for c in commands]
    dates += [u.onboard_date for u in ledger.users.values() if u.onboard_date]
    if not dates:
        return ledger
    start = min(dates)
    last = max(c.ts.date() for c in commands) if commands else start
    # By default run to the 1st after the last command: the last cycle is billed and the
    # last month's bureau file is written.
    end = until or first_of_next_month(last)
    engine = Engine(ledger, commands, results)
    engine.run(start, end)
    # Then keep going while debit attempts or late fees are still pending.
    if until is None:
        extra = pending_until(ledger)
        if extra and extra > end:
            engine.run(end + timedelta(days=1), extra)
    return ledger
