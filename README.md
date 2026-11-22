# T061-PS-014 · BNPL Pay-Later Ledger

Team T061 · C Vedasree (1AT24CG018), Chandan T (1AT24CG019) · Section CSD

A deterministic, command-file driven ledger engine for a pay-later fintech. It reads users,
merchants, purchase/refund/payment commands and auto-debit results, and writes every
authorisation decision, every bill, the line state on each date, the month-end bureau file
and a ledger print per user. No UI.

Python 3.10+, standard library only. Tests use pytest.

## Status (Week 4 – Final submission)

All 26 business rules (BR-01 to BR-26), 5 validation rules (V01 to V05) and 8 edge cases (E1 to E8)
are implemented and tested. The suite has 90 tests, all passing.

| Area | Rules | Status |
| --- | --- | --- |
| Onboarding | BR-01 | Done |
| Purchase and refund authorisation | BR-02 to BR-07, BR-13, V01 to V05 | Done |
| Available line | BR-06 | Done |
| Billing, convenience fee, GST, refunds | BR-08 to BR-12 | Done |
| Auto-debit schedule, bounce charges, mandate cancel | BR-14 to BR-16 | Done |
| Late fee tiers and 10% cap | BR-17, BR-18 | Done |
| Payment allocation and credit balance | BR-19, A-15 | Done |
| Freeze and restore state machine | BR-20 to BR-24 | Done |
| Month-end bureau file | BR-25, BR-26 | Done |
| Edge cases E1 to E8 | Design document section 9 | Done, one test each |
| Demo scenario | `data/demo/` | Done, story and every output file tested |
| Organisers' sample data | Week 2 files | Run from `data/sample/` once received |

## Documents

| Document | What it holds |
| --- | --- |
| [docs/design_document.pdf](docs/design_document.pdf) | Final design: glossary, class and state diagrams, rule register, edge cases, traceability rule → code → test |
| [docs/decision_log.md](docs/decision_log.md) | Every rule interpretation and design choice, with date and reason |
| [docs/demo_video_script.md](docs/demo_video_script.md) | Script and commands for the 5-minute demo video |
| Demo video | Link to be added after recording |

## Setup

```
git clone https://github.com/Chandan-git18/T061-PS-014.git
cd T061-PS-014
pip install -r requirements.txt
```

## Run

Demo scenario (six users, four months, every state and fee):

```
python -m bnpl demo
```

It writes to `out/demo/`. The clearest single file is `out/demo/ledger/U03.txt`: a user who reaches
HARD_FREEZE and gets the original line back.

Happy-path scenario:

```
python -m bnpl run --users data/happy_path/users.csv --merchants data/happy_path/merchants.csv --commands data/happy_path/commands.csv --debits data/happy_path/debit_results.csv --out out/happy_path
```

Organisers' sample data (put the files in `data/sample/` first):

```
python -m bnpl run --users data/sample/users.csv --merchants data/sample/merchants.csv --commands data/sample/commands.csv --debits data/sample/debit_results.csv --out out/sample
```

Outputs in the `--out` folder:

- `decisions.csv`: every PURCHASE and REFUND decision, with failed rule IDs and the available line after it
- `bills.csv`: every bill with principal, convenience fee, GST, late fee, bounce, total, due date and paid status
- `line_states.csv`: each user's state, current line, available line and days overdue at the end of every date
- `state_changes.csv`: every freeze, restore and line-restored event with its trigger rule
- `debit_attempts.csv`: every scheduled attempt with its result and any bounce charge
- `bureau_YYYY-MM.csv`: month-end bureau file (DPD, amount reported without GST)
- `rejected_lines.csv`: malformed or out-of-order input lines (V05)
- `ledger/<user_id>.txt`: a readable ledger print per user

## Tests

```
python -m pytest -q
```

- `tests/unit/`: tests named `test_br_NN_*` for every business rule BR-01 to BR-26, and V01 to V05
- `tests/scenarios/test_edge_cases.py`: `test_e1_*` to `test_e8_*`, each edge case run through the parser and engine
- `tests/scenarios/test_happy_path.py`: runs `data/happy_path/` and compares the output line by line with hand-worked expected files
- `tests/scenarios/test_demo.py`: runs `data/demo/`, checks each user's story against hand-worked values, then compares every output file
- `tests/test_rule_coverage.py`: fails if any BR-ID or edge case has no test

## Input formats (provisional until aligned with the sample files)

```
users.csv:          user_id,kyc,line,mandate,onboard_date
merchants.csv:      merchant_id,category
commands.csv:       ts,type,txn_id,user_id,merchant_id,amount,ref_txn_id
debit_results.csv:  ts,user_id,bill_id,attempt_no,result,amount
```

Command types: PURCHASE, REFUND, PAYMENT, MANDATE_CANCEL. Commands must be in time order.

## Layout

```
bnpl/            engine package (money, calendar, rules, models, ledger, users,
                 authorisation, billing, fees, payments, autodebit, state_machine,
                 bureau, engine, io, cli)
data/happy_path/ happy-path scenario and its expected outputs
data/demo/       demo scenario (6 users, 4 months) and its expected outputs
data/sample/     organisers' sample files
docs/            design document (PDF), decision log, demo video script
tests/           unit and scenario tests
```

All rule constants and assumption switches (A-01 to A-17) live in `bnpl/rules.py`.
