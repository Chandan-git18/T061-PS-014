"""Input parsing. Malformed or out-of-order command lines are rejected with V05."""
import csv
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from .. import rules
from ..money import parse_amount

COMMAND_TYPES = {"PURCHASE", "REFUND", "PAYMENT", "MANDATE_CANCEL"}


@dataclass
class Command:
    ts: datetime
    type: str
    txn_id: str
    user_id: str
    merchant_id: str
    amount: Optional[object]
    ref_txn_id: str
    line_no: int


@dataclass
class Rejected:
    line_no: int
    raw: str
    rule_id: str
    reason: str


def _rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            yield i, {k.strip(): (v or "").strip() for k, v in row.items() if k}


def read_users(path):
    users = []
    for _, r in _rows(path):
        users.append({
            "user_id": r["user_id"],
            "kyc": r["kyc"],
            "line": parse_amount(r["line"]),
            "mandate_active": r.get("mandate", "ACTIVE").upper() != "CANCELLED",
            "onboard_date": date.fromisoformat(r["onboard_date"]) if r.get("onboard_date") else None,
        })
    return users


def read_merchants(path):
    return [(r["merchant_id"], r["category"].upper()) for _, r in _rows(path)]


def read_commands(path):
    """Return (commands, rejected). Input must be time-ordered (V05)."""
    commands, rejected = [], []
    last_ts = None
    with open(path, newline="", encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    header = [h.strip() for h in lines[0].split(",")]
    for line_no, raw in enumerate(lines[1:], start=2):
        if not raw.strip():
            continue
        values = next(csv.reader([raw]))
        if len(values) != len(header):
            rejected.append(Rejected(line_no, raw, rules.V05, "wrong number of fields"))
            continue
        r = dict(zip(header, (v.strip() for v in values)))
        try:
            ts = datetime.fromisoformat(r["ts"])
        except ValueError:
            rejected.append(Rejected(line_no, raw, rules.V05, "bad timestamp"))
            continue
        ctype = r["type"].upper()
        if ctype not in COMMAND_TYPES:
            rejected.append(Rejected(line_no, raw, rules.V05, "unknown command type"))
            continue
        if last_ts is not None and ts < last_ts:
            rejected.append(Rejected(line_no, raw, rules.V05, "timestamp earlier than previous command"))
            continue
        amount = parse_amount(r.get("amount", "")) if r.get("amount") else None
        if ctype != "MANDATE_CANCEL" and amount is None and r.get("amount"):
            rejected.append(Rejected(line_no, raw, rules.V05, "amount is not a number"))
            continue
        last_ts = ts
        commands.append(Command(ts, ctype, r["txn_id"], r["user_id"], r.get("merchant_id", ""),
                                amount, r.get("ref_txn_id", ""), line_no))
    return commands, rejected


def read_debit_results(path):
    """Map (bill_id, attempt_no) -> SUCCESS / FAILED."""
    results = {}
    if path is None:
        return results
    for _, r in _rows(path):
        results[(r["bill_id"], int(r["attempt_no"]))] = r["result"].upper()
    return results
