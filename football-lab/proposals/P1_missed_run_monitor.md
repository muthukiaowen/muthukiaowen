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
