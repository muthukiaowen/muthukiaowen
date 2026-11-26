# FID-v1.0 probability methodology — APPROVED for controlled prospective testing on 26 November 2026 (not a proven betting strategy)
Registered 26 November 2026. Engine: GC-1.1 in engine/labsys.py (the GC-1.0 calculation plus ranges, second outcome and scorelines). Back-test: engine/backtest.py, engine/backtest_gc11.json.

## Summary
FID probabilities come from one calculation, the venue-split Poisson core GC-1.0 (scripts/goals_core.py).
Injuries, suspensions, coaching changes, congestion and motivation are NOT converted into percentages, because the
Lab holds no data from which a defensible size for those effects can be estimated. They are recorded as coded
qualitative evidence and can affect the FID selection only through the fixed decision rule in section 6.

## 1. League base rates and reference period
Current season to date, from the league's own home and away tables read before kick-off:
LH = league home goals per match, LA = league away goals per match. No earlier seasons are used.
Home advantage is therefore the league's own, not a fixed constant.

## 2. Minimum data
League: at least 40 matches played. Each team: at least 4 games at the relevant venue.
If either fails, FID records "no probabilities: insufficient data" for the fixture. It does not fall back to estimates.

## 3. Home and away strength
Home team, home games only: goals for and against. Away team, away games only: goals for and against.
Each rate is shrunk toward the league mean with K = 4 games:
att_h = (homeGF + 4*LH)/(home games + 4);  def_a = (awayGA + 4*LH)/(away games + 4)
att_a = (awayGF + 4*LA)/(away games + 4);  def_h = (homeGA + 4*LA)/(home games + 4)

## 4. Points per game and goal difference
Not used in the calculation. Goals for and against already carry the goal-difference information, and using points
as well would count the same results twice. League position and points are recorded as descriptive evidence only.

## 5. From strength to probabilities, and normalisation
Expected goals: home = att_h * def_a / LH; away = att_a * def_h / LA.
Scores are treated as two independent Poisson variables; P(home), P(draw), P(away) are summed over all scorelines
up to 12 goals each and divided by their total, so they sum to exactly 100%. Reported to one decimal place.
Known weakness: an independent Poisson model tends to under-state draws. No correction is applied in v1.0, because
choosing a correction size without data would be an arbitrary adjustment.

## 6. Qualitative evidence and the selection rule
Each factor is recorded with: what, source, date, status (confirmed / reported / inferred), and direction
(favours home / favours away / favours caution, i.e. both sides weakened or likely to settle).
Factor types: key absence (a player with at least 25% of the team's league goals, or the first-choice goalkeeper),
coaching change in the last 21 days, fewer than 4 days since the previous match, nothing or everything at stake.
FID-A selection = the most likely outcome from section 5, EXCEPT:
if the top two outcomes are within 5.0 percentage points AND confirmed factors favouring the second outcome
outnumber confirmed factors favouring the first by 2 or more, FID-A selects the second outcome.
"Favours caution" factors count for the draw. Reported and inferred factors never count.
The 5-point and 2-factor thresholds are fixed decision rules, untested, and are not probability adjustments.
The probabilities themselves are never altered by qualitative evidence.

## 7. Avoiding double counting
One factor per cause per team (one injury crisis is one factor, however many players). Form is not a factor,
because recent results are already inside the goal totals. Table position is not a factor, for the same reason.

## 8. Missing information and coverage
Coverage rating: High = venue data plus team news from at least two sources for both teams; Medium = venue data
plus team news for one team or from one source; Low = venue data only. Coverage never changes the probabilities;
on Low coverage the override in section 6 cannot fire, because no confirmed factors exist.

## 9. FID-F (after market comparison)
FID-F = FID-A unless the market comparison leads to a verifiable football fact that Stage A missed
(for example confirmed team news behind a price move). In that case the fact is added to the register, the rule in
section 6 is re-applied, and both versions are kept. A price difference alone never changes the selection.

## 10. Reproducibility
Inputs for every fixture are stored in the round's fid_inputs.csv with source and read time. Running
scripts/goals_core.py on those inputs reproduces every probability exactly; there is no random element.

## 11. Relation to S2
GC-1.0 is the same calculation proposed for S2. If both are approved, S2 and FID-A will carry identical
probabilities, and FID will differ from S2 only where the section 6 rule changes the selection. This is stated
so the two are not mistaken for independent evidence. The earlier registered description of S2 mentioned
"documented absence adjustments"; that is withdrawn for the same reason as above, as a recorded correction made
before S2's first use.

## 12. Worked example (outside the 29 November round)
Hoffenheim v Augsburg, Bundesliga, 29 November 2026. Source: Sports Mole home and away tables, read 26 Nov 2026.
League: 186 home goals and 119 away goals in 90 matches -> LH 2.067, LA 1.322.
Hoffenheim at home: 5 games, 11 for, 8 against. Augsburg away: 4 games, 11 for, 13 against.
att_h = (11 + 8.267)/9 = 2.141; def_a = (13 + 8.267)/8 = 2.658; att_a = (11 + 5.289)/8 = 2.036; def_h = (8 + 5.289)/9 = 1.477
Expected goals: home 2.141*2.658/2.067 = 2.754; away 2.036*1.477/1.322 = 2.274.
Probabilities: home 49.3%, draw 17.9%, away 32.8%. Selection: Home (lead 16.5 points, so the override cannot apply).

## 13. Selection override as approved (26 November 2026)
Stored and scored for every FID row: the original highest-probability selection (core_pick), the override selection
(pick), and the original H/D/A probabilities (never changed by the override).
Eligible factors: key absence (a player with at least 25% of the team's league goals, or the first-choice goalkeeper),
coaching change in the last 21 days, fewer than 4 days since the previous match, nothing or everything at stake.
Evidence standard: category verified_fact, state confirmed, with source URL; and at least one corroborating source
recorded in corroborated_by. Conflict handling: a claim contradicted by an equal or better source is 'disputed' and
cannot count. Duplicate-cause prevention: one factor per team per factor type.
