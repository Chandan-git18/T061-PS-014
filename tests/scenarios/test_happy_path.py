"""Happy path: onboarding -> purchases and a refund -> bill -> auto-debit -> line restored.

Expected files were worked out by hand (design document, section 6), not copied from
engine output, so this test checks the engine against the design.
"""
from pathlib import Path

from bnpl.engine import run_files
from bnpl.io.writer import write_outputs

DATA = Path(__file__).resolve().parents[2] / "data" / "happy_path"


def test_happy_path(tmp_path):
    ledger = run_files(DATA / "users.csv", DATA / "merchants.csv", DATA / "commands.csv",
                       DATA / "debit_results.csv")
    write_outputs(ledger, tmp_path)
    for name in ("decisions.csv", "bills.csv"):
        actual = (tmp_path / name).read_text().splitlines()
        expected = (DATA / "expected" / name).read_text().splitlines()
        assert actual == expected, name
    assert ledger.available_line("U01") == ledger.users["U01"].original_line
    assert all(u.state.value == "ACTIVE" for u in ledger.users.values())
