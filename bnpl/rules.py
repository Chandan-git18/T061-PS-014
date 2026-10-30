"""All business-rule constants and assumption switches in one place.

Each assumption (A-xx) from the design document is a single constant here, so it
can be changed quickly once the organisers answer.
"""
from decimal import Decimal as D

# BR-01 onboarding limits
KYC_MAX_LINE = {"MIN": D("10000.00"), "FULL": D("60000.00")}

# BR-02 single purchase cap
SINGLE_PURCHASE_PCT = D("0.50")
SINGLE_PURCHASE_ABS = D("15000.00")

# BR-03 / BR-04 / BR-05 merchant categories
BLOCKED_CATEGORIES = {"GAMING", "CRYPTO"}
FUEL_CATEGORY = "FUEL"
FUEL_CYCLE_CAP = D("2000.00")
GROCERY_CATEGORY = "GROCERY"
GROCERY_EXEMPT_FROM_P01 = True  # A-08

# BR-09 due date
DUE_DAYS_AFTER_BILL = 5

# BR-10 convenience fee (A-01: 1% of the whole bill when above the threshold)
CONV_FEE_THRESHOLD = D("1000.00")
CONV_FEE_RATE = D("0.01")
CONV_FEE_MAX = D("100.00")
GST_RATE = D("0.18")  # A-03: GST on the convenience fee only

# BR-14 / BR-15 auto-debit
DEBIT_DAY_OFFSETS = (0, 2, 5)  # due date, due + 2, due + 5
DEBIT_HOUR = 8
BOUNCE_CHARGE = D("50.00")

# BR-19 allocation order (Bill attribute names)
ALLOCATION_ORDER = ("bounce_total", "late_fee", "conv_fee", "conv_gst", "principal")

# A-17: report every failed rule ID (set False to report only the first)
REPORT_ALL_RULE_IDS = True

# Rule IDs printed in decision lines
O01 = "O01"  # onboarding line above KYC max
P01 = "P01"  # single purchase cap
M01 = "M01"  # blocked category
M02 = "M02"  # fuel cycle cap
L01 = "L01"  # insufficient available line
S01, S02, S03 = "S01", "S02", "S03"  # purchase in SOFT_FREEZE / HARD_FREEZE / CLOSED
R01 = "R01"  # refund above purchase amount
R02 = "R02"  # refund references unknown purchase or another user's purchase
V01, V02, V03, V04, V05 = "V01", "V02", "V03", "V04", "V05"
