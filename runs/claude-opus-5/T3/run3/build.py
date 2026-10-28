import sys
import numpy as np
import pandas as pd

DATA = sys.argv[1]      # claims csv
PRAC = sys.argv[2]      # practices csv
OUT = sys.argv[3]       # ed-visit level parquet/csv

PC_SPEC = ['Family Medicine', 'Internal Medicine']
OFFICE_EM = ['99202', '99203', '99204', '99205', '99211', '99212', '99213', '99214', '99215']
ED_EM = ['99281', '99282', '99283', '99284', '99285']

d = pd.read_csv(DATA, dtype={'claim_id': str, 'member_id': str, 'practice_id': str,
                             'pos': str, 'revenue_code': str, 'cpt_hcpcs': str})
d['service_date'] = pd.to_datetime(d['service_date'])
pr = pd.read_csv(PRAC, dtype={'practice_id': str})

# ---------- ED visits: facility ED claim (one per claim_id), 2025 only ----------
ed = d[(d.claim_type == 'facility') & (d.pos == '23') & (d.revenue_code == '0450')]
ed = ed[ed.service_date.dt.year == 2025]
ed = (ed.groupby(['claim_id', 'member_id', 'practice_id', 'service_date'], as_index=False)
        .agg(acuity=('cpt_hcpcs', 'max')))
ed = ed.rename(columns={'service_date': 'ed_date'})

# ---------- PCP visit date sets (several definitions) ----------
prof_pcp = d[(d.claim_type == 'professional') & (d.pos == '11') &
             d.cpt_hcpcs.isin(OFFICE_EM) & d.rendering_specialty.isin(PC_SPEC)]
clinic_fp = d[(d.cpt_hcpcs == 'G0463') & (d.revenue_code == '0517')]      # hosp-based family practice clinic
clinic_oth = d[(d.cpt_hcpcs == 'G0463') & (d.revenue_code == '0519')]     # hosp-based "other" clinic
prof_spec = d[(d.claim_type == 'professional') & (d.pos == '11') &
              d.cpt_hcpcs.isin(OFFICE_EM) & ~d.rendering_specialty.isin(PC_SPEC)]

defs = {
    'main': pd.concat([prof_pcp, clinic_fp]),                      # office PCP + hosp-based FP clinic
    'profonly': prof_pcp,                                          # office PCP only
    'wide': pd.concat([prof_pcp, clinic_fp, clinic_oth]),           # + other hosp clinic
    'anyoffice': pd.concat([prof_pcp, prof_spec, clinic_fp, clinic_oth]),  # any ambulatory E&M
}

ed = ed.sort_values('ed_date').reset_index(drop=True)
for name, df in defs.items():
    v = df[['member_id', 'service_date']].drop_duplicates().sort_values('service_date')
    v = v.rename(columns={'service_date': 'pcp_date'})
    # for each ED visit, is there a pcp_date in [ed_date, ed_date+14] for same member
    m = ed[['claim_id', 'member_id', 'ed_date']].merge(v, on='member_id', how='left')
    gap = (m.pcp_date - m.ed_date).dt.days
    hit = m.assign(ok=((gap >= 0) & (gap <= 14)).fillna(False)).groupby('claim_id').ok.max()
    ed['fu_' + name] = ed.claim_id.map(hit).astype(int)
    # also days-to-first-followup under main def
    if name == 'main':
        g = m.assign(gap=gap)
        g = g[(g.gap >= 0) & (g.gap <= 14)].groupby('claim_id').gap.min()
        ed['days_to_fu'] = ed.claim_id.map(g)
        # 7-day and 30-day variants
        for w in (7, 30):
            gg = m.assign(gap=gap)
            hw = gg.assign(ok=((gg.gap >= 0) & (gg.gap <= w)).fillna(False)).groupby('claim_id').ok.max()
            ed[f'fu_main_{w}d'] = ed.claim_id.map(hw).astype(int)
        # excluding same-day (1-14 days)
        hx = m.assign(ok=((gap >= 1) & (gap <= 14)).fillna(False)).groupby('claim_id').ok.max()
        ed['fu_main_excl_sameday'] = ed.claim_id.map(hx).astype(int)

ed = ed.merge(pr[['practice_id', 'program']], on='practice_id', how='left')
ed['post'] = (ed.ed_date >= pd.Timestamp('2025-07-01')).astype(int)
ed['month'] = ed.ed_date.dt.to_period('M').astype(str)
ed.to_csv(OUT, index=False)
print('ED visits 2025:', len(ed))
print(ed.groupby(['program', 'post'])[['fu_main', 'fu_profonly', 'fu_wide', 'fu_anyoffice']].mean().round(4))
print(ed.groupby(['program', 'post']).size())
