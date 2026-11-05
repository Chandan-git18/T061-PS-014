"""Every business rule BR-01 to BR-26 and every edge case E1 to E8 has at least one test.

Tests are named test_br_NN_* and test_eN_*, so the rule register maps straight to tests.
"""
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def collect_test_names():
    names = set()
    for f in TESTS.rglob("test_*.py"):
        names |= set(re.findall(r"^def (test_\w+)", f.read_text(), re.M))
    return names


def test_every_br_id_has_a_test():
    names = collect_test_names()
    missing = [f"BR-{n:02d}" for n in range(1, 27)
               if not any(t.startswith(f"test_br_{n:02d}_") for t in names)]
    assert missing == []


def test_every_edge_case_has_a_test():
    names = collect_test_names()
    missing = [f"E{n}" for n in range(1, 9)
               if not any(t.startswith(f"test_e{n}_") for t in names)]
    assert missing == []
