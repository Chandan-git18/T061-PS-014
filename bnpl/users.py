"""Onboarding (BR-01)."""
from datetime import date, datetime, time

from . import rules
from .models import Decision, KycLevel, User
from .money import fmt, money


def onboard(ledger, user_id: str, kyc: str, line, mandate_active: bool = True,
            onboard_date: date = None) -> Decision:
    """Create a user if the requested line is within the KYC maximum, else O01."""
    line = money(line)
    ts = datetime.combine(onboard_date, time()) if onboard_date else None
    ts_text = ts.isoformat() if ts else ""
    kyc = kyc.strip().upper()
    if kyc not in rules.KYC_MAX_LINE or line <= 0 or line > rules.KYC_MAX_LINE[kyc]:
        return Decision(ts_text, "", user_id, "ONBOARD", fmt(line), "DECLINED",
                        [rules.O01], None)
    user = User(user_id=user_id, kyc=KycLevel(kyc), original_line=line,
                current_line=line, onboard_date=onboard_date,
                mandate_active=mandate_active)
    ledger.users[user_id] = user
    if ts:
        ledger.log(user_id, ts, f"ONBOARD kyc={kyc} line={fmt(line)}")
    return Decision(ts_text, "", user_id, "ONBOARD", fmt(line), "APPROVED", [], line)
