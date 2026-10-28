import pandas as pd, numpy as np, statsmodels.formula.api as smf, statsmodels.api as sm
import json

DIR = '/Users/lydiaashton/vib-bench-runs/runs/claude-opus-5/T3/run1'
d = pd.read_csv('/tmp/work/claim_lines.csv', dtype=str)
d['service_date'] = pd.to_datetime(d.service_date)
pr = pd.read_csv(DIR + '/practices.csv', dtype={'practice_id': str})
print('launch dates:', pr[pr.program == 1].launch_date.value_counts().to_dict(),
      '| control launch non-null:', pr[pr.program == 0].launch_date.notna().sum())
print('practices per arm:', pr.program.value_counts().to_dict())

# ---------------- ED visits ----------------
edl = d[d.pos == '23']
ed = edl[['member_id', 'practice_id', 'service_date']].drop_duplicates()
ed = ed[(ed.service_date >= '2025-01-01') & (ed.service_date <= '2025-12-31')].merge(pr, on='practice_id')
ed['post'] = (ed.service_date >= '2025-07-01').astype(int)
ed['month'] = ed.service_date.dt.to_period('M').astype(str)
# acuity of index ED visit (max E/M level) for composition check
ac = (edl[edl.cpt_hcpcs.isin(['99281', '99282', '99283', '99284', '99285'])]
      .groupby(['member_id', 'service_date']).cpt_hcpcs.max().rename('acuity').reset_index())
ed = ed.merge(ac, on=['member_id', 'service_date'], how='left')
print('N ED visits 2025:', len(ed))

# ---------------- PCP visit candidate sets ----------------
EM = ['99211', '99212', '99213', '99214', '99215']
office = d[(d.pos == '11') & d.rendering_specialty.isin(['Family Medicine', 'Internal Medicine'])
           & d.cpt_hcpcs.isin(EM)]
office_fm = d[(d.pos == '11') & (d.rendering_specialty == 'Family Medicine') & d.cpt_hcpcs.isin(EM)]
any_pcp_contact = d[(d.pos == '11') & d.rendering_specialty.isin(['Family Medicine', 'Internal Medicine'])]
h517 = d[(d.pos == '22') & (d.cpt_hcpcs == 'G0463') & (d.revenue_code == '0517')]
hall = d[(d.pos == '22') & (d.cpt_hcpcs == 'G0463')]
spec_office = d[(d.pos == '11') & d.cpt_hcpcs.isin(EM + ['99204'])]  # any office E/M incl specialists

PCPDEFS = {
    'main: office E/M (POS11, FM/IM) + hosp-based family-practice clinic (POS22 G0463 rev0517)':
        pd.concat([office, h517]),
    'office E/M only (POS11, FM/IM)': office,
    'office E/M + all POS22 G0463 (rev 0517 and 0519)': pd.concat([office, hall]),
    'hosp-based family-practice clinic only (POS22 G0463 rev0517)': h517,
    'Family Medicine only + hosp clinic rev0517': pd.concat([office_fm, h517]),
    'any POS11 FM/IM contact (incl. lab-only days) + hosp clinic rev0517':
        pd.concat([any_pcp_contact, h517]),
    'any office E/M incl. specialists + hosp clinic rev0517': pd.concat([spec_office, h517]),
}


def make_panel(pcp_lines, window=14, edset=None):
    e = ed if edset is None else edset
    pv = pcp_lines[['member_id', 'service_date']].drop_duplicates().rename(columns={'service_date': 'pdate'})
    m = e.merge(pv, on='member_id', how='left')
    gap = (m.pdate - m.service_date).dt.days
    m['hit'] = ((gap >= 0) & (gap <= window)).fillna(False)
    f = m.groupby(['member_id', 'practice_id', 'service_date'], as_index=False).hit.max()
    f = f.merge(e.drop(columns='hit', errors='ignore'), on=['member_id', 'practice_id', 'service_date'])
    f['hit'] = f.hit.astype(int)
    return f


def did_ols(f, formula='hit ~ program*post', cluster=True, scale=100):
    mod = smf.ols(formula, data=f)
    if cluster:
        r = mod.fit(cov_type='cluster', cov_kwds={'groups': f.practice_id})
    else:
        r = mod.fit()
    key = [k for k in r.params.index if ':' in k and 'program' in k and 'post' in k][0]
    b = scale * r.params[key]
    lo, hi = [scale * x for x in r.conf_int().loc[key].values]
    return b, lo, hi, r.pvalues[key], r


results = []
panels = {}
for name, lines in PCPDEFS.items():
    f = make_panel(lines)
    panels[name] = f
    b, lo, hi, p, _ = did_ols(f)
    results.append((name, b, lo, hi, p, f.hit.mean() * 100))
    print(f'{b:7.3f} [{lo:7.3f},{hi:7.3f}] p={p:.4f}  rate={f.hit.mean()*100:5.2f}  {name}')

MAIN = list(PCPDEFS)[0]
f = panels[MAIN]
f.to_csv('/tmp/work/panel_main.csv', index=False)
print()
print('2x2 cell means (main def):')
print(f.groupby(['program', 'post']).hit.agg(['mean', 'size']))
