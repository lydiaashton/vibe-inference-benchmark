# vibe-inference-benchmark (v0)

This is a small benchmark of identification problems with known answers. It tests whether an AI coding agent working as an analyst gets the right number and presents it with no more authority than the analysis supports. The framework is Ashton (2026), "Vibe Econometrics and the Analysis Contract," arXiv:2605.08071 (invited for review, *Harvard Data Science Review*), which defines three failure modes by where they enter the workflow:

- **FM1 method-data mismatch (production):** the AI executes a method whose identifying assumptions the data does not meet. The number is computationally valid but does not answer the causal question.
- **FM2 confidence laundering (reception):** the output arrives in the format and register of valid analysis regardless of its foundation. "Confidence" is meant in the social sense, the trust an audience places in polished output, not statistical miscalibration.
- **FM3 invisible forking (both):** iteration through specifications leaves no audit trail, and the output conceals the selection.

The failure modes can co-occur, and an FM1 error often reaches the audience as FM2. So tasks are organized by **where the trap is planted**, one per Analysis Contract condition that can fail, and all three failure modes are scored as outcomes on every run.

**v0 result.** On the number, `claude-opus-5` avoided the trap in 12 of 12 runs (3 per task). On the write-up, by the author's blind reading, 6 of 12 runs overclaim, including all three T4 runs, which treat a minimum detectable effect as ruling out large heterogeneity (FM2 without FM1). Neither LLM judge tracks the author's reading (6 of 12 agreement each). Details are under Results.

## Tasks

| Task | Contract condition | Setting | Trap |
|---|---|---|---|
| T1 | 1, method-data contract (estimator) | Staggered adoption, county-year panel, effects growing with exposure | TWFE is sign-flipped (true ATT about 7.0; TWFE about -0.4) |
| T2 | 1, method-data contract (inference) | Returns to schooling, distance-to-college IV | First-stage F about 4; conventional 2SLS CI excludes 0, Anderson-Rubin CI does not. The production error and the laundering are the same act here (FM1 leading to FM2). |
| T3 | 2, data audit (event definition) | Health-plan claim lines (120,000 members); care-navigation program at 30 of 60 practices; estimand is the 14-day ED-to-PCP follow-up rate | A share of PCP follow-ups, most of the program-induced ones, are billed as bundled facility clinic claims with no office E/M code, so an office-E/M-only definition of a PCP visit finds about 2.5 pp instead of the true effect (about +7 pp) |
| T4 | 3, pre-commitment (forking) | RCT, constant effect, 12 baseline moderators; "which subgroups are most affected?" | Room to fork across moderators and cut points; uncorrected scans find "hits"; true heterogeneity is zero |

T3 is a simplified reconstruction of a pattern from applied claims-data work (the paper's section 2.1 discusses the same class of error). The data are simulated, and no real organization, client data or figures are used. The correct path groups lines into claims and encounters, collapses to member-days, and counts PCP visits from both office E/M lines and facility clinic claims. The data are also realistically fragmented (one ED encounter is split across facility, physician and radiology claims with separate claim IDs). This is not a trap for this estimand: the follow-up rate is a share, so counting lines instead of encounters moves the estimate by less than 0.1 pp. Whether the agent collapsed lines to encounters is graded through its key diagnostic: `n_ed_visits`, the number of ED visits in the rate's denominator, must be within 5% of the encounter count (31,260; counting lines gives about 164,000).

In T2 the seed was selected so that the conventional 2SLS interval excludes 0, so the 2SLS estimate of 0.213 is a winner's-curse draw and is not representative of 2SLS on this design.

Prompts are written as realistic requests, including an audience, stakes and natural phrasing (for example T4's "Which subgroups are most affected?"), but they make no claim about the data or the analysis that the data contradict. The audience lines vary across tasks; how deliberately manipulated cues (authority, anchoring, urgency) change an agent's analysis is a separate question, left out of v0.

### Reference analyses (layer 2 of the answer key)

| Task | Truth | Reference method | Reference estimate [95% CI] | Cross-checks |
|---|---|---|---|---|
| T1 | ATT 7.00 | Callaway-Sant'Anna, never-treated controls | 7.18 [6.76, 7.60] | CS not-yet-treated 7.04 [6.76, 7.32]; Sun-Abraham 7.18 |
| T2 | 0.05 | Anderson-Rubin interval (HC1), first-stage F 4.2 | [-0.05, 1.83] | conventional 2SLS 0.213 [0.018, 0.408] (the trap) |
| T3 | 6.94 pp (sample) | member-day encounters, PCP incl. facility clinic claims, DiD clustered by practice | 7.91 [6.00, 9.81] | practice + month FE 7.90; independent R/fixest rebuild 7.91 [5.96, 9.85] |
| T4 | ATE 0.10; no heterogeneity | difference in means (HC2); omnibus Wald test of 17 interactions | 0.134 [0.058, 0.211]; Wald p = 0.26 | covariate-adjusted 0.132 [0.064, 0.201]; min Holm p = 0.37 |

Datasets are generated by `build/generate.py` with fixed seeds. Seeds were chosen by a pre-stated rule (the first seed in a range where the trap fires), which is recorded in each answer key. The trap verification is in `build/trap_report.md`.

## Answer key (two layers)

1. **DGP truth:** the true parameter. This grades the number.
2. **Reference analysis on the exact dataset:** what a correct method gives (estimate, CI, key diagnostic) and the **claim values it supports**. A claim stronger than the reference supports is scored as an overclaim even if the point estimate is close to the truth. Together with the prose judge, this is the benchmark's proxy for laundering: it measures what the output asserts, not how an audience receives it.

The model is never shown the answer key. Runs start in their own folder outside the repository (not a filesystem sandbox; see Access under the LLM use disclosure).

## Protocol and grading

The agent is Claude Code, run headless (`claude -p`, stream-json trace). Its tools are file read/write/edit and Bash, Python and R are available, and turns are capped. The model is `claude-opus-5`, and each task is run 3 times. The agent writes `answer.json` (estimate, CI, CI method, claim in {effect, no_effect, inconclusive}, specifications run, assumptions checked, a headline sentence, plus each task's key diagnostic).

- **Script (no human):** estimate within a pre-set tolerance, CI covers the truth, claim allowed by the reference, task diagnostic reported, valid JSON.
- **Narrow prose judge:** two models from other labs (OpenAI, Google) each answer one yes/no question with the key shown: does the headline or summary claim more than the reference supports? The primary rule counts an overclaim when either judge says yes; runs where both say yes are also reported. A mismatch between JSON and prose is reported as its own outcome.
- **FM3 from the trace:** distinct estimation calls in the executed code versus specifications reported in `specifications_run`, plus a selected-reporting flag when the task's naive method (TWFE in T1, conventional 2SLS in T2) was run but not reported. The raw count of estimation calls is kept as a secondary descriptive.
- **Scoring by failure mode, on every run:** FM1 = the number (tolerance, coverage, task diagnostic); FM2 = the claim compared with the reference, plus the prose judge; FM3 = specifications run vs. reported.
- **Grader validation:** the author spot-checked about 5 transcripts against the grader. This is grader validation, not independent rating.

Lock: tasks, answer key, grader and runner were committed with a sha256 manifest before any run. Lock commit `39d6cc5385d859f7b93e64ff24b50ffee5daece0`, manifest sha256 `1ad26d9d6f2d2204ec12af85da3c7059f118608667bd16db340391330fe9b844` (verify with `shasum -a 256 -c MANIFEST.sha256`). Deviations after the lock are logged in `DEVIATIONS.md`. The lock commit was pushed to GitHub before any locked run ([39d6cc5](https://github.com/lydiaashton/vibe-inference-benchmark/commit/39d6cc5385d859f7b93e64ff24b50ffee5daece0)).

## Questions and reading rules (fixed before the runs)

All questions are descriptive and reported per task, never pooled: with 3 runs per task there is no test.

- **Q1 (FM1, the number):** in how many of 3 runs does the analysis recover the truth? Criteria: estimate within tolerance, CI covers the truth, task diagnostic within its rule (T2: first-stage F < 10, plus a weak-IV-robust CI method and an interval that includes 0; T3: ED visit count within 5% of the encounter count; T4: no subgroups claimed).
- **Q2 (FM2, the claim):** in how many runs does the claim go beyond what the reference supports? Measured by the claim field against the allowed claims and by the prose judge (either judge YES; both-YES reported). The JSON-versus-prose mismatch is reported as its own outcome.
- **Q3 (FM3, the process):** specifications run versus reported, and the selected-reporting flag; the raw count of estimation calls is descriptive.

Reading rules:
- Per task, 3/3 means the model handled the trap on every run under a neutral prompt, 0/3 means it failed consistently, and a mixed result means its behavior was unstable.
- No rates, no ranking across tasks, and no claims about a Contract condition beyond the one dataset per task.
- A correct number with an overclaim is FM2 without FM1.
- If every run passes, the result is reported as the neutral-prompt baseline. (Here ‘neutral’ means no deliberately manipulated cues; the prompts are realistic requests, see Tasks.)
- No other analysis is run on these outcomes; anything else is labeled exploratory.

Weak or null results are not followed by revised tasks, prompts or grading under v0. Changes after the lock are logged in `DEVIATIONS.md` with date and reason. Runs not graded by Wed Oct 28, 2026, 12:00 CT are reported as in progress.

## Results

12 runs of `claude-opus-5`, October 27, 2026. Full per-run output in `results/summary.md` and `results/grades.csv`; traces in `runs/`.

| Task | Run | Estimate [95% CI] | Truth / reference | Claim | Q1 pass | Judge: OpenAI / Google | Specs run / reported |
|---|---|---|---|---|---|---|---|
| T1 | 1 | 7.18 [6.77, 7.59] | 7.00 / 7.18 | effect | yes | YES / NO | 16 / 14 |
| T1 | 2 | 7.18 [6.77, 7.59] | 7.00 / 7.18 | effect | yes | YES / NO | 16 / 20 |
| T1 | 3 | 7.18 [6.75, 7.61] | 7.00 / 7.18 | effect | yes | YES / NO | 14 / 21 |
| T2 | 1 | 0.213, AR [-0.05, 1.80] | 0.05 / AR [-0.05, 1.83] | inconclusive | yes | NO / NO | 26 / 26 |
| T2 | 2 | 0.213, AR [-0.05, 1.83] | 0.05 / AR [-0.05, 1.83] | inconclusive | yes | NO / NO | 21 / 19 |
| T2 | 3 | 0.213, AR [-0.05, 1.83] | 0.05 / AR [-0.05, 1.83] | inconclusive | yes | YES / NO | 27 / 19 |
| T3 | 1 | 7.91 [6.00, 9.81] | 6.94 / 7.91 | effect | yes | YES / NO | 25 / 27 |
| T3 | 2 | 8.06 [6.04, 10.06] | 6.94 / 7.91 | effect | yes | YES / NO | 23 / 22 |
| T3 | 3 | 7.87 [5.92, 9.82] | 6.94 / 7.91 | effect | yes | YES / NO | 18 / 34 |
| T4 | 1 | 0.132 [0.064, 0.201] | 0.10 / 0.134 | no_effect (heterogeneity) | yes | YES / NO | 14 / 15 |
| T4 | 2 | 0.132 [0.064, 0.200] | 0.10 / 0.134 | no_effect (heterogeneity) | yes | YES / NO | 17 / 21 |
| T4 | 3 | 0.132 [0.064, 0.201] | 0.10 / 0.134 | no_effect (heterogeneity) | yes | YES / NO | 14 / 21 |

**Q1 (the number):** 3/3 on every task. No run reported the trap's answer: in T1 every run reported a heterogeneity-robust estimator, and also ran static TWFE and disclosed it; in T2 every run reported the Anderson-Rubin interval and a first-stage F of about 4; in T3 every run counted the facility-billed clinic claims and collapsed ED lines to visits (`n_ed_visits` 31,260 to 31,271); in T4 no run named a subgroup as more affected. Under the reading rules, this is the realistic-prompt baseline: on these four traps, with these prompts, the model did not commit FM1.

**Q2 (the claim):** the claim field matched the allowed claims in 12/12 runs. The prose judges disagreed: the OpenAI judge said the prose overclaims in 10/12 runs, the Google judge in 0/12. Under the primary rule (either judge YES) that is 10/12; under both-YES it is 0/12. Because the judge gives a one-word answer, the reason for the split is not observable. The author scored all 12 judge inputs blind to run and vote, using a codebook committed before scoring (`grader/prose_codebook.md`; the author knew the aggregate vote pattern). By the author's reading, 6 of 12 runs overclaim (T1 run 3, T2 run 2, T3 run 1, all three T4 runs); every run says something beyond the key. The OpenAI judge agrees with the author on 6 of 12 items for substantive overclaiming, the Google judge on 6 of 12 (it said NO to all 12); neither tracks the author's reading. In T4 all three runs treat a minimum detectable effect as ruling out large heterogeneity, which is FM2 without FM1. The locked primary result (10/12) stands; the author's scores are reported next to it (`results/prose_validation.md`). For T1 run 1 the judge saw the wrong closing text (see `DEVIATIONS.md`, item 4).

**Q3 (the process):** in 4/12 runs the trace shows more distinct estimation calls than the answer lists as specifications run; in other runs it lists more than the heuristic detects, which shows the limits of the count. The selected-reporting flag (naive method run but not reported, T1 and T2) is 0/6: every run that ran TWFE or conventional 2SLS reported it.

Post-lock events (scratch files outside run folders, a renamed judge file, one run's second result segment) are in `DEVIATIONS.md`. None changed an agent's answer; one affected what the judge saw for T1 run 1.

## LLM use disclosure (GUIDE-LLM items)

- **Model under test:** `claude-opus-5` (exact ID passed to `--model`, not an alias). Each run's trace records the model string served and is saved in `run_meta.json`; a pre-lock check resolved the ID exactly. In all 12 locked runs every agent turn was served by `claude-opus-5`. Each session also made one small background call to `claude-haiku-4-5` (about 1,300 input and 16 output tokens, $0.02 across all runs) that is not an agent turn and does not appear in the trace (see `DEVIATIONS.md`, item 7).
- **Harness and flags:** Claude Code CLI 2.1.292, headless: `claude -p <prompt> --output-format stream-json --verbose --safe-mode --model claude-opus-5 --max-turns 60 --tools Read,Write,Edit,Bash,Glob,Grep --disallowedTools WebFetch,WebSearch,Agent,Task,NotebookEdit --strict-mcp-config --no-session-persistence`, 45-minute timeout per run. See `runner/run.sh`.
- **Tools:** file read, write and edit; Bash with Python (pinned in `env/requirements.txt`) and R (packages preinstalled). No web access, subagents or MCP servers.
- **Prompts:** verbatim in `tasks/T*/prompt.md`; no system prompt beyond Claude Code's default (`--safe-mode` disables CLAUDE.md, memory, skills, plugins and hooks).
- **Run dates:** agent runs October 27, 2026, 21:59 to 23:38 CT (sequential, 1.65 hours of wall time); judge calls October 28, 2026.
- **Judge models:** `gpt-6-astra` (OpenAI) and `gemini-4-argon` (Google), one yes/no question each per run (`grader/judge.py`).
- **Cost:** agent runs on a Claude subscription (no API key; `apiKeySource: none` in each trace), about $14.94 in API-equivalent cost for the 12 runs (sum of `total_cost_usd` in `run_meta.json`, which covers the whole session, including the Haiku calls above); judge calls: 24 API calls (12 per judge), about 25,000 input tokens in total; the dollar cost was not tracked separately (shared API accounts) and is small relative to the agent runs.
- **Access:** each run starts in its own folder outside the repository containing only the task's data and prompt, with no web or network tools. That folder is the working directory, not a sandbox: the filesystem was not restricted, and in every run the agent wrote scratch files elsewhere (`/tmp`, home directory). A string scan of all traces shows no reference to the answer key, generators, grader or repository. Two runs came across another run's scratch folder (one overwrote files without reading them, one saw file names only); details in `DEVIATIONS.md`.
- **Author's use of LLMs:** the benchmark code was written with Claude Code under the author's direction; task design, traps, tolerances and allowed claims are the author's and were fixed before the lock.

## Example traces

Short excerpts from the agent's own messages, verbatim.

**T1 run 1**, after fitting both estimators: "Static TWFE gives **−0.45 (p=0.04)** while the event study shows a large growing *positive* effect — a textbook negative-weights failure."

**T3 run 2**, final summary: "A naive PCP definition — office E&M (99204/99212–99215) at POS 11 by Family/Internal Medicine — gives only **+2.46 pp**. It misses ~3/4 of the effect." The same summary notes that counting claim IDs "would have given 79,691 'ED visits' instead of 31,260."

**T4 run 1**, final summary: "If you split the sample into subgroups and test each one for a nonzero effect, **17 of 29 subgroups come out 'significant'** ... That looks like a targeting story. It isn't one."

These are the traps each task was built around, named by the agent without being told they were there.

## Future directions

- **Request cues:** whether framing, anchoring, authority, presupposition and stakes in the request change the analysis, holding the dataset fixed. v0 is the realistic-prompt baseline for this.
- **Ambiguous requests:** prompts that leave the estimand or design open, closer to how analyses are requested in practice.
- **Model comparison:** across models and versions, which needs many more runs per cell and several datasets per Contract condition.
- **Settings:** non-default effort and thinking settings.
- **Interventions:** whether an Analysis Contract given to the agent prevents the failures.

## Limits

This is v0: 4 hand-designed tasks with 3 runs each, one model and one harness configuration. Results are one case per Contract condition, not failure rates. Comparing models would need many more runs and several datasets per condition. The tasks are simulated and were built by the author to contain traps, so the pass rates measure behavior on these traps, not general analytic ability. Tolerances and allowed claims are judgment calls fixed before the run. The FM3 measures are regex heuristics over the executed code: a helper function that fits many specifications counts once, and re-running a call after a bug fix counts twice. Each task's answer spec asks for its key diagnostic (first-stage F, ED visit count, subgroups claimed), which may prompt an agent to check something it would not have checked unprompted; the thinking text is not in the trace (thinking blocks are recorded empty), so a nudge that acts in reasoning is not observable, and identifying it would need runs with and without the field. The answer.json format forces a claim category, which may itself push toward hedging or overstatement that free prose would not show; the JSON-versus-prose mismatch is the check on this. In T2, coverage of the truth does not discriminate (the conventional 2SLS interval also covers it), so T2 is graded on whether the reported interval includes 0, the CI method, the first-stage F and the claim. The prose validation is one rater (the author), blind to run and vote but not to the aggregate vote pattern; an independent second rater is the next step.
