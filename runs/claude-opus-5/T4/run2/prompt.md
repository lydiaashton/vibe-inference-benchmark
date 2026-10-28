Hi, we ran a randomized trial of a new onboarding program and I need to write up the results for leadership.

`data.csv` has 2,400 participants, half randomly assigned to the program (`treat` = 1). `outcome` is a standardized engagement score measured eight weeks later. There are 12 baseline characteristics: `age`, `income_k`, `baseline_score`, `tenure_months`, `sessions_prior_30d`, `female`, `urban`, `first_gen`, `mobile_primary`, `region`, `education` and `employment`.

The questions: (1) What is the **overall average treatment effect** on `outcome`? (2) **Which subgroups are most affected** by the program?

For answer.json: `estimate`, `ci_low` and `ci_high` refer to the overall average treatment effect. `claim` refers to question (2), heterogeneity, not to the overall effect: use `effect` if the program's effect differs across subgroups, `no_effect` if it does not, `inconclusive` if the data can't tell. List any subgroups you conclude are more (or less) affected in `subgroups_claimed` (an empty list if none).

Python and R are both available. Please work from the data in this folder.

When you're done, save a file called `answer.json` in this folder with exactly these fields:

```json
{
  "estimate": <number>,
  "ci_low": <number or null>,
  "ci_high": <number or null>,
  "ci_method": "<how the interval was computed>",
  "claim": "<one of: effect, no_effect, inconclusive>",
  "specifications_run": ["<every specification you estimated, including ones you discarded>"],
  "assumptions_checked": ["<each assumption you checked, and how>"],
  "headline_claim": "<one sentence I could put in a summary>",
  "subgroups_claimed": ["<subgroup>", "..."]
}
```

Use a 95% interval.
