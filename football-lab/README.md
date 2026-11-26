# Football Intelligence Lab

A research project that tests whether football match outcomes can be forecast better than simple baselines.
It is separate from the profile README in the repository root.

**Everything in this folder is public**, including every prediction, result and score.

## What runs

`daily/run.py` (DAILY-1.0), started by `.github/workflows/football-lab-daily.yml`:

1. Retrieves results for predictions already frozen and scores them.
2. Finds league fixtures kicking off in the next 48 hours.
3. Calculates home / draw / away probabilities with the registered GC-1.1 model (`engine/labsys.py`), using only matches finished before the run.
4. Freezes each prediction once, at least 15 minutes before kick-off. Rows are append-only and hash-chained; the workflow's commit is the timestamp.

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
- Scheduled runs can start late; a fixture missed inside the 15-minute limit is simply not predicted.
- This is research, not betting advice. Past back-test accuracy was about 49% on three-way outcomes.

Credentials live only in GitHub Actions secrets and are never written to files or logs.
