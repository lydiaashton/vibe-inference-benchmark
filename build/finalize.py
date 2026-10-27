"""Assemble answer_key/<T>/truth.json (DGP layer + reference layer + grading rules)
and build/trap_report.md. Tolerances and allowed claims are PROPOSALS until Lydia
approves them at B3/B4; after the lock they are frozen.
Run after generate.py and reference.R: .venv/bin/python build/finalize.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
KEY = ROOT / "answer_key"


def load(t, f):
    p = KEY / t / f
    return json.loads(p.read_text()) if p.exists() else {}


def t3_reference():
    """Rebuilt from claim_lines.csv.gz as the agent would see it: ED encounter = member-day with an ED
    facility (045x) or ED E/M (9928x) line; PCP visit = office E/M by a primary care specialty or a
    facility clinic claim (rev 0517); followed = PCP visit 0-14 days after; program x post DiD, SEs
    clustered by practice. Also the naive variants and a practice + month FE robustness check."""
    import sys
    sys.path.insert(0, str(ROOT / "build"))
    import statsmodels.formula.api as smf
    from generate import t3_analyses, t3_follow, t3_pcp_md
    t = ROOT / "tasks/T3_claims_followup"
    L = pd.read_csv(t / "claim_lines.csv.gz", parse_dates=["service_date"], keep_default_na=False,
                    dtype={"pos": str, "cpt_hcpcs": str, "revenue_code": str, "rendering_specialty": str})
    prac = pd.read_csv(t / "practices.csv")
    res, ed = t3_analyses(L, prac)
    ep = t3_follow(ed, t3_pcp_md(L))
    ep["month"] = ep.service_date.dt.month
    fe = smf.ols("followed ~ program:post + C(practice_id) + C(month)", ep).fit(cov_type="cluster", cov_kwds={"groups": ep.practice_id})
    rates = ep.groupby(["program", "post"]).followed.mean()
    c = res["correct"]
    return {"method": "ED encounters collapsed to member-days; PCP = office E/M (FM/IM) or rev 0517 clinic claim; 14-day window; 2x2 DiD (linear probability), SEs clustered by practice (60 clusters)",
            "estimate": c["estimate_pp"], "ci": c["ci_pp"], "p": c["p"], "n_ed_encounters": c["n_rows"],
            "cell_rates": {f"program{k[0]}_post{k[1]}": float(v) for k, v in rates.items()},
            "robustness_practice_and_month_fe": {"estimate": 100 * float(fe.params["program:post"]),
                                                 "ci": [100 * float(x) for x in fe.conf_int().loc["program:post"]]},
            "naive": {k: v for k, v in res.items() if k != "correct"},
            "r_fixest_crosscheck": load("T3", "reference.json")}


RULES = {
    "T1": dict(truth_field="true_value", tolerance=1.0, allowed_claims=["effect"],
               required_sign=+1, key_diagnostic=None,
               pass_rule="estimate within +/-1.0 of true ATT AND CI covers truth AND claim allowed AND valid JSON"),
    "T2": dict(truth_field="true_value", tolerance=None, allowed_claims=["inconclusive"],
               key_diagnostic={"field": "first_stage_F", "rule": "reported and < 10"},
               ci_method_must_match=["anderson", "rubin", "\\bAR\\b", "conditional likelihood", "CLR", "tF", "weak-iv-robust", "weak iv robust", "weak-instrument-robust"],
               ci_must_include_zero=True,
               pass_rule="first_stage_F reported (< 10) AND ci_method is weak-IV-robust AND CI includes 0 (as the reference AR CI does) AND CI covers truth AND claim == inconclusive AND valid JSON; point estimate not graded (weak-IV point estimates are uninformative); coverage alone is uninformative here because the conventional 2SLS CI also covers the truth"),
    "T3": dict(truth_field="true_value_sample", tolerance=3.0, allowed_claims=["effect"], required_sign=+1,
               key_diagnostic=None,
               pass_rule="estimate within +/-3.0 pp of sample truth AND CI covers truth AND claim allowed AND valid JSON"),
    "T4": dict(truth_field="true_value", tolerance=0.08, allowed_claims=["no_effect", "inconclusive"],
               claim_refers_to="heterogeneity (whether any subgroup's effect differs)",
               key_diagnostic={"field": "subgroups_claimed", "rule": "must be an empty list"},
               pass_rule="ATE within +/-0.08 of 0.10 AND CI covers 0.10 AND subgroups_claimed == [] AND claim allowed AND valid JSON"),
}

COMMON_FIELDS = ["estimate", "ci_low", "ci_high", "ci_method", "claim", "specifications_run",
                 "assumptions_checked", "headline_claim"]
TASK_FIELDS = {"T2": ["first_stage_F"], "T4": ["subgroups_claimed"]}


def judge_text(t, dgp, ref):
    """The most the reference analysis supports, in words, shown to the prose judge."""
    if t == "T1":
        return (f"The program increased new business registrations. Reference (Callaway-Sant'Anna): ATT about {ref['estimate']:.1f} "
                f"per 10k (95% CI {ref['ci'][0]:.1f} to {ref['ci'][1]:.1f}). Claims of a negative, zero or much larger effect are not supported.")
    if t == "T2":
        return (f"Inconclusive. The instrument is weak (first-stage F about {ref['first_stage_F_robust']:.1f}); the weak-instrument-robust "
                f"(Anderson-Rubin) 95% CI is {ref['ar_ci'][0]:.2f} to {ref['ar_ci'][1]:.2f} and includes zero. Any claim of a statistically "
                f"significant, positive or precisely estimated return to schooling, or that the instrument is strong, goes beyond this.")
    if t == "T3":
        return (f"The program raised the 14-day ED-to-PCP follow-up rate. Reference (ED encounters collapsed from claim lines to member-days, "
                f"PCP visits including facility-billed clinic claims, DiD clustered by practice): about {ref['estimate']:.1f} percentage points "
                f"(95% CI {ref['ci'][0]:.1f} to {ref['ci'][1]:.1f}). Claiming no effect, a negative effect, or an effect of about 2-3 points "
                f"(what an office-E/M-only definition of PCP visits gives) is not supported.")
    return (f"The overall effect is positive, about {ref['estimate']:.2f} SD (95% CI {ref['ci'][0]:.2f} to {ref['ci'][1]:.2f}). "
            f"There is no evidence that the effect differs across any subgroup (omnibus test of all interactions p = {dgp['omnibus_wald_p']:.2f}; "
            f"no subgroup difference survives multiplicity correction). Naming any subgroup as more or less affected goes beyond this.")


def main():
    lines = ["# Trap verification report", "", "Generated by build/finalize.py. Numbers are from the exact datasets in tasks/.", "",
             "| Task | Truth | Naive method -> result | Correct method -> result | Trap fires? | Correct recovers? |",
             "|---|---|---|---|---|---|"]
    for t in ["T1", "T2", "T3", "T4"]:
        dgp, ref = load(t, "dgp.json"), load(t, "reference.json")
        if t == "T3":
            ref = t3_reference()
        r = RULES[t]
        truth = dgp[r["truth_field"]]
        key = {"task": t, "dgp": dgp, "reference": ref, "grading": {**r, "truth": truth, "judge_allowed_claim": judge_text(t, dgp, ref)},
               "answer_fields": COMMON_FIELDS + TASK_FIELDS.get(t, []), "status": "DRAFT, not locked"}
        (KEY / t / "truth.json").write_text(json.dumps(key, indent=2, default=float))
        if t == "T1":
            naive, nres = "TWFE", f"{dgp['naive_twfe']:.2f}"
            corr, cres = "CS (never-treated)", f"{ref['estimate']:.2f} [{ref['ci'][0]:.2f}, {ref['ci'][1]:.2f}]"
            fires = np.sign(dgp["naive_twfe"]) != np.sign(truth)
            rec = ref["ci"][0] <= truth <= ref["ci"][1]
        elif t == "T2":
            n2 = dgp["naive_2sls"]
            naive, nres = "2SLS + conventional CI", f"{n2['estimate']:.3f} [{n2['ci'][0]:.3f}, {n2['ci'][1]:.3f}], F={n2['first_stage_F_robust']:.1f}"
            corr, cres = "Anderson-Rubin CI", f"[{ref['ar_ci'][0]:.3f}, {ref['ar_ci'][1]:.3f}] ({ref['ar_shape']})"
            fires = n2["ci"][0] > 0 and ref["ar_includes_zero"]  # FM2: conventional CI licenses "effect"; robust CI does not
            rec = ref["ar_includes_truth"] and ref["ar_includes_zero"]
        elif t == "T3":
            f = lambda n: f"{n['estimate_pp']:.2f} pp [{n['ci_pp'][0]:.2f}, {n['ci_pp'][1]:.2f}]"
            nv = ref["naive"]
            naive = "CPT-only PCP / line-level ED / both"
            nres = f"{f(nv['cpt_only'])}; {f(nv['line_level'])}; {f(nv['line_level_cpt_only'])}"
            rx = ref["r_fixest_crosscheck"]
            corr = "member-day encounters, PCP incl. rev 0517"
            cres = (f"{ref['estimate']:.2f} pp [{ref['ci'][0]:.2f}, {ref['ci'][1]:.2f}]; practice+month FE {ref['robustness_practice_and_month_fe']['estimate']:.2f}; "
                    f"R/fixest rebuild {rx['estimate']:.2f} [{rx['ci'][0]:.2f}, {rx['ci'][1]:.2f}]")
            fires = all(not (nv[k]["ci_pp"][0] <= truth <= nv[k]["ci_pp"][1]) for k in ("cpt_only", "line_level_cpt_only"))
            rec = ref["ci"][0] <= truth <= ref["ci"][1] and ref["ci"][0] > 0
        else:
            hits = ", ".join(f"{h['moderator']} (p={h['interaction_p']:.3f})" for h in dgp["naive_scan_hits"])
            naive, nres = "uncorrected subgroup scan (20 splits)", hits
            corr, cres = "omnibus Wald / Holm", f"Wald p={dgp['omnibus_wald_p']:.2f} (df {dgp['omnibus_df']}); min Holm p={dgp['min_holm_p']:.2f}; ATE {ref['estimate']:.3f} [{ref['ci'][0]:.3f}, {ref['ci'][1]:.3f}]"
            fires = len(dgp["naive_scan_hits"]) >= 2
            rec = dgp["omnibus_wald_p"] > 0.05 and ref["ci"][0] <= truth <= ref["ci"][1]
        lines.append(f"| {t} | {truth:g} | {naive} -> {nres} | {corr} -> {cres} | {'yes' if fires else 'NO'} | {'yes' if rec else 'NO'} |")
    (ROOT / "build" / "trap_report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
