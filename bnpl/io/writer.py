"""CSV outputs: decisions, bills, line states, state changes, debit attempts,
bureau files, rejected lines and per-user ledger prints."""
import csv
from pathlib import Path

from ..money import fmt

DECISION_HEADER = ["ts", "txn_id", "user_id", "type", "amount", "decision",
                   "rule_ids", "available_after"]
BILL_HEADER = ["bill_id", "user_id", "cycle_id", "bill_date", "due_date", "principal",
               "conv_fee", "gst", "late_fee", "bounce", "total", "paid_on", "status"]
LINE_STATE_HEADER = ["date", "user_id", "state", "current_line", "available_line",
                     "days_overdue"]
STATE_CHANGE_HEADER = ["ts", "user_id", "from_state", "to_state", "current_line", "trigger"]
ATTEMPT_HEADER = ["bill_id", "user_id", "attempt_no", "scheduled_at", "result", "bounce"]
BUREAU_HEADER = ["report_month", "user_id", "kyc", "sanctioned_line", "current_line",
                 "line_state", "amount_reported", "dpd"]


def _write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def bill_status(bill) -> str:
    if not bill.is_paid:
        return "OPEN"
    return "PAID_ON_TIME" if bill.on_time else "PAID_LATE"


def write_outputs(ledger, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    _write(out / "decisions.csv", DECISION_HEADER, [
        [d.ts, d.txn_id, d.user_id, d.type, d.amount, d.decision, "|".join(d.rule_ids),
         fmt(d.available_after) if d.available_after is not None else ""]
        for d in ledger.decisions])

    _write(out / "bills.csv", BILL_HEADER, [
        [b.bill_id, b.user_id, b.cycle_id, b.bill_date.isoformat(), b.due_date.isoformat(),
         fmt(b.principal), fmt(b.conv_fee), fmt(b.conv_gst), fmt(b.late_fee),
         fmt(b.bounce_total), fmt(b.total), b.paid_on.isoformat() if b.paid_on else "",
         bill_status(b)]
        for b in ledger.bills])

    _write(out / "rejected_lines.csv", ["line_no", "rule_id", "reason", "raw"],
           [[r.line_no, r.rule_id, r.reason, r.raw] for r in ledger.rejected])

    _write(out / "line_states.csv", LINE_STATE_HEADER, [
        [d.isoformat(), uid, state, fmt(line), fmt(avail), dpd]
        for d, uid, state, line, avail, dpd in ledger.state_rows])

    _write(out / "state_changes.csv", STATE_CHANGE_HEADER, [
        [s.ts.isoformat(), s.user_id, s.from_state.value, s.to_state.value,
         fmt(s.current_line), s.trigger]
        for s in ledger.state_changes])

    _write(out / "debit_attempts.csv", ATTEMPT_HEADER, [
        [a.bill_id, a.user_id, a.attempt_no, a.scheduled_at.isoformat(),
         a.result.value if a.result else "PENDING", "50.00" if a.bounce_charged else "0.00"]
        for a in ledger.attempts])

    for month, rows in sorted(ledger.bureau_reports.items()):
        _write(out / f"bureau_{month}.csv", BUREAU_HEADER, [
            [r.report_month, r.user_id, r.kyc, fmt(r.sanctioned_line), fmt(r.current_line),
             r.line_state, fmt(r.amount_reported), r.dpd]
            for r in rows])

    ledger_dir = out / "ledger"
    ledger_dir.mkdir(exist_ok=True)
    for user_id, user in sorted(ledger.users.items()):
        lines = [f"User {user_id}  kyc={user.kyc.value}  original_line={fmt(user.original_line)}  "
                 f"current_line={fmt(user.current_line)}  state={user.state.value}", ""]
        lines += ledger.log_lines[user_id]
        lines += ["", f"Available line at end: {fmt(ledger.available_line(user_id))}",
                  f"Credit balance at end: {fmt(user.credit_balance)}"]
        (ledger_dir / f"{user_id}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
