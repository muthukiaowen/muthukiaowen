# Football Intelligence Lab

A research project that tests whether football match outcomes can be forecast better than simple baselines.
It is separate from the profile README in the repository root.

**Everything in this folder is public**, including every prediction, result and score.

## What runs

`daily/run.py` (DAILY-1.1), started by `.github/workflows/football-lab-daily.yml`:

1. Retrieves results for predictions already frozen and scores them.
2. Finds league fixtures kicking off in the next 48 hours.
3. Calculates home / draw / away probabilities with the registered GC-1.1 model (`engine/labsys.py`), using only matches finished before the run.
4. Freezes each prediction once, at least 15 minutes before kick-off. Rows are append-only and hash-chained; the workflow's commit is the timestamp.

**Pick rule (DAILY-1.1, from 26 Nov 2026).** The pick is the most likely outcome, except that the draw is picked when the home and away probabilities are within 5 points of each other. The probabilities themselves are unchanged. The 5-point threshold is a first setting and has not been tested; the scoreboard reports draw picks separately and also what the plain most-likely pick would have scored. Rows frozen under DAILY-1.0 keep their original picks.

**Sample.** At most 10 fixtures are frozen per kick-off day (Kenya time). They are chosen by a hash of the fixture ID, so nobody selects them.

A fixture without enough history (fewer than 40 league matches, or fewer than 4 venue games for either team) is recorded as an abstention with no pick.

## Files

| Path | Contents |
|---|---|
| `data/daily/predictions.csv` | Frozen predictions and abstentions |
| `data/daily/results.csv` | Final results |
| `data/daily/scoreboard.json` | Accuracy, Brier score, log loss, calibration, by competition and by day |
| `data/daily/run_log.csv` | Every run: requests made, leagues that failed, rows added |
| `data/daily/api_football_probe.json` | Plan and quota check for the second provider |
| `engine/` | Registered model, lineage register, tests, historical back-test |

## Limits

- Source: football-data.org free plan, 9 league competitions (PL, ELC, BL1, SA, PD, FL1, DED, PPL, BSA). Cups are not modelled.
- No bookmaker prices are collected, so the benchmark here is the league base rate and an always-home pick, not the market.
- The model uses goals only. It knows nothing about injuries, line-ups or tactics.
- Known sampling bias (recorded 27 Nov 2026, rule unchanged during verification): the hash only ranks fixtures within one run, so fixtures that enter the 48-hour window first take the day's 10 slots. Early kick-offs are favoured. The 32 rows frozen on 26 Nov predate the cap and are not a sample.
- A scheduled slot that GitHub never starts leaves no record. The 00:23 EAT slot on 27 Nov did not run.
- Scheduled runs can start late; a fixture missed inside the 15-minute limit is simply not predicted.
- This is research, not betting advice. Past back-test accuracy was about 49% on three-way outcomes.

Credentials live only in GitHub Actions secrets and are never written to files or logs.
