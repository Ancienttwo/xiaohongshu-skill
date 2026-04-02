# Diagnosis Rubric

Use this reference with `metrics.csv` and `scripts/score_health.py`.

## Traffic Tiers

Score recent note performance by average views:

| Tier | Average views | Meaning |
|---|---:|---|
| 1 | <200 | Weak distribution or account not warmed |
| 2 | 200-499 | Basic distribution only |
| 3 | 500-1,999 | Usable baseline, still fragile |
| 4 | 2,000-19,999 | Healthy early traction |
| 5 | 20,000-99,999 | Strong natural distribution |
| 6 | 100,000+ | Breakout performance |

## Engagement Thresholds

Use engagement rate:

`(likes + collects + comments + shares) / views * 100`

Interpretation:

- `>= 5%`: strong
- `3% to <5%`: acceptable
- `<3%`: weak

## Exit Criteria For Initial Nurture

Treat the account as ready to move beyond nurture only if most of these are true:

- at least 5 recent notes recorded
- average views are 500+
- average engagement rate is 3%+
- no clear violation or suppression hints
- posting cadence is being maintained

If the account misses the threshold, extend the plan to D8-D10 and tighten note selection.

## Bottleneck Heuristics

Use this mapping when recommending next steps:

| Signal | Likely bottleneck | Typical fix |
|---|---|---|
| Low views, low engagement | poor topic choice or account readiness | narrow niche, improve keyword fit, extend nurturing |
| High views, low engagement | weak hook or cover mismatch | rewrite titles and covers, sharpen payoff |
| Some strong notes, many weak notes | inconsistent pattern selection | standardize content buckets and publishing rules |
| Good engagement, blocked distribution | possible compliance or account-state issue | review risky claims, account behavior, and public profile |

## Reporting Standard

A diagnosis is not complete until `06-health-report.md` includes:

- note count analyzed
- average views
- average engagement rate
- current tier
- pass/fail against exit criteria
- 3 concrete next actions
