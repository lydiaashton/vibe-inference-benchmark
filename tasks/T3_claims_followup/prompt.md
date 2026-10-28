Hi, I'm evaluating a care-navigation program for a regional health plan and need an estimate for the program review.

Starting July 1, 2025, 30 of our 60 primary care practices began a care-navigation program for their members who visit the emergency department. The other 30 practices did not. There are two files in this folder:
- `claim_lines.csv.gz`: our claims extract, one row per claim line, Jan 1, 2025 through Jan 14, 2026. Columns: `claim_id`, `line_no`, `member_id`, `practice_id` (the member's attributed primary care practice), `service_date`, `pos` (place of service), `claim_type` (professional or facility), `cpt_hcpcs`, `revenue_code`, `rendering_specialty` and `allowed_amount`.
- `practices.csv`: `practice_id`, `program` (1 if the practice is in the program) and `launch_date`.

The question: what is the **effect of the program on the 14-day ED-to-PCP follow-up rate**, meaning the share of ED visits (Jan 1 to Dec 31, 2025) that are followed by a PCP visit by the same member on the same day or within the 14 days after? Please estimate it as a difference-in-differences (program vs. other practices, before vs. after July 1, 2025), **in percentage points**, give me a confidence interval, and tell me whether the program worked.

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
  "n_ed_visits": <number of ED visits in the denominator of the follow-up rate, all of 2025>
}
```

Use a 95% interval.
