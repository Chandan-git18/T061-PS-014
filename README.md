# T061-PS-014 · BNPL Pay-Later Ledger

Team T061 · C Vedasree (1AT24CG018), Chandan T (1AT24CG019) · Section CSD

A deterministic, command-file driven ledger engine for a pay-later fintech. It reads users,
merchants, purchase/refund/payment commands and auto-debit results, and writes every
authorisation decision, every bill and a ledger print per user. No UI.

Python 3.10+, standard library only. Tests use pytest.

## Status (Week 2 – Core flows)

| Area | Rules | Status |
| --- | --- | --- |
| Onboarding | BR-01 | Done |
| Purchase and refund authorisation | BR-02 to BR-07, BR-13, V01 to V05 | Done |
| Available line | BR-06 | Done |
| Billing, convenience fee, GST, refunds | BR-08 to BR-12 | Done |
| Auto-debit schedule and success posting | BR-14 | Done |
| Payment allocation and credit balance | BR-19, A-15 | Done |
| Happy path end to end | Section 6 of the design document | Done, tested |

## Setup

```
git clone https://github.com/Chandan-git18/T061-PS-014.git
cd T061-PS-014
pip install -r requirements.txt
```

## Run

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
- `rejected_lines.csv`: malformed or out-of-order input lines (V05)
- `ledger/<user_id>.txt`: a readable ledger print per user

## Tests

```
python -m pytest -q
```

- `tests/unit/`: one or more tests per business rule (BR-01 to BR-14, BR-19) and per validation rule (V01 to V05)
- `tests/scenarios/test_happy_path.py`: runs `data/happy_path/` and compares the output line by line with hand-worked expected files

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
                 authorisation, billing, payments, autodebit, engine, io, cli)
data/happy_path/ happy-path scenario and its expected outputs
data/sample/     organisers' sample files
docs/            design document
tests/           unit and scenario tests
```

All rule constants and assumption switches (A-01 to A-17) live in `bnpl/rules.py`.
