# Proposal P1 - Independent missed-run monitor

Status: design only. Not deployed. Needs approval.

## Problem
A scheduled slot that GitHub never starts leaves no log row, no commit and no email. The 00:23 EAT slot on 27 Nov 2026 was lost this way.

## Design: three layers, each outside the one before it

1. **Gap detection inside every run (same system, detects late).**
   Each run reads `run_evidence.csv`, lists the expected slots since the last recorded run (03:23, 09:23, 15:23, 21:23 UTC) and writes any slot with no run started within 90 minutes to `missed_slots.csv`. Cheap, but silent if runs stop altogether.

2. **External dead-man's switch (different system, detects when nothing runs).**
   The last workflow step sends one HTTPS ping to a heartbeat-monitoring service. The service expects a ping every 6 hours with a 90-minute grace period and emails the owner when one is absent. The ping URL is stored as a GitHub secret (`HEARTBEAT_URL`). A failed run sends a "fail" ping instead.
   Requires: a free account with a heartbeat service, created by the owner. No cost on a free tier; to be confirmed before sign-up.

3. **Independent reader (third system, verifies content rather than liveness).**
   A daily check outside GitHub Actions reads the public `run_evidence.csv` and `predictions.csv`, confirms four slots ran, the hash chain verifies and no frozen row changed, and reports to the owner.

## Mitigation worth considering separately
The run is idempotent, so it can be scheduled hourly instead of six-hourly. A dropped slot then costs one hour rather than six. Cost: 9 football-data.org requests per run (216 a day; that provider's limit is per minute, not per day). This is a schedule change and needs approval.

## Tests
- Remove a slot from a copy of `run_evidence.csv`: layer 1 lists exactly that slot.
- Run late by 30 minutes: not reported as missed. Late by 2 hours: reported.
- Disable the workflow for one slot: layer 2 emails within grace period.
- Alter one frozen row in a copy: layer 3 reports a broken chain.

## Addendum, 27 Nov 2026 - observation and heartbeat service findings

### Observation so far
Four expected slots on 27 Nov (00:23, 06:23, 12:23, 18:23 EAT). GitHub created one run (06:40, run 45935517542, schedule). The Actions page lists no failed, cancelled or skipped runs for the other slots: they were not triggered. Cause unknown.

### Candidate service: Healthchecks.io, free "Hobbyist" plan (pricing page read 27 Nov 2026)
- $0 a month; 20 checks; 100 log entries kept per check (about 25 days at four pings a day).
- Not stated on the pricing page, to confirm at sign-up: whether a card is needed, which alert channels the free plan includes, shortest period and grace settings.

### Limitations to accept before deployment
1. It reports a missed run; it does not start one. Predictions for fixtures in a missed window are still lost.
2. Alerts arrive after the grace period, so detection lags the slot by that long (proposed: 90 minutes).
3. With the current schedule missing most slots, it would alert several times a day until scheduling is fixed. It measures the problem; it does not solve it.
4. It depends on a third party's free plan, which can change or end.
5. The ping address works like a password: anyone holding it can fake a heartbeat. It must live in a GitHub secret (`HEARTBEAT_URL`) and never appear in logs.
6. A run that starts but hangs sends no ping; that is reported as missed, which is correct but not distinguishable from "never started" without the start ping as well.
7. Account creation and alert email belong to the repository owner; Claude does not create the account or handle the address.

### Not yet investigated
Alternative free services, and an external scheduler that would start the workflow (which would need an access token created by the owner).
