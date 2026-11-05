# Decision log · T061 PS-014

One line per decision: what we chose, which rule or assumption it settles, and why.
Assumption IDs (A-xx) are from section 2 of the design document; each one is a constant in
`bnpl/rules.py`. When the organisers answer a question, add the answer and the code change here.

| ID | Date | Decision | Rule | Why |
| --- | --- | --- | --- | --- |
| D-01 | 2026-10-21 | Python 3.10+, standard library only, pytest for tests | n/a | Less code per rule, `Decimal` reads naturally, short tests |
| D-02 | 2026-10-21 | All money is `Decimal`, rounded to 0.01 half-up; fee rounded before GST | BR-10 | Output must match to the paisa; floats cannot guarantee that |
| D-03 | 2026-10-21 | Cycle membership by date only; bills generated at 00:00:00 on the 16th and 1st, before commands at that instant | BR-08, E1 | One fixed rule settles 15th 23:59:59 vs 16th 00:00:00 |
| D-04 | 2026-10-21 | Convenience fee is 1% of the whole bill when bill > Rs 1,000 | BR-10, A-01 | Literal reading of the brief; one switch if they mean "of the excess" |
| D-05 | 2026-10-30 | Every failed rule ID is reported, in evaluation order | A-17 | Shows the full reason; `REPORT_ALL_RULE_IDS` switches to first-only |
| D-06 | 2026-10-30 | GROCERY is exempt from the single-purchase cap but not from L01 | BR-02, BR-05, A-08 | "Up to 100% of available line" contradicts a 50% cap |
| D-07 | 2026-11-05 | Late fee charged once at 00:00:00 on due + 6 days if any amount of the bill is unpaid | BR-17, E6 | "After due + 5 days" means once that whole day is over |
| D-08 | 2026-11-05 | Late-fee tier and the 10% cap both use the bill principal, not fees | BR-17, BR-18, A-02 | "Bill amount" read as what was billed; Rs 400 bill gives Rs 40 |
| D-09 | 2026-11-05 | Late fee and bounce charge carry no GST | A-03 | The brief only mentions GST on the convenience fee |
| D-10 | 2026-11-05 | A debit attempt with no result line counts as FAILED (and charges a bounce if not the first) | BR-15, A-14 | The result file may not list every attempt |
| D-11 | 2026-11-05 | After a mandate cancel, remaining attempts are SKIPPED with no charge; bills generated later get no attempts | BR-16, E4 | "No retry if mandate cancelled" |
| D-12 | 2026-11-05 | Days overdue = date − earliest due date among unpaid bills; the due date itself is 0 | BR-20, BR-25 | Same definition for freezes and the bureau DPD |
| D-13 | 2026-11-05 | Forward state moves checked daily at 00:00:00; every step is logged even if the data skips days | BR-20 to BR-22 | One check per day keeps state per date deterministic |
| D-14 | 2026-11-05 | HARD_FREEZE sets the line to total outstanding (all bill components incl. GST, plus unbilled), so available becomes 0 | BR-21 | "Reduced to current outstanding" |
| D-15 | 2026-11-05 | SOFT_FREEZE → ACTIVE as soon as no bill is past due, checked after every payment | BR-23, A-06 | Bills not yet due do not block restoration |
| D-16 | 2026-11-05 | HARD_FREEZE → ACTIVE once no bill is overdue, line stays reduced; original line after 3 consecutive on-time bills | BR-24, A-04, A-05 | Reconciles "permanently" with the restoration rule |
| D-17 | 2026-11-05 | The streak counts bills fully paid while the line is reduced: on time +1, late resets to 0, any overdue day resets to 0 | BR-24 | "Consecutive" broken by any late or overdue bill |
| D-18 | 2026-11-05 | A bill fully covered by refund credit is paid on its bill date and counts as on time | A-07, E7 | It was settled before its due date |
| D-19 | 2026-11-05 | Refund credit is applied at the next bill generation even when the user has no new bill, to older unpaid bills | BR-12, A-09, E3 | Otherwise a frozen user's credit would never be used |
| D-20 | 2026-11-05 | Bureau file written at 00:00:00 on the 1st, after the month-end bill, before late fees and state checks | BR-25 | Shows the state as at the end of the last day of the month |
| D-21 | 2026-11-05 | Bureau amount = unpaid principal + conv fee + late fee + bounce + unbilled − credit, floored at 0 | BR-26 | GST excluded as the brief says; credit is money the user is owed |
| D-22 | 2026-11-05 | By default the run ends on the 1st after the last command, then continues until pending debit attempts and late fees are done; `--until` overrides | n/a | Last cycle billed and last month reported without extra input |

## Still waiting on the organisers

A-01 fee base, A-02 bill amount for late-fee tiers, A-03 GST scope, A-04/A-05 HARD_FREEZE restoration,
A-06 "full payment", A-07 credit-only bills, A-08 GROCERY cap, A-09 refund credit, A-10 first cycle.
Ask on the team assignment thread, then record each answer here.
