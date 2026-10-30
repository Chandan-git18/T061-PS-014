"""Single simulated clock: walks day by day and runs events in a fixed order.

For each day D:
  1. 00:00:00  if D is the 16th or the 1st, generate bills for the cycle that just ended.
  2. Then debit attempts (08:00) and commands for D, in timestamp order.
     System events at an instant run before commands at the same instant.
"""
from datetime import date, datetime, time, timedelta

from .authorisation import authorise_purchase, authorise_refund
from .autodebit import run_attempt
from .billing import generate_bills
from .calendar import cycle_of, is_bill_generation_day
from .io.parser import read_commands, read_debit_results, read_merchants, read_users
from .ledger import Ledger
from .models import Merchant
from .payments import process_payment
from .users import onboard


def next_generation_day(d: date) -> date:
    d += timedelta(days=1)
    while not is_bill_generation_day(d):
        d += timedelta(days=1)
    return d


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
            midnight = datetime.combine(day, time())
            if is_bill_generation_day(day):
                generate_bills(self.ledger, cycle_of(day - timedelta(days=1)), midnight)
            events = [(a.scheduled_at, 0, i, a) for i, a in enumerate(self.ledger.attempts)
                      if a.result is None and a.scheduled_at.date() == day]
            events += [(c.ts, 1, i, c) for i, c in enumerate(by_day.get(day, []))]
            for _, kind, _, item in sorted(events, key=lambda e: e[:3]):
                if kind == 0:
                    run_attempt(self.ledger, item, self.results)
                else:
                    self.apply(item)
            day += timedelta(days=1)
        return self.ledger

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
                led.users[c.user_id].mandate_active = False
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
    # Run to the next bill-generation day after the last command, so the open cycle is billed.
    end = until or next_generation_day(max(c.ts.date() for c in commands) if commands else start)
    engine = Engine(ledger, commands, results)
    engine.run(start, end)
    # Keep going while debit attempts for bills already generated are still pending.
    if until is None:
        pending = [a.scheduled_at.date() for a in ledger.attempts if a.result is None]
        if pending:
            engine.run(end + timedelta(days=1), max(pending))
    return ledger
