import sys
import pandas as pd
d = pd.read_csv(sys.argv[1], dtype=str); d['service_date'] = pd.to_datetime(d['service_date'])
e = pd.read_csv(sys.argv[2], dtype={"member_id": str, "practice_id": str, "claim_id": str}); e['ed_date'] = pd.to_datetime(e['ed_date'])
EM = ['99204', '99212', '99213', '99214', '99215']
PC = ['Family Medicine', 'Internal Medicine']
spec = d[(d.pos == '11') & d.cpt_hcpcs.isin(EM) & ~d.rendering_specialty.isin(PC)][['member_id', 'service_date']]
lab = d[(d.pos == '81')][['member_id', 'service_date']]
pcp = pd.concat([d[(d.pos == '11') & d.cpt_hcpcs.isin(EM) & d.rendering_specialty.isin(PC)],
                 d[(d.cpt_hcpcs == 'G0463') & (d.revenue_code == '0517')]])[['member_id', 'service_date']]
for name, v, lo, hi in [('fu_spec14', spec, 0, 14), ('fu_lab14', lab, 0, 14), ('fu_pre14', pcp, -14, -1)]:
    vv = v.drop_duplicates().rename(columns={'service_date': 'dt'})
    m = e[['claim_id', 'member_id', 'ed_date']].merge(vv, on='member_id', how='left')
    gap = (m.dt - m.ed_date).dt.days
    hit = m.assign(ok=((gap >= lo) & (gap <= hi)).fillna(False)).groupby('claim_id').ok.max()
    e[name] = e.claim_id.map(hit).astype(int)
e.to_csv(sys.argv[2], index=False)
print(e.groupby(['program', 'post'])[['fu_spec14', 'fu_lab14', 'fu_pre14']].mean().round(4))
