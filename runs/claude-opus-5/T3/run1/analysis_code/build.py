import pandas as pd, numpy as np, sys

DIR = '/Users/lydiaashton/vib-bench-runs/runs/claude-opus-5/T3/run1'
d = pd.read_csv('/tmp/work/claim_lines.csv', dtype=str)
d['service_date'] = pd.to_datetime(d.service_date)
pr = pd.read_csv(DIR + '/practices.csv', dtype={'practice_id': str})

# ---------- ED visits: POS 23, deduped to member-day ----------
ed = d[d.pos == '23']
edv = (ed.groupby(['member_id', 'practice_id', 'service_date'], as_index=False)
         .agg(nfac=('claim_id', 'nunique')))
edv = edv[(edv.service_date >= '2025-01-01') & (edv.service_date <= '2025-12-31')]
print('ED visits (member-days) 2025:', len(edv))
print('ED member-days w/ >1 claim_id:', (edv.nfac > 1).sum())
# alt: count distinct facility claims as visits
nfac_claims = ed[(ed.claim_type == 'facility') & (ed.service_date <= '2025-12-31')].claim_id.nunique()
print('distinct ED facility claims 2025:', nfac_claims)

# ---------- PCP visit definitions ----------
office = d[(d.pos == '11') &
           d.rendering_specialty.isin(['Family Medicine', 'Internal Medicine']) &
           d.cpt_hcpcs.isin(['99211', '99212', '99213', '99214', '99215'])]
hosp = d[(d.pos == '22') & (d.cpt_hcpcs == 'G0463')]
hosp_fp = hosp[hosp.revenue_code == '0517']   # rev 0517 = family practice clinic
hosp_oth = hosp[hosp.revenue_code == '0519']  # rev 0519 = other clinic

defs = {
    'office_only': office,
    'office_plus_hosp_fp': pd.concat([office, hosp_fp]),
    'office_plus_all_hosp': pd.concat([office, hosp]),
}
for k, v in defs.items():
    print(k, 'lines', len(v), 'member-days', v.groupby(['member_id', 'service_date']).ngroups)

out = {}
for k, v in defs.items():
    pv = v[['member_id', 'service_date']].drop_duplicates().rename(columns={'service_date': 'pcp_date'})
    m = edv.merge(pv, on='member_id', how='left')
    gap = (m.pcp_date - m.service_date).dt.days
    m['hit'] = ((gap >= 0) & (gap <= 14)).fillna(False)
    f = m.groupby(['member_id', 'practice_id', 'service_date'], as_index=False).hit.max()
    assert len(f) == len(edv)
    out[k] = f

v = out['office_plus_hosp_fp']
for k in out:
    print(k, 'followup rate', out[k].hit.mean().round(4))

for k, f in out.items():
    f = f.merge(pr, on='practice_id')
    f['post'] = (f.service_date >= '2025-07-01').astype(int)
    f.to_csv(f"/tmp/work/ed_{k}.csv",index=False)
    t = f.groupby(['program', 'post']).hit.agg(['mean', 'size'])
    print('==', k); print(t)
    did = (t.loc[(1, 1), 'mean'] - t.loc[(1, 0), 'mean']) - (t.loc[(0, 1), 'mean'] - t.loc[(0, 0), 'mean'])
    print('DiD pp:', round(100 * did, 3))
