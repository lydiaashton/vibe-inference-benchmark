# Deviations and run observations

Logged after the lock (commit `39d6cc5`). Tasks, answer key, grader and runner are unchanged. No run was repeated or excluded.

## 2026-10-28: observations from the 12 locked runs

These are observations about how the runs went, not changes to the protocol.

### 1. Scratch files written outside the run folder

Each run started in its own folder outside the repository (`~/vib-bench-runs/runs/claude-opus-5/<task>/run<k>`). That folder was the working directory, not a sandbox: the harness flags limit the toolset (Bash, Read, Write, Edit, Glob, Grep) but do not limit which paths the agent can reach. In all 12 runs the agent wrote scratch scripts and intermediate files outside its run folder:

| Location | Runs |
|---|---|
| `/tmp/sbgrant` | T1 run1, T1 run2 |
| `/tmp/sbwork` | T1 run3 |
| `/tmp/iv_analysis` | T2 run1, T2 run3 |
| `/tmp/rts` | T2 run2 |
| `/tmp/iv_run3` | T2 run3 |
| `/tmp/work` | T3 run1 |
| `~/analysis` | T3 run2, T4 run2 |
| `~/work` | T3 run3 |
| `~/vib-bench-runs/runs/claude-opus-5/T4/scripts` | T4 run1 |
| `/tmp/ob_analysis` | T4 run3 |

Since folder names were reused, a later run could have come across an earlier run's files. The traces show two cases where it did:

- **T1 run2** reused `/tmp/sbgrant` from T1 run1. It overwrote run1's scripts with its own (via `cat > file`) and never read, listed or sourced any run1 file, including run1's cached `cs.rds`.
- **T2 run3** first wrote to `/tmp/iv_analysis`, T2 run1's folder. When a Write was refused because the file already existed, it ran `ls -la /tmp/iv_analysis/`, which showed run1's file names and sizes (`iv.py`, `robust.py`, `robust2.py`, `final_check.py`, `check.R`, `explore.py`). It read none of those files and moved to a new folder, `/tmp/iv_run3`. Its numbers (estimate 0.213, AR interval [-0.052, 1.83]) come from its own scripts and match the other two T2 runs, which had no such exposure.

T3 run2 and T4 run2 both used `~/analysis`, but the traces show no listing or reading of the other run's files.

**Answer key.** No trace mentions the repository path, `answer_key`, `truth.json` or the generators (string scan of all 12 traces). That is evidence the agent never looked for them, not proof it could not have reached them.

**README wording to correct.** The "Access" item in the LLM use disclosure says the agent "could not access" the answer key or any other task. The accurate statement is that the agent had no network tools and worked from a folder holding only the task's data and prompt, that the filesystem was not sandboxed, and that the traces show no access to the answer key and only the exposure described above. README corrected on 2026-10-28 (Access item and the sentence after the answer-key description).

**For future versions.** Run each agent in a container or under a filesystem sandbox, with a fresh `/tmp` for each run.

### 2. T1 run1: two result segments in the trace

T1 run1 started a background shell job (re-running `main.R` to re-read output that had scrolled past). After the agent wrote `answer.json` and returned its final result, the job reached its time limit and was stopped. That notification began a second, short segment in the same session: the agent explained that the job was redundant, re-ran a TWFE check and confirmed the numbers it had already reported. That segment did not modify `answer.json`.

`run_meta.json` takes the run's metadata from the last result event, so for this run it shows `num_turns: 2` and a 25-second API duration, which describe the second segment only. The first segment shows 20 turns and about 489 seconds. Wall time (884 s) covers the whole run; `total_cost_usd_equiv` ($1.48) covers both segments: the cost field in the trace is cumulative ($1.35 at the end of the first segment, $1.48 at the end of the second), while the turn and token counts are per segment. The grader reads `answer.json` and the full trace, so grading is not affected. The spec counts include the verification calls from the second segment.

### 3. Judge output files renamed (judge.py filename bug)

In `grader/judge.py`, `judge_run` reuses the name `model` for the model string each judge returns (`text, model = fn(prompt)`). The output file was then named after the last judge's served model (`gemini-4-argon_T1_run1.json`) rather than the model under test, so `grade.py` did not find the files and left the prose columns blank. The contents of each file were correct, including `model_under_test`.

Fix: the 12 files were renamed to `claude-opus-5_<task>_<run>.json`, using the `model_under_test` field in each file, and `grade.py` was rerun. No judge call was repeated and no judgment changed. `judge.py` itself is left as locked; anyone rerunning it should note that it will not recognize existing judge files and will judge again.

### 4. T1 run1: judge saw the second segment's summary

`judge.py` passes the judge the text of the last result event in the trace. Because of item 2, for T1 run1 that is the short note from the second segment (the TWFE re-check), not the analyst's main summary. The headline from `answer.json` was passed correctly. The judge's T1 run1 verdict therefore rests on the headline plus that note, not on the full write-up.

### 5. Leftover scratch folders

The folders in item 1 are still on the run machine. They are not part of the repository and are not used in grading.

### 6. Author validation of the prose judge: all 12 runs, with a codebook

The locked plan says the author would spot-check "about 5 transcripts" against the grader. After the judge results came in, the check was widened to all 12 judge inputs, scored against a codebook (`grader/prose_codebook.md`) that was committed and pushed before any item was scored, with items shuffled and run IDs and votes removed (`grader/prose_blind_pack.py`).

Why: the judges split 10/12 (OpenAI) vs 0/12 (Google), so the open question was which judge, if either, reads overclaiming the way the key intends. Checking only the YES runs would test for false positives and say nothing about false negatives, and with one judge at 0/12 the NO side carries half of the question. A selected subset of about 5 would also leave room to pick which runs to read after seeing the votes. Scoring all 12 against a rule fixed in advance removes that choice. The author knew the aggregate vote pattern before scoring, so this is grader validation, not independent rating. The locked primary rule (either judge YES) is unchanged; the author's scores are reported next to it.

### 7. A background Haiku call in each session

Each run's session-level usage lists two models: `claude-opus-5`, which served every agent turn in the trace, and `claude-haiku-4-5`, with one small call per run (about 1,250 to 1,450 input tokens and 14 to 21 output tokens, about $0.0013 to $0.0016 each, $0.02 in total). The Haiku call is made by Claude Code itself, not by the agent, and its content is not in the trace. `run_meta.json` records `models_seen` from the agent turns only, so it shows `claude-opus-5` alone. The README statement that `claude-opus-5` was "the only model served" was corrected on 2026-10-28 to say every agent turn was served by `claude-opus-5`, with the Haiku call noted. The reported cost ($14.94) includes the Haiku calls.
