"""Demo scenario (data/demo/): six users, four months, every major rule in one run.

    U01  good customer: refund before and after billing, M01 / P01 / R01 / V04 declines
    U02  three failed debits, Rs 100 bounce, Rs 150 late fee, SOFT_FREEZE, pays, ACTIVE
    U03  HARD_FREEZE, refund while frozen, 3 on-time bills, original line restored
    U04  mandate cancelled between retry 1 and retry 2 (E4)
    U05  Rs 400 bill never paid: Rs 40 late fee (E5), SOFT, HARD, CLOSED at 90 days
    U06  onboarding rejected (O01), so its purchase is V01; one out-of-order line (V05)

The story checks below were worked out by hand. The file comparison then guards every
output line against accidental changes (regenerate data/demo/expected only on purpose).
"""
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from bnpl.engine import run_files
from bnpl.io.writer import write_outputs
from bnpl.models import LineState

DATA = Path(__file__).resolve().parents[2] / "data" / "demo"


@pytest.fixture(scope="module")
def ledger():
    return run_files(DATA / "users.csv", DATA / "merchants.csv", DATA / "commands.csv",
                     DATA / "debit_results.csv")


def bill(ledger, bill_id):
    return next(b for b in ledger.bills if b.bill_id == bill_id)


def test_demo_u01_refunds_and_declines(ledger):
    assert bill(ledger, "B0001").total == D("4755.46")      # 4000 + 1200 - 500, fee 47, GST 8.46
    assert bill(ledger, "B0005").principal == D("1500.00")  # 2500 - 1000 refund credit
    rules = {d.txn_id: d.rule_ids for d in ledger.decisions if d.user_id == "U01"}
    assert rules["T0014"] == ["M01"] and rules["T0015"] == ["P01"]
    assert rules["T0017"] == ["R01"] and rules["T0016"] == ["V04"]


def test_demo_u02_soft_freeze_and_recovery(ledger):
    b = bill(ledger, "B0004")
    assert (b.bounce_total, b.late_fee, b.total) == (D("100.00"), D("150.00"), D("3285.40"))
    moves = [(s.to_state, s.ts.date()) for s in ledger.state_changes if s.user_id == "U02"]
    assert moves == [(LineState.SOFT_FREEZE, date(2027, 2, 8)),
                     (LineState.ACTIVE, date(2027, 2, 12))]
    fuel = [d for d in ledger.decisions if d.txn_id == "T0019"][0]
    assert fuel.rule_ids == ["M02"]                          # 1,500 + 800 > 2,000 per cycle


def test_demo_u03_hard_freeze_and_restore(ledger):
    lines = [(s.trigger.split()[0], s.current_line) for s in ledger.state_changes
             if s.user_id == "U03"]
    assert lines == [("BR-20", D("20000.00")), ("BR-21", D("6370.80")),
                     ("A-05", D("6370.80")), ("BR-24", D("20000.00"))]
    assert ledger.users["U03"].current_line == D("20000.00")


def test_demo_u04_mandate_cancel(ledger):
    b = bill(ledger, "B0006")
    assert (b.bounce_total, b.late_fee, b.total) == (D("50.00"), D("50.00"), D("1921.24"))


def test_demo_u05_closed(ledger):
    assert bill(ledger, "B0003").late_fee == D("40.00")
    closed = [s for s in ledger.state_changes if s.to_state == LineState.CLOSED]
    assert [(s.user_id, s.ts.date()) for s in closed] == [("U05", date(2027, 4, 20))]
    april = {r.user_id: r for r in ledger.bureau_reports["2027-04"]}
    assert (april["U05"].dpd, april["U05"].amount_reported) == (100, D("440.00"))


def test_demo_u06_and_bad_line(ledger):
    assert [d.rule_ids for d in ledger.decisions if d.user_id == "U06"] == [["O01"], ["V01"]]
    assert [r.rule_id for r in ledger.rejected] == ["V05"]


def test_demo_bureau_excludes_gst(ledger):
    jan = {r.user_id: r for r in ledger.bureau_reports["2027-01"]}
    assert jan["U03"].amount_reported == D("6360.00")        # 6000 + 60 + 300, not the 10.80 GST
    assert jan["U03"].dpd == 11


def test_demo_output_files_unchanged(ledger, tmp_path):
    write_outputs(ledger, tmp_path)
    for expected in sorted((DATA / "expected").glob("*.csv")):
        actual = (tmp_path / expected.name).read_text().splitlines()
        assert actual == expected.read_text().splitlines(), expected.name


def test_demo_command_line(tmp_path, capsys):
    from bnpl.cli import main
    assert main(["demo", "--out", str(tmp_path)]) == 0
    assert capsys.readouterr().out.startswith("Done.")
    for name in ("decisions.csv", "bills.csv", "line_states.csv", "bureau_2027-04.csv",
                 "ledger/U03.txt"):
        assert (tmp_path / name).exists(), name
