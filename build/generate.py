"""Generate task datasets and the DGP-truth layer of each answer key.

Writes tasks/<T>/data files (visible to the model) and answer_key/<T>/dgp.json
(never visible). Seeds are searched over a fixed range against pre-stated trap
conditions; the chosen seed and the condition are recorded in dgp.json.
Run: .venv/bin/python build/generate.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks"
KEY = ROOT / "answer_key"


def write_key(task, obj):
    d = KEY / task
    d.mkdir(parents=True, exist_ok=True)
    (d / "dgp.json").write_text(json.dumps(obj, indent=2))


# ---------------------------------------------------------------- T1 staggered DiD
def t1_sim(seed):
    r = np.random.default_rng(seed)
    years = list(range(2005, 2021))
    cohorts = {2006: 0.55, 2011: 0.20, 2016: 0.17}
    n = 300
    g = r.choice(list(cohorts) + [0], size=n, p=list(cohorts.values()) + [1 - sum(cohorts.values())])
    alpha = r.normal(0, 2, n)
    yfe = {y: 0.3 * (y - years[0]) + r.normal(0, 0.5) for y in years}
    rows = []
    for i in range(n):
        for y in years:
            d = int(g[i] > 0 and y >= g[i])
            tau = 1.0 * (y - g[i] + 1) if d else 0.0  # effect grows 1 unit per year of exposure
            rows.append((1000 + i, y, int(g[i]) if g[i] else np.nan, d, tau,
                         10 + alpha[i] + yfe[y] + tau + r.normal(0, 1)))
    return pd.DataFrame(rows, columns=["county_id", "year", "adoption_year", "program", "tau", "new_biz_per_10k"])


def t1():
    # Trap condition: TWFE coefficient sign-flipped relative to the true ATT.
    for seed in range(100, 200):
        df = t1_sim(seed)
        att = df.loc[df.program == 1, "tau"].mean()
        twfe = smf.ols("new_biz_per_10k ~ program + C(county_id) + C(year)", df).fit().params["program"]
        if np.sign(twfe) != np.sign(att):
            break
    out = TASKS / "T1_staggered_did"
    out.mkdir(parents=True, exist_ok=True)
    df.drop(columns="tau").round(3).to_csv(out / "data.csv", index=False)
    write_key("T1", {
        "seed": seed, "seed_rule": "first seed in 100..199 with sign(TWFE) != sign(true ATT)",
        "dgp": "y_it = 10 + a_i + d_t + tau_it + e_it; tau_it = (t - g_i + 1) for t >= g_i; cohorts 2006/2011/2016 (55/20/17%), 8% never treated; 300 counties x 2005-2020",
        "estimand": "ATT averaged over all treated county-years",
        "true_value": round(float(att), 4),
        "naive_twfe": round(float(twfe), 4),
    })


# ---------------------------------------------------------------- T2 weak IV
def t2_sim(seed, n=1500):
    r = np.random.default_rng(seed)
    ability = r.normal(0, 1, n)
    dist = r.gamma(2.0, 10.0, n)  # miles to nearest four-year college
    z = (dist - 20) / 14
    parent_ed = r.integers(10, 19, n)
    female = r.integers(0, 2, n)
    school = 12.5 + 0.12 * (parent_ed - 14) - 0.10 * z + 1.2 * ability + r.normal(0, 1.6, n)
    school = np.clip(np.round(school), 8, 20)
    beta = 0.05
    logwage = 1.6 + beta * school + 0.25 * ability + 0.01 * (parent_ed - 14) - 0.12 * female + r.normal(0, 0.35, n)
    return pd.DataFrame({"person_id": np.arange(1, n + 1), "log_wage": logwage.round(4), "years_school": school.astype(int),
                         "dist_college_miles": dist.round(1), "parent_educ": parent_ed, "female": female}), beta


def iv_fit(df):
    from linearmodels.iv import IV2SLS
    res = IV2SLS.from_formula("log_wage ~ 1 + parent_educ + female + [years_school ~ dist_college_miles]", df).fit(cov_type="robust")
    fs = smf.ols("years_school ~ dist_college_miles + parent_educ + female", df).fit(cov_type="HC1")
    F = float(fs.tvalues["dist_college_miles"] ** 2)
    lo, hi = res.conf_int().loc["years_school"]
    return float(res.params["years_school"]), float(lo), float(hi), F


def ar_ci(df, grid=np.linspace(-1.5, 1.5, 6001)):
    X = sm.add_constant(df[["dist_college_miles", "parent_educ", "female"]])
    acc = []
    for b in grid:
        m = sm.OLS(df.log_wage - b * df.years_school, X).fit(cov_type="HC1")
        if m.pvalues["dist_college_miles"] > 0.05:
            acc.append(b)
    if not acc:
        return None, None, "empty"
    lo, hi = min(acc), max(acc)
    shape = "bounded"
    if np.isclose(lo, grid[0]) or np.isclose(hi, grid[-1]):
        shape = "unbounded_on_grid"
    if len(acc) < (hi - lo) / (grid[1] - grid[0]) * 0.99:
        shape = "disjoint_or_" + shape
    return lo, hi, shape


def t2():
    # Trap condition: robust first-stage F in [3,5]; conventional 2SLS 95% CI excludes 0; AR CI includes 0.
    for seed in range(200, 400):
        df, beta = t2_sim(seed)
        b, lo, hi, F = iv_fit(df)
        if not (3 <= F <= 5 and (lo > 0 or hi < 0)):
            continue
        alo, ahi, shape = ar_ci(df)
        if alo is not None and alo <= 0 <= ahi or shape.startswith("disjoint"):
            break
    out = TASKS / "T2_weak_iv"
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "data.csv", index=False)
    ols = smf.ols("log_wage ~ years_school + parent_educ + female", df).fit().params["years_school"]
    write_key("T2", {
        "seed": seed, "seed_rule": "first seed in 200..399 with robust first-stage F in [3,5], conventional 2SLS CI excluding 0, AR CI including 0",
        "dgp": "school = 12.5 + 0.12(parent_ed-14) - 0.10 z + 1.2 ability + v; log_wage = 1.6 + 0.05 school + 0.25 ability + ...; z = standardized distance",
        "estimand": "causal return to one year of schooling (log points)",
        "true_value": beta, "naive_ols": round(float(ols), 4),
        "naive_2sls": {"estimate": round(b, 4), "ci": [round(lo, 4), round(hi, 4)], "first_stage_F_robust": round(F, 2)},
    })


# ---------------------------------------------------------------- T3 claims follow-up (Condition 2: data audit)
T3_START, T3_LAUNCH, T3_END_ED, T3_END = (pd.Timestamp(d) for d in ("2025-01-01", "2025-07-01", "2025-12-31", "2026-01-14"))
PCP_SPECIALTIES = ["Family Medicine", "Internal Medicine"]
SPEC_SPECIALTIES = ["Cardiology", "Dermatology", "Orthopedic Surgery", "Gastroenterology", "Endocrinology"]
ED_EM = ["99281", "99282", "99283", "99284", "99285"]
OFFICE_EM = ["99202", "99203", "99204", "99205", "99211", "99212", "99213", "99214", "99215"]
# ED facility ancillary lines: (revenue_code, cpt_hcpcs, base allowed, imaging with a separate radiology read)
ED_ANCILLARY = [("0300", "80053", 18, 0), ("0300", "85025", 12, 0), ("0320", "71046", 60, 1), ("0350", "74177", 420, 1),
                ("0250", "", 25, 0), ("0636", "J1885", 15, 0), ("0730", "93005", 30, 0)]
ED_ANC_P = [.22, .22, .14, .08, .14, .10, .10]


def t3_encounters(seed, n_members=120000, n_practices=60, effect_low=0.11, effect_high=0.03):
    """Encounter-level DGP. Program practices (30 of 60) get care navigation from T3_LAUNCH: for ED visits
    on/after launch, the probability of a PCP follow-up rises by effect_low (acuity 1-3) or effect_high
    (acuity 4-5); program-induced follow-ups arrive 3-14 days after the ED visit. Navigators book most
    induced follow-ups into hospital-based clinic slots, which bill as a bundled facility claim (75% vs
    20% for other PCP visits). Returns encounters (with internal `induced`, `acuity`, `facility_only`) and practices."""
    r = np.random.default_rng(seed)
    n_days = (T3_END - T3_START).days + 1
    ed_days = (T3_END_ED - T3_START).days + 1
    launch = (T3_LAUNCH - T3_START).days
    prac = pd.DataFrame({"practice_id": np.arange(101, 101 + n_practices)})
    prac["program"] = (r.permutation(n_practices) < n_practices // 2).astype(int)
    # program targeted at lower-follow-up practices (level difference; parallel trends hold)
    prac["p0"] = np.clip(0.27 - 0.05 * prac.program + r.normal(0, 0.03, n_practices), 0.08, 0.6)
    prac["specialty"] = r.choice(PCP_SPECIALTIES, n_practices)
    member = np.arange(500001, 500001 + n_members)
    mprac = r.choice(prac.practice_id.values, n_members)

    def poisson(rate, kind, horizon):
        k = r.poisson(rate * horizon / 365, n_members)
        return pd.DataFrame({"member_id": np.repeat(member, k), "practice_id": np.repeat(mprac, k),
                             "day": r.integers(0, horizon, k.sum()), "kind": kind, "induced": 0, "acuity": 0})

    routine = [poisson(2.5, "PCP", n_days), poisson(1.0, "SPEC", n_days), poisson(1.2, "LAB", n_days), poisson(0.4, "IMG", n_days)]
    ed = poisson(0.26, "ED", ed_days)  # ED visits dated within 2025, so every one has a full 14-day window in the data
    ed["acuity"] = r.choice([1, 2, 3, 4, 5], len(ed), p=[.05, .20, .35, .25, .15])
    ed = ed.merge(prac[["practice_id", "program", "p0"]], on="practice_id", how="left")
    post = (ed.day >= launch).to_numpy()
    eff = np.where(ed.acuity <= 3, effect_low, effect_high)
    p_ctrl = ed.p0.to_numpy() + 0.02 * post  # common secular change after July (same for both groups)
    u = r.random(len(ed))
    ctrl = u < p_ctrl
    ind = (ed.program.to_numpy() == 1) & post & (u >= p_ctrl) & (u < p_ctrl + eff)
    lag_ctrl = np.where(r.random(len(ed)) < 0.15, 0, r.integers(1, 15, len(ed)))  # 15% same-day follow-ups
    lag_ind = r.integers(3, 15, len(ed))
    fu = pd.concat([
        pd.DataFrame({"member_id": ed.member_id[ctrl], "practice_id": ed.practice_id[ctrl], "day": ed.day[ctrl] + lag_ctrl[ctrl],
                      "kind": "PCP", "induced": 0, "acuity": 0}),
        pd.DataFrame({"member_id": ed.member_id[ind], "practice_id": ed.practice_id[ind], "day": ed.day[ind] + lag_ind[ind],
                      "kind": "PCP", "induced": 1, "acuity": 0})])
    enc = pd.concat(routine + [ed[["member_id", "practice_id", "day", "kind", "induced", "acuity"]], fu], ignore_index=True)
    enc = enc[enc.day < n_days].reset_index(drop=True)
    fac_p = np.select([enc.kind.eq("PCP") & enc.induced.eq(1), enc.kind.eq("PCP"), enc.kind.eq("SPEC")], [0.75, 0.20, 0.10], 0.0)
    enc["facility_only"] = r.random(len(enc)) < fac_p
    prac["launch_date"] = np.where(prac.program == 1, T3_LAUNCH.strftime("%Y-%m-%d"), "")
    return enc, prac


def t3_lines(enc, prac, seed):
    """Expand encounters to claim lines. An ED encounter is a facility claim (0450 + ancillaries), an ED
    physician claim and, with imaging, a radiology claim, each with its own claim_id. Facility-only clinic
    visits carry revenue code 0517/0519 and G0463 and no office E/M CPT."""
    r = np.random.default_rng(seed + 10000)
    spec_of = dict(zip(prac.practice_id, prac.specialty))
    parts, nk = [], [0]

    def add(e, claim_type, pos, specialty, cpt, rev, base, key=None):
        """One line per row of e; new claim keys unless key (existing claim) is given."""
        if key is None:
            key = np.arange(nk[0], nk[0] + len(e))
            nk[0] += len(e)
        parts.append(pd.DataFrame({"key": key, "member_id": e.member_id.to_numpy(), "practice_id": e.practice_id.to_numpy(),
                                   "day": e.day.to_numpy(), "claim_type": claim_type, "pos": pos, "specialty": specialty,
                                   "cpt_hcpcs": cpt, "revenue_code": rev, "base": base, "induced": e.induced.to_numpy()}))
        return key

    def extra(e, key, p, claim_type, pos, specialty, cpt, rev, base):
        m = r.random(len(e)) < p
        add(e[m], claim_type, pos, specialty if np.ndim(specialty) == 0 else np.asarray(specialty)[m], cpt, rev, base, key[m])

    # ED: facility claim, physician claim, radiology read
    ed = enc[enc.kind == "ED"]
    a = ed.acuity.to_numpy() - 1
    em = np.array(ED_EM)[a]
    fkey = add(ed, "facility", "23", "", em, "0450", np.array([80, 150, 280, 450, 700])[a])
    n_anc = r.poisson(np.array([0.3, 0.8, 1.8, 3.5, 5.5])[a])
    rep = np.repeat(np.arange(len(ed)), n_anc)
    pick = r.choice(len(ED_ANCILLARY), len(rep), p=ED_ANC_P)
    anc = np.array(ED_ANCILLARY, dtype=object)[pick]
    add(ed.iloc[rep], "facility", "23", "", anc[:, 1].astype(str), anc[:, 0].astype(str), anc[:, 2].astype(float), fkey[rep])
    pkey = add(ed, "professional", "23", "Emergency Medicine", em, "", np.array([30, 60, 110, 170, 250])[a])
    ekg = np.isin(np.arange(len(ed)), rep[anc[:, 1] == "93005"])
    add(ed[ekg], "professional", "23", "Emergency Medicine", "93010", "", 9.0, pkey[ekg])
    img = anc[:, 3].astype(int) == 1
    add(ed.iloc[rep[img]], "professional", "23", "Radiology", anc[img, 1].astype(str), "", 40.0)
    # PCP visits
    pcp = enc[(enc.kind == "PCP") & ~enc.facility_only]
    k = add(pcp, "professional", "11", pcp.practice_id.map(spec_of).to_numpy(),
            r.choice(["99212", "99213", "99214", "99215"], len(pcp), p=[.2, .5, .25, .05]), "", 95.0)
    extra(pcp, k, 0.35, "professional", "11", pcp.practice_id.map(spec_of).to_numpy(), "36415", "", 3.0)
    pf = enc[(enc.kind == "PCP") & enc.facility_only]
    k = add(pf, "facility", "22", "", "G0463", "0517", 110.0)
    extra(pf, k, 0.30, "facility", "22", "", "36415", "0300", 4.0)
    # Specialist visits
    sp = enc[(enc.kind == "SPEC") & ~enc.facility_only]
    s = r.choice(SPEC_SPECIALTIES, len(sp))
    add(sp, "professional", "11", s, r.choice(["99213", "99214", "99204"], len(sp), p=[.45, .4, .15]), "", 140.0)
    sf = enc[(enc.kind == "SPEC") & enc.facility_only]
    add(sf, "facility", "22", "", "G0463", "0519", 120.0)
    # Labs and outpatient imaging
    lab = enc[enc.kind == "LAB"]
    nl = r.integers(1, 4, len(lab))
    lk = np.arange(nk[0], nk[0] + len(lab))
    nk[0] += len(lab)
    rep = np.repeat(np.arange(len(lab)), nl)
    add(lab.iloc[rep], "professional", "81", "Clinical Laboratory", r.choice(["80053", "85025", "83036", "80061"], len(rep)), "", 15.0, lk[rep])
    im = enc[enc.kind == "IMG"]
    add(im, "professional", "11", "Radiology", r.choice(["71046", "73030", "76700", "72148"], len(im)), "", 120.0)

    L = pd.concat(parts, ignore_index=True)
    L["allowed_amount"] = (L.base * np.exp(r.normal(0, 0.25, len(L)))).round(2)
    ids = r.permutation(nk[0]) + 70000001  # claim_ids carry no ordering by encounter
    L["claim_id"] = ids[L.key.to_numpy()]
    L["service_date"] = T3_START + pd.to_timedelta(L.day, unit="D")
    L = L.sort_values(["claim_id", "cpt_hcpcs", "revenue_code"], kind="stable").reset_index(drop=True)
    L["line_no"] = L.groupby("claim_id").cumcount() + 1
    return L


T3_COLS = ["claim_id", "line_no", "member_id", "practice_id", "service_date", "pos", "claim_type",
           "cpt_hcpcs", "revenue_code", "rendering_specialty", "allowed_amount"]


def t3_ed_md(L):
    """Correct ED unit: member-days with an ED facility (045x) or ED E/M (9928x) line, ED dates in 2025."""
    is_ed = L.revenue_code.astype(str).str.startswith("045") | L.cpt_hcpcs.isin(ED_EM)
    e = L.loc[is_ed & (L.service_date <= T3_END_ED), ["member_id", "practice_id", "service_date"]]
    return e.drop_duplicates(["member_id", "service_date"]).reset_index(drop=True)


def t3_pcp_md(L, cpt_only=False):
    """PCP visit member-days. Correct: office E/M by a primary care specialty, or a facility clinic claim
    with revenue code 0517 (family practice clinic). cpt_only=True drops the facility route."""
    spec = L.rendering_specialty if "rendering_specialty" in L else L.specialty
    m = (L.claim_type == "professional") & L.cpt_hcpcs.isin(OFFICE_EM) & spec.isin(PCP_SPECIALTIES)
    if not cpt_only:
        m |= L.revenue_code.astype(str).eq("0517")
    return L.loc[m, ["member_id", "service_date"]].drop_duplicates()


def t3_follow(ed, pcp, window=14):
    """ed rows (any unit) with followed = any PCP member-day 0..window days after the ED date."""
    ed = ed.reset_index(drop=True).assign(_row=lambda d: np.arange(len(d)))
    m = ed[["_row", "member_id", "service_date"]].merge(pcp.rename(columns={"service_date": "pcp_date"}), on="member_id")
    lag = (m.pcp_date - m.service_date).dt.days
    hit = set(m._row[(lag >= 0) & (lag <= window)])
    return ed.assign(followed=ed._row.isin(hit).astype(float)).drop(columns="_row")


def t3_did(df, y, cluster="practice_id"):
    m = smf.ols(f"{y} ~ program * post", df).fit(cov_type="cluster", cov_kwds={"groups": df[cluster]})
    b, (lo, hi) = m.params["program:post"], m.conf_int().loc["program:post"]
    return float(b), float(lo), float(hi), float(m.pvalues["program:post"])


def t3_prep(ed, prac):
    ed = ed.merge(prac[["practice_id", "program"]], on="practice_id")
    return ed.assign(post=(ed.service_date >= T3_LAUNCH).astype(int))


def t3_analyses(L, prac):
    """Correct and naive DiDs (pp). Naive line-level: every line on an ED claim (POS 23) is an ED visit."""
    ed = t3_prep(t3_ed_md(L), prac)
    pcp, pcp_cpt = t3_pcp_md(L), t3_pcp_md(L, cpt_only=True)
    edl = t3_prep(L.loc[(L.pos == "23") & (L.service_date <= T3_END_ED), ["member_id", "practice_id", "service_date"]], prac)
    out = {}
    for name, e, p in [("correct", ed, pcp), ("cpt_only", ed, pcp_cpt), ("line_level", edl, pcp), ("line_level_cpt_only", edl, pcp_cpt)]:
        b, lo, hi, pv = t3_did(t3_follow(e, p), "followed")
        out[name] = {"estimate_pp": 100 * b, "ci_pp": [100 * lo, 100 * hi], "p": pv, "n_rows": int(len(e))}
    return out, ed


def t3():
    # Trap condition: correct (encounter = member-day, PCP incl. facility clinic claims) DiD CI excludes 0 and covers
    # the sample truth; CPT-only DiD CI and line-level + CPT-only DiD CI both exclude the sample truth.
    for seed in range(400, 500):
        enc, prac = t3_encounters(seed)
        L = t3_lines(enc, prac, seed)
        res, ed = t3_analyses(L, prac)
        cf = t3_follow(ed, t3_pcp_md(L[L.induced == 0]))  # same ED member-days, program-induced visits removed
        f = t3_follow(ed, t3_pcp_md(L))
        tp = (f.program == 1) & (f.post == 1)
        truth = 100 * float((f.followed[tp] - cf.followed[tp]).mean())
        c, n1, n3 = res["correct"]["ci_pp"], res["cpt_only"]["ci_pp"], res["line_level_cpt_only"]["ci_pp"]
        if c[0] > 0 and c[0] <= truth <= c[1] and not (n1[0] <= truth <= n1[1]) and not (n3[0] <= truth <= n3[1]):
            break
    out = TASKS / "T3_claims_followup"
    out.mkdir(parents=True, exist_ok=True)
    for old in ("claims.csv", "daily_summary.csv"):
        (out / old).unlink(missing_ok=True)
    L.rename(columns={"specialty": "rendering_specialty"})[T3_COLS].to_csv(
        out / "claim_lines.csv.gz", index=False, date_format="%Y-%m-%d", compression={"method": "gzip", "mtime": 0})
    prac[["practice_id", "program", "launch_date"]].to_csv(out / "practices.csv", index=False)
    ed_enc = enc[enc.kind == "ED"]
    write_key("T3", {
        "seed": seed, "seed_rule": "first seed in 400..499 with correct DiD CI excluding 0 and covering the sample truth, and both the CPT-only DiD CI and the line-level + CPT-only DiD CI excluding the sample truth",
        "dgp": "120,000 members in 60 practices (30 program, launch 2025-07-01). Encounters: routine PCP 2.5/yr, specialist 1/yr, lab 1.2/yr, imaging 0.4/yr, ED ~0.26/yr (2025 only), ED acuity 1-5 (5/20/35/25/15%). PCP follow-up prob p0 by practice (program 5 pp lower at baseline), +2 pp common post trend, 15% same-day. Program adds +11 pp (acuity 1-3) / +3 pp (acuity 4-5) follow-up for post-launch ED visits, arriving 3-14 days later. Billing: ED = facility claim (0450 + Poisson ancillaries rising with acuity) + ED physician claim + radiology read if imaging, separate claim_ids. PCP visits are bundled facility-only clinic claims (POS 22, rev 0517, G0463, no office E/M) with prob 0.75 if program-induced, 0.20 otherwise; specialist 0.10 (rev 0519).",
        "estimand": "DiD effect of the program on the 14-day ED-to-PCP follow-up rate (ED visits in 2025, one per member-day; any PCP visit by the same member 0-14 days after), in percentage points",
        "ed_encounters_2025": int(len(ed_enc)),
        "true_value_sample": round(truth, 4),
        "true_value_note": "sample truth = mean over program-practice post-launch ED member-days of (observed follow-up - follow-up with program-induced PCP visits removed)",
        "analyses_python": {k: {kk: (round(vv, 4) if isinstance(vv, float) else [round(x, 4) for x in vv] if isinstance(vv, list) else vv)
                                for kk, vv in v.items()} for k, v in res.items()},
        "naive_definitions": {"cpt_only": "ED = member-day; PCP = professional office E/M (99202-99215) by Family/Internal Medicine only (misses rev 0517 facility clinic claims)",
                              "line_level": "every line on a POS 23 claim treated as an ED visit (facility ancillaries, physician and radiology claims each count)",
                              "line_level_cpt_only": "both errors"},
    })


# ---------------------------------------------------------------- T4 null HTE
def t4_sim(seed, n=2400):
    r = np.random.default_rng(seed)
    d = pd.DataFrame({
        "participant_id": np.arange(1, n + 1),
        "treat": r.permutation(np.repeat([0, 1], n // 2)),
        "age": np.clip(r.normal(38, 11, n), 18, 75).round(0).astype(int),
        "income_k": np.clip(r.lognormal(4.0, 0.5, n), 8, 400).round(1),
        "baseline_score": r.normal(0, 1, n).round(3),
        "tenure_months": r.gamma(2, 12, n).round(0).astype(int),
        "sessions_prior_30d": r.poisson(4, n),
        "female": r.integers(0, 2, n),
        "urban": (r.random(n) < 0.62).astype(int),
        "first_gen": (r.random(n) < 0.35).astype(int),
        "mobile_primary": (r.random(n) < 0.55).astype(int),
        "region": r.choice(["Northeast", "Midwest", "South", "West"], n, p=[.18, .22, .37, .23]),
        "education": r.choice(["HS or less", "Some college", "BA", "Graduate"], n, p=[.25, .30, .30, .15]),
        "employment": r.choice(["Full-time", "Part-time", "Not working"], n, p=[.55, .2, .25]),
    })
    ate = 0.10
    y = (ate * d.treat + 0.45 * d.baseline_score + 0.004 * (d.age - 38) + 0.08 * np.log(d.income_k / 55)
         + 0.05 * d.urban - 0.04 * d.first_gen + r.normal(0, 0.85, n))
    d["outcome"] = y.round(4)  # control-group SD is ~1 by construction, so ATE 0.10 ~ 0.10 SD
    return d, ate


SUBGROUP_SPLITS = {
    "age": lambda d: d.age >= d.age.median(), "income_k": lambda d: d.income_k >= d.income_k.median(),
    "baseline_score": lambda d: d.baseline_score >= d.baseline_score.median(),
    "tenure_months": lambda d: d.tenure_months >= d.tenure_months.median(),
    "sessions_prior_30d": lambda d: d.sessions_prior_30d >= d.sessions_prior_30d.median(),
    "female": lambda d: d.female == 1, "urban": lambda d: d.urban == 1, "first_gen": lambda d: d.first_gen == 1,
    "mobile_primary": lambda d: d.mobile_primary == 1,
}
CATS = ["region", "education", "employment"]


def naive_subgroup_scan(d):
    """Per-subgroup treatment effect t-tests and interaction tests (no multiplicity correction)."""
    res = []
    for k, f in SUBGROUP_SPLITS.items():
        s = f(d).astype(int)
        m = smf.ols("outcome ~ treat * s", d.assign(s=s)).fit(cov_type="HC1")
        res.append({"moderator": k, "split": "median/binary", "interaction_p": float(m.pvalues["treat:s"])})
    for c in CATS:
        for lvl in sorted(d[c].unique()):
            s = (d[c] == lvl).astype(int)
            m = smf.ols("outcome ~ treat * s", d.assign(s=s)).fit(cov_type="HC1")
            res.append({"moderator": f"{c}={lvl}", "split": "level vs rest", "interaction_p": float(m.pvalues["treat:s"])})
    return pd.DataFrame(res)


def omnibus_p(d):
    mods = "age + income_k + baseline_score + tenure_months + sessions_prior_30d + female + urban + first_gen + mobile_primary + C(region) + C(education) + C(employment)"
    full = smf.ols(f"outcome ~ treat * ({mods})", d).fit(cov_type="HC1")
    names = [n for n in full.params.index if n.startswith("treat:")]
    R = np.zeros((len(names), len(full.params)))
    for i, n in enumerate(names):
        R[i, list(full.params.index).index(n)] = 1
    w = full.wald_test(R, scalar=True)
    return float(w.pvalue), len(names)


def t4():
    # Trap condition: uncorrected scan finds >= 2 moderators with p < .05; omnibus interaction Wald p > .20; min Holm-adjusted p > .05.
    from statsmodels.stats.multitest import multipletests
    for seed in range(500, 700):
        d, ate = t4_sim(seed)
        scan = naive_subgroup_scan(d)
        if (scan.interaction_p < 0.05).sum() < 2:
            continue
        p_omni, k = omnibus_p(d)
        holm = multipletests(scan.interaction_p, method="holm")[1].min()
        if p_omni > 0.20 and holm > 0.05:
            break
    out = TASKS / "T4_null_hte"
    out.mkdir(parents=True, exist_ok=True)
    d.to_csv(out / "data.csv", index=False)
    write_key("T4", {
        "seed": seed, "seed_rule": "first seed in 500..699 with >= 2 uncorrected interaction p < .05, omnibus Wald p > .20, min Holm p > .05",
        "dgp": "RCT n=2400, 50/50; outcome = 0.10*treat + prognostic covariates + noise, control SD ~1; NO treatment-covariate interactions",
        "estimand": "overall ATE (SD units); heterogeneity truth: no subgroup differs",
        "true_value": ate,
        "naive_scan_hits": scan[scan.interaction_p < 0.05].to_dict("records"),
        "omnibus_wald_p": p_omni, "omnibus_df": k, "min_holm_p": float(holm),
    })


if __name__ == "__main__":
    for f in (t1, t2, t3, t4):
        f()
        print("done", f.__name__)
