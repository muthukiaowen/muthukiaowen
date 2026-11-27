# Proposal P2 - Sampling from the complete daily fixture universe

Status: design only. The live rule (DAILY-1.1) is unchanged. Needs approval.

## Problem with the live rule
Selection happens at freeze time. Fixtures that enter the 48-hour window first take the day's 10 slots, so early kick-offs are over-represented and the outcome depends on when runs happen.

## Proposed rule
Separate **selection** from **freezing**.

1. **Draw.** For each kick-off day D (Kenya time), the first run at or after 12:00 EAT on day D-2 performs the draw for D. Fixtures are published weeks ahead, so the whole day is visible.
2. **Universe.** Every fixture in the covered leagues scheduled to kick off on D, as listed at the draw. The universe size, the ordered list of fixture IDs and a SHA-256 of that list are written to `sample_register.csv` (append-only, hash-chained).
3. **Selection.** Rank by SHA-256 of `"sample|" + D + "|" + fixture_id`; take the lowest 10. Nobody chooses, and anyone can recompute it from the register.
4. **Freeze.** Selected fixtures are frozen by the existing rule (inside 48 hours, at least 15 minutes before kick-off). A selected fixture without enough history is frozen as an abstention and is not replaced.
5. **Changes after the draw.** A selected fixture moved to another day stays selected. A fixture added to D after the draw is logged as outside the universe. Postponed fixtures stay in the sample as unresolved.
6. **If the draw run is missed,** the next run performs it and records the delay. Fixtures already inside 15 minutes of kick-off are logged as lost.

## Option for decision
Plain draw (above), or a cap of 3 fixtures per league per day so one league cannot fill the sample. The cap makes the sample more even but no longer proportional to the fixture list.

## Tests
- Same register, two machines: identical selection.
- Draw run at different times of day: identical selection.
- 30 fixtures on one day: exactly 10 selected; distribution by kick-off hour matches the universe within chance.
- Fixture rescheduled after the draw: still selected, logged.
- Existing frozen rows: byte-identical before and after.
