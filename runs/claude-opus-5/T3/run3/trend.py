import sys
import numpy as np, pandas as pd, statsmodels.formula.api as smf
from scipy import stats
pd.set_option('display.width', 250)

d = pd.read_csv(sys.argv[1], dtype=str); d['service_date'] = pd.to_datetime(d['service_date'])
pr = pd.read_csv(sys.argv[2], dtype={'practice_id': str})
ed = d[(d.claim_type == 'facility') & (d.pos == '23') & (d.revenue_code == '0450') &
       (d.service_date.dt.year == 2025)][['claim_id', 'member_id', 'practice_id', 'service_date']] \
       .rename(columns={'service_date': 'ed_date'}).merge(pr[['practice_id', 'program']], on='practice_id')
off = d[(d.claim_type == 'professional') & (d.pos == '11') &
        d.cpt_hcpcs.isin(['99204', '99212', '99213', '99214', '99215']) &
        d.rendering_specialty.isin(['Family Medicine', 'Internal Medicine'])][['member_id', 'service_date']].assign(src='office')
cl = d[(d.cpt_hcpcs == 'G0463') & (d.revenue_code == '0517')][['member_id', 'service_date']].assign(src='clinic')
v = pd.concat([off, cl]).rename(columns={'service_date': 'pcp_date'})
m = ed.merge(v, on='member_id', how='left'); m['gap'] = (m.pcp_date - m.ed_date).dt.days
w = m[(m.gap >= 0) & (m.gap <= 14)]
ed['fu_off'] = ed.claim_id.isin(w[w.src == 'office'].claim_id).astype(int)
ed['fu_cl'] = ed.claim_id.isin(w[w.src == 'clinic'].claim_id).astype(int)
ed['fu_any'] = ((ed.fu_off + ed.fu_cl) > 0).astype(int)
ed['month'] = ed.ed_date.dt.to_period('M').astype(str)
ed['t'] = ed.ed_date.dt.month - 6
ed['post'] = (ed.ed_date >= pd.Timestamp('2025-07-01')).astype(int)

print('=== monthly rates & program-minus-control difference, by follow-up channel (pp) ===')
tab = ed.pivot_table(index='month', columns='program', values=['fu_any', 'fu_off', 'fu_cl'], aggfunc='mean') * 100
for y in ['fu_any', 'fu_off', 'fu_cl']:
    tab[(y, 'diff')] = tab[(y, 1)] - tab[(y, 0)]
print(tab[[(y, c) for y in ['fu_any', 'fu_off', 'fu_cl'] for c in [0, 1, 'diff']]].round(2).to_string())

G = ed.practice_id.nunique(); crit = stats.t.ppf(0.975, G - 1)
def run(f, key, lab, data=ed):
    r = smf.ols(f, data=data).fit(cov_type='cluster', cov_kwds={'groups': data.practice_id})
    b, se = r.params[key] * 100, r.bse[key] * 100
    print(f'{lab:<58s} b={b:7.3f} se={se:6.3f} [{b-crit*se:7.3f},{b+crit*se:7.3f}] p={2*stats.t.sf(abs(b/se),G-1):.4f}')
    return r

print()
print('=== jump vs trend, outcome = any 14-day PCP follow-up ===')
run('fu_any ~ program + post + program:post', 'program:post', 'A jump only (headline DiD)')
run('fu_any ~ program + t + program:t', 'program:t', 'B linear differential trend only (per month)')
rC = run('fu_any ~ program + t + program:t + post + program:post', 'program:post', 'C jump + differential trend: JUMP')
bt, st = rC.params['program:t'] * 100, rC.bse['program:t'] * 100
print(f'{"C jump + differential trend: TREND (per month)":<58s} b={bt:7.3f} se={st:6.3f} [{bt-crit*st:7.3f},{bt+crit*st:7.3f}]')
for f, lab in [('fu_any ~ program + post + program:post', 'A'),
               ('fu_any ~ program + t + program:t', 'B'),
               ('fu_any ~ program + t + program:t + post + program:post', 'C')]:
    r = smf.ols(f, data=ed).fit()
    print(f'   model {lab}: R2={r.rsquared:.5f} AIC={r.aic:.1f} BIC={r.bic:.1f}')

print()
print('=== de-trended DiD: subtract pre-period differential trend extrapolated into post ===')
pre = ed[ed.post == 0]
rp = smf.ols('fu_any ~ program + t + program:t', data=pre).fit(cov_type='cluster', cov_kwds={'groups': pre.practice_id})
slope, sls = rp.params['program:t'], rp.bse['program:t']
# DiD bias = slope * (mean t post - mean t pre)
dt = ed[ed.post == 1].t.mean() - ed[ed.post == 0].t.mean()
rA = smf.ols('fu_any ~ program + post + program:post', data=ed).fit(cov_type='cluster', cov_kwds={'groups': ed.practice_id})
bA, sA = rA.params['program:post'], rA.bse['program:post']
adj = (bA - slope * dt) * 100
# conservative se via delta method treating the two estimates as independent
sadj = np.sqrt(sA**2 + (dt * sls)**2) * 100
print(f'  pre-period differential slope = {slope*100:.3f} pp/month (se {sls*100:.3f}); post-pre gap in t = {dt:.2f} months')
print(f'  de-trended DiD = {adj:.3f} pp (se {sadj:.3f}) 95% CI [{adj-crit*sadj:.3f},{adj+crit*sadj:.3f}]')

print()
print('=== channel-specific DiD ===')
run('fu_off ~ program + post + program:post', 'program:post', 'office-PCP channel')
run('fu_cl  ~ program + post + program:post', 'program:post', 'hospital-based FP clinic channel')
print()
print('=== pre-trend by channel (pre-period only) ===')
for y in ['fu_any', 'fu_off', 'fu_cl']:
    r = smf.ols(f'{y} ~ program + t + program:t', data=pre).fit(cov_type='cluster', cov_kwds={'groups': pre.practice_id})
    b, se = r.params['program:t'] * 100, r.bse['program:t'] * 100
    print(f'  {y}: differential pre-trend {b:6.3f} pp/mo (se {se:.3f}) p={2*stats.t.sf(abs(b/se),G-1):.3f}')
print()
print('=== post-period: is the effect declining? (post only, program x months-since-launch) ===')
po = ed[ed.post == 1].copy(); po['s'] = po.t - 1
r = smf.ols('fu_any ~ program + s + program:s', data=po).fit(cov_type='cluster', cov_kwds={'groups': po.practice_id})
b, se = r.params['program:s'] * 100, r.bse['program:s'] * 100
print(f'  program x months-since-launch: {b:.3f} pp/mo (se {se:.3f}) p={2*stats.t.sf(abs(b/se),G-1):.3f}')

print()
print('=== underlying PCP-visit volume (all members, not just post-ED) per 1000 members ===')
mem = d.groupby(['practice_id', 'member_id']).size().reset_index().groupby('practice_id').size().rename('mem')
for nm, x in [('office PCP visits', off), ('hosp FP clinic visits', cl)]:
    xx = d.loc[x.index] if False else None
for nm, src in [('office', 'office'), ('clinic', 'clinic')]:
    base = off if src == 'office' else cl
    b2 = base.merge(d[['member_id', 'practice_id']].drop_duplicates(), on='member_id')
    b2 = b2.merge(pr[['practice_id', 'program']], on='practice_id')
    b2 = b2[b2.service_date.dt.year == 2025]
    t2 = b2.pivot_table(index=b2.service_date.dt.to_period('M').astype(str), columns='program', values='member_id', aggfunc='size')
    print(nm); print(t2.T.to_string())
