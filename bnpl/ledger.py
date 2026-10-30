"""The ledger: all state for one run, plus available-line math (BR-06)."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from .money import ZERO, money, fmt
from .rules import FUEL_CATEGORY


class Ledger:
    def __init__(self):
        self.users = {}       # user_id -> User
        self.merchants = {}   # merchant_id -> Merchant
        self.purchases = {}   # txn_id -> Purchase
        self.refunds = {}     # txn_id -> Refund
        self.bills = []       # in generation order
        self.payments = []
        self.attempts = []    # DebitAttempt
        self.txn_ids = set()  # every transaction ID seen (V04)
        self.decisions = []   # Decision lines for decisions.csv
        self.rejected = []    # malformed input lines (V05)
        self.log_lines = defaultdict(list)  # user_id -> ledger print lines
        self._bill_seq = 0

    # ---- lookups -------------------------------------------------------
    def next_bill_id(self) -> str:
        self._bill_seq += 1
        return f"B{self._bill_seq:04d}"

    def bill(self, bill_id: str):
        return next(b for b in self.bills if b.bill_id == bill_id)

    def user_bills(self, user_id: str, unpaid_only: bool = False) -> list:
        """Bills of a user, oldest first."""
        bills = [b for b in self.bills if b.user_id == user_id]
        if unpaid_only:
            bills = [b for b in bills if not b.is_paid]
        return sorted(bills, key=lambda b: (b.bill_date, b.bill_id))

    # ---- available line (BR-06) ---------------------------------------
    def unbilled_net(self, user_id: str) -> Decimal:
        """Approved purchases not yet billed, minus refunds against them."""
        return sum((p.net_unbilled for p in self.purchases.values()
                    if p.user_id == user_id and p.billed_in is None), ZERO)

    def unpaid_principal(self, user_id: str) -> Decimal:
        return sum((b.outstanding("principal") for b in self.user_bills(user_id)), ZERO)

    def unpaid_fees(self, user_id: str) -> Decimal:
        return sum((b.outstanding() - b.outstanding("principal")
                    for b in self.user_bills(user_id)), ZERO)

    def available_line(self, user_id: str) -> Decimal:
        """Recomputed on every call from the transactions, never stored."""
        user = self.users[user_id]
        return money(user.current_line - self.unbilled_net(user_id)
                     - self.unpaid_principal(user_id) - self.unpaid_fees(user_id))

    def fuel_net_in_cycle(self, user_id: str, cycle_id: str) -> Decimal:
        return sum((p.net_unbilled for p in self.purchases.values()
                    if p.user_id == user_id and p.cycle_id == cycle_id
                    and p.category == FUEL_CATEGORY and p.billed_in is None), ZERO)

    # ---- ledger print ---------------------------------------------------
    def log(self, user_id: str, ts: datetime, text: str):
        if user_id in self.users:
            avail = fmt(self.available_line(user_id))
            self.log_lines[user_id].append(
                f"{ts.isoformat()}  {text}  | available {avail}")
