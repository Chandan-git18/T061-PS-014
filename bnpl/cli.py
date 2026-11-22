"""Command-line entry point.

    python -m bnpl run --users U.csv --merchants M.csv --commands C.csv \
        --debits D.csv --out out/
    python -m bnpl demo                 # runs data/demo/ into out/demo/
    python -m bnpl demo --save-expected # after an agreed rule change: refresh
                                        # data/demo/expected/ (see decision log D-25)
"""
import argparse
from datetime import date
from pathlib import Path

from .engine import run_files
from .io.writer import write_outputs


def main(argv=None):
    parser = argparse.ArgumentParser(prog="bnpl", description="PS-014 BNPL ledger engine")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the engine on input files")
    run.add_argument("--users", required=True)
    run.add_argument("--merchants", required=True)
    run.add_argument("--commands", required=True)
    run.add_argument("--debits", default=None)
    run.add_argument("--out", default="out")
    run.add_argument("--until", default=None, help="last simulated date, YYYY-MM-DD")
    demo = sub.add_parser("demo", help="run the demo scenario in data/demo/")
    demo.add_argument("--out", default="out/demo")
    demo.add_argument("--save-expected", action="store_true",
                      help="also overwrite data/demo/expected/ with this run's CSV files")
    args = parser.parse_args(argv)

    if args.command == "demo":
        data = Path(__file__).resolve().parent.parent / "data" / "demo"
        args.users, args.merchants = data / "users.csv", data / "merchants.csv"
        args.commands, args.debits = data / "commands.csv", data / "debit_results.csv"
        args.until = None
    until = date.fromisoformat(args.until) if args.until else None
    ledger = run_files(args.users, args.merchants, args.commands, args.debits, until)
    write_outputs(ledger, args.out)
    if args.command == "demo" and args.save_expected:
        expected = data / "expected"
        for f in sorted(Path(args.out).glob("*.csv")):
            (expected / f.name).write_bytes(f.read_bytes())
        print(f"Expected files refreshed in {expected}/")
    print(f"Done. {len(ledger.decisions)} decisions, {len(ledger.bills)} bills, "
          f"{len(ledger.rejected)} rejected lines -> {args.out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
