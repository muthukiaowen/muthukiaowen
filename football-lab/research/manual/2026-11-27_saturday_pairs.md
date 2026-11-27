# Manual research run - Saturday 28 Nov 2026 fixtures, exploratory pair analysis

- Trigger: MANUAL (requested by the owner in chat). Not a scheduled GitHub execution.
- Executed: 2026-11-27 20:25-20:50 EAT (17:25-17:50 UTC), by Claude in a chat session.
- Pipeline run on GitHub: none. No prediction was frozen or changed by this run.
- Status: exploratory. Not a registered method. No pair has a tested track record.

## Universe
The 23 fixtures kicking off on 28 Nov (EAT) that the Lab froze on 26 Nov 2026 15:57 UTC (DAILY-1.0, GC-1.1 probabilities, pick = most likely outcome).
SportPesa's fixture list and odds were not collected (terms clauses 19.1, 24.1, 25.3). Reconciliation and market comparison: not done.

## Researched in depth: the nine fixtures with a frozen pick probability of 0.60 or more
Venue records: Wikipedia season results grids, read 27 Nov 20:30 EAT. Availability: starting11.com fixture pages (single source, "reported availability, not a confirmed team sheet").

| Fixture | Frozen pick | p | Home team at home (P-W-D-L, GF-GA) | Away team away | Reported absences | Pairing |
|---|---|---|---|---|---|---|
| Frosinone - Parma | H | 0.683 | 6-5-0-1, 16-6 | 5-1-0-4, 5-9 | Frosinone 1 out, 1 doubt; Parma 3 out, 2 doubts | eligible |
| Arouca - Rio Ave | H | 0.649 | 5-4-0-1, 9-3 | 5-1-0-4, 3-8 | none listed | rejected: grid only updated to 8 Nov; no availability information |
| Preston - Norwich | A | 0.648 | 8-2-1-5, 8-13 | 8-4-0-4, 19-12 | not found | rejected: no availability information |
| Real Betis - Rayo Vallecano | H | 0.643 | 6-5-0-1, 12-8 | 6-0-2-4, 6-14 | Betis 4 out, 3 doubts; Rayo 4 out, 2 doubts | eligible, with risk |
| Blackburn - Charlton | H | 0.636 | 8-5-0-3, 14-10 | 8-1-2-5, 7-18 | Blackburn 5 out, 2 doubts; Charlton 6 out, 1 doubt | eligible |
| Leeds - Coventry | H | 0.635 | 5-2-3-0, 7-3 | 5-1-0-4, 3-10 | not found | rejected: no availability information; Leeds drew 3 of 5 at home |
| Mainz - Union Berlin | H | 0.630 | 5-0-1-4, 7-12 | 4-0-1-3, 1-14 | Mainz 2 out; Union 6 out, 1 suspended, 1 doubt | rejected: Mainz have not won at home; probability rests on Union's four away games |
| Lincoln - Wolves | A | 0.624 | 8-1-2-5, 8-17 | 8-4-2-2, 13-11 | Lincoln 3 out; Wolves 5 out | eligible |
| Birmingham - Bolton | H | 0.618 | 8-4-4-0, 19-8 | 8-3-2-3, 11-14 | Birmingham 1 suspended, 2 out, 2 doubts; Bolton 5 out, 1 doubt | eligible, with risk (4 home draws in 8) |

Not researched beyond the frozen model output: the other 14 Saturday fixtures. Not collected for any fixture: last five results, tactics, likely line-ups, coaching changes, rest and travel, motivation.

## Pairs (ranked by the two frozen probabilities; joint figure assumes independence, which is not verified)
1. Frosinone H + Real Betis H - 0.683 x 0.643 = 0.44
2. Frosinone H + Blackburn H - 0.43
3. Frosinone H + Wolves A - 0.43
4. Frosinone H + Birmingham H - 0.42
5. Real Betis H + Blackburn H - 0.41

All five share one dependency: the same goals model on small venue samples, known from the back-test to be overconfident at high probabilities.

## Sources
- https://en.wikipedia.org/wiki/2026–27_Serie_A , 2026–27_Primeira_Liga , 2026–27_EFL_Championship , 2026–27_La_Liga , 2026–27_Premier_League , 2026–27_Bundesliga
- https://starting11.com/fixtures/frosinone-vs-parma , real-betis-vs-rayo-vallecano , fsv-mainz-05-vs-union-berlin , blackburn-vs-charlton , lincoln-vs-wolves , birmingham-vs-bolton , arouca-vs-rio-ave

## Tests at execution
Daily pipeline offline tests 21 of 21; engine tests 48 of 48.
