Hi, I'm working on a returns-to-schooling paper and need a second pair of hands.

`data.csv` has 1,500 adults: `log_wage`, `years_school`, `dist_college_miles` (distance from their childhood home to the nearest four-year college), `parent_educ` (years) and `female`. Schooling is obviously endogenous (ability), so we're instrumenting it with distance to college, controlling for parent education and sex.

The question: what is the **causal effect of one additional year of schooling on log wages** (the coefficient on years_school)? Please estimate it, give me a confidence interval, and tell me what we can say in the paper.

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
  "first_stage_F": <number>
}
```

Use a 95% interval.
