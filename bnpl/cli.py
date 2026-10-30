"""Command-line entry point.

    python -m bnpl run --users U.csv --merchants M.csv --commands C.csv \
        --debits D.csv --out out/
"""
import argparse
from datetime import date

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
    args = parser.parse_args(argv)

    until = date.fromisoformat(args.until) if args.until else None
    ledger = run_files(args.users, args.merchants, args.commands, args.debits, until)
    write_outputs(ledger, args.out)
    print(f"Done. {len(ledger.decisions)} decisions, {len(ledger.bills)} bills, "
          f"{len(ledger.rejected)} rejected lines -> {args.out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
