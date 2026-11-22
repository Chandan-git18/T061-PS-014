# Demo video script · T061 PS-014 · 5 minutes

Record the screen with your voice (OBS Studio, or Windows Game Bar: Win + Alt + R).
Split the speaking between both of you: Vedasree takes parts 1 and 2, Chandan takes parts 3 to 6.
Before recording, open Command Prompt in the `T061-PS-014` folder, close Excel, and run
`python -m bnpl demo` once so the `out\demo` folder exists.

| Part | Time | Who | On screen |
| --- | --- | --- | --- |
| 1. What we built | 0:00–0:30 | Vedasree | `README.md` on GitHub |
| 2. Design | 0:30–1:30 | Vedasree | `docs/design_document.pdf`: rule register, state diagram |
| 3. Run the demo | 1:30–2:15 | Chandan | Command Prompt |
| 4. The results | 2:15–3:45 | Chandan | `decisions.csv`, `bills.csv`, `ledger\U03.txt`, bureau file |
| 5. Tests | 3:45–4:15 | Chandan | `python -m pytest -v` |
| 6. Live rule change | 4:15–5:00 | Chandan | `bnpl\rules.py`, then rerun |

## 1. What we built (30 s)

> "We are Team T061. We built the ledger engine behind a buy-now-pay-later app, in Python.
> It reads users, merchants, purchases, refunds, payments and bank results from CSV files, and
> writes every decision, every bill, each user's account state per day and a month-end bureau
> report. There is no UI, as the brief asks."

## 2. Design (60 s)

Open the PDF at the business rule register (section 4).

> "Every rule in the brief has an ID, BR-01 to BR-26, and each one maps to one module and at
> least one test. That is section 11, the traceability table."

Scroll to the state diagram (section 3).

> "This is the heart of it. An account moves right as its oldest unpaid bill gets older: 3 days
> overdue is SOFT_FREEZE, 30 days is HARD_FREEZE where the line is cut to what they owe, 90 days
> is CLOSED. It only moves back through payment, and after a HARD_FREEZE the original line
> comes back after three bills paid on time in a row."

## 3. Run the demo (45 s)

```
python -m bnpl demo
```

> "This is our demo data: six users over four months, January to April 2027. Each user shows a
> different part of the rules. The engine walks the calendar one day at a time, in a fixed
> order: bills at midnight, then late fees, then freezes, then the 8 am bank debits, then the
> customer's own actions. That fixed order is what makes boundary cases like midnight on the
> 16th always come out the same."

Point at the output line: 25 decisions, 11 bills, 1 rejected line.

## 4. The results (90 s)

```
start out\demo\decisions.csv
```

> "Every purchase and refund, approved or declined, with the reason codes. Here U01 is declined
> M01 for a gaming merchant, P01 for a purchase above 15,000, and R01 for refunding more than
> was bought. U02 gets S01 because the account is frozen."

```
start out\demo\bills.csv
```

> "U02's bill: three failed bank debits added two bounce charges of 50, and the late fee of 150
> came at due date plus six days. U05's bill of 400 got a late fee of only 40, because the late
> fee is capped at 10 percent."

```
notepad out\demo\ledger\U03.txt
```

Scroll slowly from top to bottom.

> "This is one user's whole story. U03 never paid the January bill. SOFT_FREEZE on 23 January,
> late fee 300, then HARD_FREEZE on 19 February: the line drops from 20,000 to 6,370.80, exactly
> what they owed, so available line is zero. A refund while frozen pays off the fees first. They
> pay the rest on 2 March and become ACTIVE, but still on the reduced line. Then three bills
> paid on time, and on 19 April the line goes back to 20,000."

```
start out\demo\bureau_2027-04.csv
```

> "The April bureau report. U05 is CLOSED with 100 days past due, and the amount excludes GST,
> as the brief requires."

## 5. Tests (30 s)

```
python -m pytest -v
```

> "90 tests, all passing. Each one is named after the rule it proves, so test_br_21 proves
> BR-21. Each of the eight edge cases has its own test, and one test fails if any rule is left
> untested."

## 6. Live rule change (45 s)

Open `bnpl\rules.py` in an editor and change one line:

```
SOFT_FREEZE_DAYS = 5
```

Save, then run:

```
python -m pytest -q
```

> "Every limit in the brief is one constant in rules.py. If the freeze moves from 3 days to 5,
> I change this one line, and 7 tests fail straight away: the two that pin the 3-day rule, and
> the demo scenario, whose freeze dates moved. That shows the tests really guard the rules."

Change it back to `3`, save, run `python -m pytest -q` again to show all tests passing.

> "Thank you. The design document, decision log and all code are in our repository."

## Before you upload

- [ ] Video is 5 minutes or less
- [ ] Voice is clear and the text on screen is readable (zoom Command Prompt with Ctrl + scroll)
- [ ] `rules.py` is back to `SOFT_FREEZE_DAYS = 3` and the last test run shows all passing
- [ ] Upload to YouTube as **Unlisted** or Google Drive with "Anyone with the link can view"
- [ ] Put the link in the README's Documents table and commit it
