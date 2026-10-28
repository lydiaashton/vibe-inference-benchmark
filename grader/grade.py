"""Mechanical grader. Reads runs/<model>/<T>/run<k>/{answer.json, trace.jsonl} and answer_key/<T>/truth.json.
Optionally merges judge results from results/judge/<model>_<T>_run<k>.json.
Writes results/grades.csv, results/grades.json and results/summary.md.
Run: python3 grader/grade.py   (standard library only)
"""
import csv
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = {"effect", "no_effect", "inconclusive"}

# Estimation calls counted in the trace for the FM3 specs-run vs specs-reported comparison.
EST_PATTERNS = [
    r"\blm\s*\(", r"\bglm\s*\(", r"\bfeols\s*\(", r"\bfeglm\s*\(", r"\blm_robust\s*\(", r"\biv_robust\s*\(",
    r"\bivreg\s*\(", r"\bfeols\s*\(.*\|.*~", r"\batt_gt\s*\(",
    r"\bcausal_forest\s*\(", r"\bsmf\.(ols|wls|glm|logit|probit)\s*\(", r"\bsm\.(OLS|WLS|GLM|Logit|Probit)\s*\(",
    r"\bIV2SLS\b", r"\bIVLIML\b", r"\bPanelOLS\b", r"\bLinearRegression\s*\(",
]
# FM3 primary measure: distinct estimation-call signatures (call name + normalized argument text) in executed or
# written code, compared with len(specifications_run). Heuristic: a helper wrapping one call counts once however
# many specs it fits, and re-running a call after a bug fix counts twice.
CALL_RE = re.compile(r"\b(lm|glm|feols|feglm|lm_robust|iv_robust|ivreg|att_gt|causal_forest|smf\.(?:ols|wls|glm|logit|probit)|"
                     r"sm\.(?:OLS|WLS|GLM|Logit|Probit)|IV2SLS(?:\.from_formula)?|IVLIML(?:\.from_formula)?|"
                     r"PanelOLS(?:\.from_formula)?|LinearRegression)\s*\(")
# Selected-reporting flag: the task's naive method appears in executed code but specifications_run never names it.
# (code pattern, disclosure pattern). Only T1 and T2 have a naive method identifiable from code.
NAIVE = {
    "T1": (r"feols\s*\([^)]*\bprogram\b[^)]*\|\s*county_id\s*\+\s*year|C\(\s*county_id\s*\)\s*\+\s*C\(\s*year\s*\)|"
           r"EntityEffects\s*\+\s*TimeEffects|TimeEffects\s*\+\s*EntityEffects", r"TWFE|two[- ]way|fixed[- ]effects?"),
    "T2": (r"IV2SLS|ivreg\s*\(|iv_robust\s*\(|feols\s*\([^)]*\|[^)]*~", r"2SLS|two[- ]stage|ivreg|IV regression"),
}
CONTAMINATION = re.compile(r"answer_key|truth\.json|dgp\.json|build/generate|build/finalize|identification-benchmark", re.I)


def tool_code(trace_path):
    """Concatenate code the model executed or wrote: Bash commands plus Write/Edit file contents."""
    chunks, n_bash, final_text = [], 0, ""
    for line in trace_path.read_text(errors="replace").splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "assistant":
            for c in ev.get("message", {}).get("content", []):
                if c.get("type") != "tool_use":
                    continue
                inp = c.get("input", {})
                if c.get("name") == "Bash":
                    n_bash += 1
                    chunks.append(inp.get("command", ""))
                elif c.get("name") in ("Write", "Edit"):
                    chunks.append(inp.get("content", "") or inp.get("new_string", ""))
                    chunks.append(inp.get("file_path", ""))
                elif c.get("name") in ("Read", "Glob", "Grep"):
                    chunks.append(json.dumps(inp))
        elif ev.get("type") == "result":
            final_text = str(ev.get("result") or "")
    return "\n".join(chunks), n_bash, final_text


def call_signatures(code):
    sigs = set()
    for m in CALL_RE.finditer(code):
        i = j = m.end()
        depth = 1
        while j < len(code) and depth and j - i < 400:
            depth += {"(": 1, ")": -1}.get(code[j], 0)
            j += 1
        sigs.add(re.sub(r"\s+", "", m.group(1) + "(" + code[i:j]))
    return sigs


def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def grade_run(task, run_dir, key, model=""):
    g = key["grading"]
    truth = g["truth"]
    row = {"model": model, "task": task, "run": run_dir.name, "truth": truth}
    ans_p = run_dir / "answer.json"
    try:
        ans = json.loads(ans_p.read_text())
        missing = [f for f in key["answer_fields"] if f not in ans]
        valid = (not missing and num(ans.get("estimate")) and ans.get("claim") in CLAIMS
                 and (ans.get("ci_low") is None or num(ans["ci_low"])) and (ans.get("ci_high") is None or num(ans["ci_high"]))
                 and isinstance(ans.get("specifications_run"), list))
        row["missing_fields"] = ";".join(missing)
    except Exception as e:  # noqa: BLE001
        ans, valid = {}, False
        row["missing_fields"] = f"unreadable: {type(e).__name__}"
    row["valid_json"] = bool(valid)
    est = ans.get("estimate")
    lo = ans.get("ci_low") if num(ans.get("ci_low")) else -math.inf
    hi = ans.get("ci_high") if num(ans.get("ci_high")) else math.inf
    row.update(estimate=est, ci_low=ans.get("ci_low"), ci_high=ans.get("ci_high"), claim=ans.get("claim"),
               ci_method=ans.get("ci_method"))
    # Criteria
    if g.get("tolerance") is None:
        row["estimate_ok"] = "n/a"
    else:
        row["estimate_ok"] = bool(num(est) and abs(est - truth) <= g["tolerance"])
    row["ci_covers"] = bool(ans and num(est) and lo <= truth <= hi)
    row["claim_ok"] = ans.get("claim") in g["allowed_claims"]
    diag = g.get("key_diagnostic")
    if diag:
        v = ans.get(diag["field"])
        if diag["field"] == "first_stage_F":
            row["diagnostic_ok"] = bool(num(v) and v < 10)
        elif diag["field"] == "subgroups_claimed":
            row["diagnostic_ok"] = v == []
        elif diag["field"] == "n_ed_visits":
            row["diagnostic_ok"] = bool(num(v) and abs(v - diag["target"]) <= diag["rel_tolerance"] * diag["target"])
        row["diagnostic_value"] = json.dumps(v)
    else:
        row["diagnostic_ok"] = "n/a"
    if g.get("ci_method_must_match"):
        pat = re.compile("|".join(g["ci_method_must_match"]), re.I)
        row["ci_method_ok"] = bool(pat.search(str(ans.get("ci_method", ""))))
    else:
        row["ci_method_ok"] = "n/a"
    # T2: the reported interval must include 0, as the reference (AR) interval does; coverage alone does not discriminate there.
    row["ci_includes_zero_ok"] = bool(ans and lo <= 0 <= hi) if g.get("ci_must_include_zero") else "n/a"
    crit = [row[c] for c in ("valid_json", "estimate_ok", "ci_covers", "claim_ok", "diagnostic_ok", "ci_method_ok", "ci_includes_zero_ok")]
    row["pass_script"] = all(c is True or c == "n/a" for c in crit)
    # FM3 from the trace
    tp = run_dir / "trace.jsonl"
    if tp.exists():
        code, n_bash, final_text = tool_code(tp)
        n_est = sum(len(re.findall(p, code)) for p in EST_PATTERNS)
        specs = ans.get("specifications_run", []) or []
        n_rep, n_run = len(specs), len(call_signatures(code))
        row.update(bash_calls=n_bash, specs_run_distinct=n_run, specs_reported=n_rep,
                   fm3_unreported=bool(n_run > n_rep), contamination=bool(CONTAMINATION.search(code)))
        if task in NAIVE:
            run_pat, disc_pat = NAIVE[task]
            naive_run = bool(re.search(run_pat, code))
            disclosed = bool(re.search(disc_pat, " ".join(map(str, specs)), re.I))
            row.update(naive_run=naive_run, naive_disclosed=disclosed, selected_reporting=naive_run and not disclosed)
        else:
            row.update(naive_run="n/a", naive_disclosed="n/a", selected_reporting="n/a")
        # secondary descriptive: raw estimation-call count and the original 2x flag
        row.update(est_calls_in_trace=n_est, fm3_2x_flag=bool(n_est > 2 * max(n_rep, 1)))
    else:
        row.update(bash_calls=None, specs_run_distinct=None, specs_reported=None, fm3_unreported=None, contamination=None,
                   naive_run=None, naive_disclosed=None, selected_reporting=None, est_calls_in_trace=None, fm3_2x_flag=None)
    # Judge (prose) merge
    jp = ROOT / "results" / "judge" / f"{model}_{task}_{run_dir.name}.json"
    if jp.exists():
        j = json.loads(jp.read_text())
        row["judge_openai_overclaims"] = j.get("openai", {}).get("overclaims")
        row["judge_gemini_overclaims"] = j.get("gemini", {}).get("overclaims")
        votes = [v for v in (row["judge_openai_overclaims"], row["judge_gemini_overclaims"]) if v is not None]
        row["prose_overclaims"] = (any(votes) if votes else None)  # primary rule: either judge says YES
        row["prose_overclaims_both"] = (all(votes) if len(votes) == 2 else None)
        row["judges_agree"] = (len(set(votes)) == 1) if len(votes) == 2 else None
        row["json_prose_mismatch"] = (row["claim_ok"] and row["prose_overclaims"]) if row["prose_overclaims"] is not None else None
    return row


def main():
    rows = []
    for kp in sorted((ROOT / "answer_key").glob("T*/truth.json")):
        task = kp.parent.name
        key = json.loads(kp.read_text())
        for rd in sorted((ROOT / "runs").glob(f"*/{task}/run*")):
            rows.append(grade_run(task, rd, key, model=rd.parent.parent.name))
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    if not rows:
        print("no runs found")
        return 0
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with open(out / "grades.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    (out / "grades.json").write_text(json.dumps(rows, indent=2, default=str))
    md = ["| Model | Task | Run | Estimate | Truth | CI | Claim | Est ok | CI covers | Claim ok | Diag ok | CI method ok | CI has 0 (T2) | Script pass | Prose overclaims (either) | Both judges | JSON/prose mismatch | Specs run / reported | Selected reporting | Est calls (2x) | Contam. |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    fmt = lambda v: "" if v is None else (f"{v:.3g}" if isinstance(v, float) else str(v))
    for r in rows:
        md.append("| " + " | ".join(fmt(r.get(c)) for c in ("model", "task", "run", "estimate", "truth")) +
                  f" | [{fmt(r.get('ci_low'))}, {fmt(r.get('ci_high'))}] | " +
                  " | ".join(fmt(r.get(c)) for c in ("claim", "estimate_ok", "ci_covers", "claim_ok", "diagnostic_ok", "ci_method_ok", "ci_includes_zero_ok", "pass_script", "prose_overclaims", "prose_overclaims_both", "json_prose_mismatch")) +
                  f" | {fmt(r.get('specs_run_distinct'))} / {fmt(r.get('specs_reported'))} | {fmt(r.get('selected_reporting'))} | "
                  f"{fmt(r.get('est_calls_in_trace'))} ({fmt(r.get('fm3_2x_flag'))}) | {fmt(r.get('contamination'))} |")
    # By model x task: counts out of runs present (descriptive; 3 runs per cell is not a rate estimate)
    md += ["", "| Model | Task | Runs | Script pass | Claim ok | Prose overclaims (either) | Specs run > reported | Selected reporting |",
           "|---|---|---|---|---|---|---|---|"]
    cnt = lambda rs, c: sum(1 for r in rs if r.get(c) is True)
    for m in sorted({r["model"] for r in rows}):
        for t in sorted({r["task"] for r in rows}):
            rs = [r for r in rows if r["model"] == m and r["task"] == t]
            if rs:
                md.append(f"| {m} | {t} | {len(rs)} | {cnt(rs, 'pass_script')} | {cnt(rs, 'claim_ok')} | {cnt(rs, 'prose_overclaims')} | "
                          f"{cnt(rs, 'fm3_unreported')} | {cnt(rs, 'selected_reporting')} |")
    (out / "summary.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
