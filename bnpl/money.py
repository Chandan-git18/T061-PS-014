"""Exact money handling: Decimal, 2 places, ROUND_HALF_UP. No floats anywhere."""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

CENT = Decimal("0.01")


def money(value) -> Decimal:
    """Convert to Decimal and round half-up to 2 decimal places."""
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


ZERO = money(0)


def fmt(value) -> str:
    """Format money for output files, e.g. 7082.60."""
    return f"{money(value):.2f}"


def parse_amount(text: str):
    """Parse an amount exactly as written (no rounding). Returns None if not numeric."""
    try:
        return Decimal(text.strip())
    except (InvalidOperation, AttributeError):
        return None


def is_valid_amount(amount) -> bool:
    """V02: amount must be > 0 with at most 2 decimal places."""
    if amount is None or not amount.is_finite():
        return False
    return amount > 0 and amount == amount.quantize(CENT)
