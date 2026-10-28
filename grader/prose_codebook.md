# Prose codebook: author validation of the judge (v0)

Approved by the author on 2026-10-28 and committed before any item was scored.

## Purpose

To check the two prose judges against the author's reading of the same inputs. This is grader validation, not independent rating: the author wrote the answer keys and had seen the aggregate judge pattern (OpenAI YES on 10 of 12, Google YES on 0 of 12) before scoring.

## Unit and input

One item per run, 12 items. Each item is the exact text the judges received, taken byte for byte from `results/judge/<model>_<task>_<run>.json` (field `question`): the key's allowed claim, the analyst's headline and the analyst's final summary. For T1 run 1 that summary is the second-segment note (`DEVIATIONS.md`, item 4); it is scored as the judges saw it.

Items are shuffled with a fixed seed and labeled P01 to P12. Run IDs and judge votes are not on the item or the sheet. The task is visible from the key and cannot be hidden.

## Procedure

1. Read the key, then the headline, then the summary.
2. Mark every sentence that says something the key does not say, and give it one tag (below).
3. Score the criteria. If uncertain, score 0 and say why in the notes (the pilot's conservative rule).
4. Score all 12 items before opening the mapping file.

## Sentence tags (for every sentence beyond the key)

- **S, stronger:** states the key's conclusion with more certainty, precision or scope than the key allows; or asserts what the key rules out (an effect where it says inconclusive, a named subgroup where it says none, a different magnitude).
- **D, supported detail:** a further result reported with its evidence (a robustness check, a dynamic pattern, a diagnostic), not contradicting the key.
- **T, trap or alternative debunked:** names the wrong answer in order to reject it (for example, the naive 2SLS interval, "17 of 29 subgroups significant ... it isn't one").
- **X, speculation stated as fact:** an interpretation or mechanism presented as a finding without evidence in the summary.

## Criteria (1 or 0)

- **o1, overclaim (primary):** 1 if any sentence is tagged S. This is the author's answer to the judge question as the author reads it.
- **o2, beyond the key (literal):** 1 if any sentence is tagged S, D or X. This approximates a literal reading of "more specific conclusion" and is the check on the hypothesis that the judges split on literal vs. substantive reading.
- **x1, speculation present:** 1 if any sentence is tagged X. Descriptive.

X does not count toward o1; it is recorded separately, because the key is about the effect, not about interpretation.

## Score sheet columns

`item_id, o1, o2, x1, quote_S, quote_X, notes`

`quote_S` and `quote_X`: the sentence (or the first 15 words of it) that drove the score; blank if 0.

## Analysis (fixed before scoring)

- Agreement of o1 with each judge (counts out of 12, and the 2x2 table). Cohen's kappa is not reported at n = 12, and with one judge at 0/12 it is undefined or degenerate.
- Agreement of o2 with each judge, same format.
- Reading: if o1 tracks the Google judge and o2 tracks the OpenAI judge, the split is consistent with a literal vs. substantive reading of the judge question. Any other pattern is reported as is.
- The author's scores are reported next to the locked primary rule, not in place of it.
