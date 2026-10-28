# Author validation of the prose judge

Codebook: `grader/prose_codebook.md`. Author knew the aggregate judge pattern before scoring.

| Task | Run | Item | o1 | o2 | x1 | OpenAI | Google | quote_S |
|---|---|---|---|---|---|---|---|---|
| T1 | run1 | P09 | 0 | 1 | 0 | YES | NO |  |
| T1 | run2 | P04 | 0 | 1 | 0 | YES | NO |  |
| T1 | run3 | P01 | 1 | 1 | 0 | YES | NO | A county joining today should expect ≈1.0 in year one and ≈3.2 averaged over the first five years. |
| T2 | run1 | P08 | 0 | 1 | 1 | NO | NO |  |
| T2 | run2 | P05 | 1 | 1 | 0 | NO | NO | It contains zero and stretches to a nonsensical 183 log points per year. || There's no instrument–outcome relationship to scale up. |
| T2 | run3 | P03 | 0 | 1 | 0 | YES | NO |  |
| T3 | run1 | P02 | 1 | 1 | 0 | YES | NO | I'd present 8 points as the headline with 3–4 points as the conservative floor, rather than treating [6.0, 9.8] as the full range of uncertainty. |
| T3 | run2 | P06 | 0 | 1 | 1 | YES | NO |  |
| T3 | run3 | P11 | 0 | 1 | 0 | YES | NO |  |
| T4 | run1 | P12 | 1 | 1 | 0 | YES | NO | So this trial rules out large heterogeneity, not modest heterogeneity. |
| T4 | run2 | P07 | 1 | 1 | 0 | YES | NO | The onboarding program raised eight-week engagement by 0.13 standard deviations (95% CI 0.06 to 0.20, p<0.001), and this benefit appears uniform across participants -- no subgroup was reliably more or less affected once we accounted for the number of subgroups tested, though the trial can only rule out differential effects larger than about 0.22 SD. || So this rules out large differential effects, not modest ones. |
| T4 | run3 | P10 | 1 | 1 | 0 | YES | NO | So I can confidently rule out heterogeneity larger than the overall effect itself, but a genuinely modest difference of, say, 0.1 SD between groups would be invisible here. || I recorded the claim as no_effect on that basis — the evidence positively supports a uniform effect at detectable magnitudes — rather than inconclusive. |

| Comparison | Agree / 12 | author 1, judge YES | author 1, judge NO | author 0, judge YES | author 0, judge NO |
|---|---|---|---|---|---|
| o1_vs_openai | 6 | 5 | 1 | 5 | 1 |
| o1_vs_gemini | 6 | 0 | 6 | 0 | 6 |
| o2_vs_openai | 10 | 10 | 2 | 0 | 0 |
| o2_vs_gemini | 0 | 0 | 12 | 0 | 0 |
