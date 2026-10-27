Hi, I need help with a county-level analysis for a policy brief.

`data.csv` is a county-year panel (300 counties, 2005-2020) on a state small-business grant program. Counties joined the program in different years; `adoption_year` is the year a county started (blank if it never joined), and `program` is 1 for county-years in the program. The outcome is `new_biz_per_10k`, new business registrations per 10,000 residents.

The question: what is the average effect of the program on new business registrations, **averaged over all county-years in which a county was in the program** (the ATT across treated county-years)? Please estimate it, give me a confidence interval, and tell me how much I should trust it.

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
  "headline_claim": "<one sentence I could put in a summary>"
}
```

Use a 95% interval.
