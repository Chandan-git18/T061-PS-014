"""Domain classes and enums (see the class diagram in the design document)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from .money import ZERO
from .rules import ALLOCATION_ORDER


class LineState(str, Enum):
    ACTIVE = "ACTIVE"
    SOFT_FREEZE = "SOFT_FREEZE"
    HARD_FREEZE = "HARD_FREEZE"
    CLOSED = "CLOSED"


class KycLevel(str, Enum):
    MIN = "MIN"
    FULL = "FULL"


class PaymentSource(str, Enum):
    MANUAL = "MANUAL"
    AUTO_DEBIT = "AUTO_DEBIT"
    REFUND_CREDIT = "REFUND_CREDIT"


class DebitResult(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    NO_RESPONSE = "NO_RESPONSE"  # A-14: treated as FAILED


class RefundType(str, Enum):
    CYCLE_REDUCTION = "CYCLE_REDUCTION"
    CREDIT = "CREDIT"


@dataclass
class User:
    user_id: str
    kyc: KycLevel
    original_line: Decimal
    current_line: Decimal
    onboard_date: Optional[date] = None
    state: LineState = LineState.ACTIVE
    mandate_active: bool = True
    credit_balance: Decimal = ZERO
    on_time_streak: int = 0


@dataclass
class Merchant:
    merchant_id: str
    category: str


@dataclass
class Purchase:
    txn_id: str
    user_id: str
    merchant_id: str
    category: str
    amount: Decimal
    ts: datetime
    cycle_id: str
    refunded_total: Decimal = ZERO
    refunded_before_bill: Decimal = ZERO
    billed_in: Optional[str] = None

    @property
    def net_unbilled(self) -> Decimal:
        return self.amount - self.refunded_before_bill


@dataclass
class Refund:
    txn_id: str
    purchase_id: str
    user_id: str
    amount: Decimal
    ts: datetime
    applied_as: RefundType


@dataclass
class Bill:
    bill_id: str
    user_id: str
    cycle_id: str
    bill_date: date
    due_date: date
    principal: Decimal
    conv_fee: Decimal
    conv_gst: Decimal
    late_fee: Decimal = ZERO
    bounce_total: Decimal = ZERO
    paid_by_component: dict = field(
        default_factory=lambda: {c: ZERO for c in ALLOCATION_ORDER})
    paid_on: Optional[date] = None
    on_time: Optional[bool] = None

    @property
    def total(self) -> Decimal:
        return sum((getattr(self, c) for c in ALLOCATION_ORDER), ZERO)

    def outstanding(self, component: Optional[str] = None) -> Decimal:
        if component is None:
            return sum((self.outstanding(c) for c in ALLOCATION_ORDER), ZERO)
        return getattr(self, component) - self.paid_by_component[component]

    @property
    def is_paid(self) -> bool:
        return self.outstanding() == 0


@dataclass
class DebitAttempt:
    bill_id: str
    user_id: str
    attempt_no: int
    scheduled_at: datetime
    result: Optional[DebitResult] = None
    bounce_charged: bool = False


@dataclass
class Allocation:
    bill_id: str
    component: str
    amount: Decimal


@dataclass
class Payment:
    txn_id: str
    user_id: str
    amount: Decimal
    ts: datetime
    source: PaymentSource
    allocations: list = field(default_factory=list)


@dataclass
class Decision:
    ts: str
    txn_id: str
    user_id: str
    type: str
    amount: str
    decision: str
    rule_ids: list
    available_after: Optional[Decimal]

    @property
    def approved(self) -> bool:
        return self.decision == "APPROVED"
