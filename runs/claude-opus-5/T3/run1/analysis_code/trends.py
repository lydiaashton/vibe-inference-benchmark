import pandas as pd, numpy as np, statsmodels.formula.api as smf

d = pd.read_csv('/tmp/work/claim_lines.csv', dtype=str)
d['service_date'] = pd.to_datetime(d.service_date)
pr = pd.read_csv('/Users/lydiaashton/vib-bench-runs/runs/claude-opus-5/T3/run1/practices.csv',
                 dtype={'practice_id': str})
ed = d[d.pos == '23'][['member_id', 'practice_id', 'service_date']].drop_duplicates()
ed = ed[ed.service_date <= '2025-12-31'].merge(pr, on='practice_id')
ed['mnum'] = ed.service_date.dt.month
EM = ['99211', '99212', '99213', '99214', '99215']
office = d[(d.pos == '11') & d.rendering_specialty.isin(['Family Medicine', 'Internal Medicine'])
           & d.cpt_hcpcs.isin(EM)]
h517 = d[(d.pos == '22') & (d.cpt_hcpcs == 'G0463') & (d.revenue_code == '0517')]


def flag(lines, tag):
    pv = lines[['member_id', 'service_date']].drop_duplicates().rename(columns={'service_date': 'pdate'})
    m = ed.merge(pv, on='member_id', how='left')
    g = (m.pdate - m.service_date).dt.days
    m[tag] = ((g >= 0) & (g <= 14)).fillna(False)
    return m.groupby(['member_id', 'practice_id', 'service_date'])[tag].max()


f = ed.set_index(['member_id', 'practice_id', 'service_date'])
f['off'] = flag(office, 'off'); f['hos'] = flag(h517, 'hos')
f = f.reset_index()
f['hit'] = (f.off | f.hos).astype(int)
f[['off', 'hos']] = f[['off', 'hos']].astype(int)

print('Monthly program-minus-control gap (pp) by follow-up channel:')
tab = []
for ch in ['off', 'hos', 'hit']:
    t = f.pivot_table(index='mnum', columns='program', values=ch, aggfunc='mean')
    tab.append((100 * (t[1] - t[0])).rename(ch))
print(pd.concat(tab, axis=1).round(2).to_string())
print('\nMonthly rates, treated arm:')
print((100 * f[f.program == 1].pivot_table(index='mnum', values=['off', 'hos', 'hit'], aggfunc='mean')).round(2).to_string())
print('\nMonthly rates, control arm:')
print((100 * f[f.program == 0].pivot_table(index='mnum', values=['off', 'hos', 'hit'], aggfunc='mean')).round(2).to_string())

f['post'] = (f.mnum >= 7).astype(int)
f['t'] = f.mnum - 6.5


def rep(tag, r, key='program:post'):
    ci = r.conf_int().loc[key] * 100
    print(f'{100*r.params[key]:7.3f} [{ci[0]:7.3f},{ci[1]:7.3f}] p={r.pvalues[key]:.4g}  {tag}')


print('\n--- Trend / window robustness (outcome = combined 14-day follow-up) ---')
rep('baseline 2x2 (Jan-Jun vs Jul-Dec)',
    smf.ols('hit ~ program*post', data=f).fit(cov_type='cluster', cov_kwds={'groups': f.practice_id}))
g = f[f.mnum.isin([1, 2, 3, 4, 7, 8, 9, 10, 11, 12])]
rep('drop May-Jun (possible anticipation/ramp-up) from pre-period',
    smf.ols('hit ~ program*post', data=g).fit(cov_type='cluster', cov_kwds={'groups': g.practice_id}))
g = f[f.mnum.isin([5, 6, 7, 8])]
rep('narrow window May-Jun vs Jul-Aug',
    smf.ols('hit ~ program*post', data=g).fit(cov_type='cluster', cov_kwds={'groups': g.practice_id}))
g = f[f.mnum.isin([1, 2, 3, 4, 5, 6, 9, 10, 11, 12])]
rep('drop Jul-Aug (possible novelty spike)',
    smf.ols('hit ~ program*post', data=g).fit(cov_type='cluster', cov_kwds={'groups': g.practice_id}))
# linear differential trend control (identifies off deviation from trend)
r = smf.ols('hit ~ program + post + t + program:t + program:post', data=f).fit(
    cov_type='cluster', cov_kwds={'groups': f.practice_id})
rep('DiD controlling for differential linear time trend (program x t)', r)
print('   (program:t =', round(100 * r.params['program:t'], 3), 'pp/month, p=',
      round(r.pvalues['program:t'], 4), ')')
# trend extrapolation adjustment: subtract pre-trend-implied counterfactual drift
pre = f[f.post == 0]
rp = smf.ols('hit ~ program*t', data=pre).fit(cov_type='cluster', cov_kwds={'groups': pre.practice_id})
slope = rp.params['program:t']
# mean gap between post and pre period midpoints = 6 months
base = smf.ols('hit ~ program*post', data=f).fit(cov_type='cluster', cov_kwds={'groups': f.practice_id})
adj = base.params['program:post'] - slope * 6
print(f'{100*adj:7.3f} [      -,      -]           '
      f'  linear pre-trend extrapolation adjustment (naive DiD minus 6 x pre-slope)')
print('   pre-period differential slope =', round(100 * slope, 3), 'pp/month, p=', round(rp.pvalues['program:t'], 4))

print('\n--- channel-specific DiD ---')
for ch in ['off', 'hos']:
    rep(f'channel {ch}', smf.ols(f'{ch} ~ program*post', data=f).fit(
        cov_type='cluster', cov_kwds={'groups': f.practice_id}))

print('\n--- window length sensitivity (needs recompute) ---')
for w in [7, 14, 30]:
    pv = pd.concat([office, h517])[['member_id', 'service_date']].drop_duplicates().rename(
        columns={'service_date': 'pdate'})
    m = ed.merge(pv, on='member_id', how='left')
    gp = (m.pdate - m.service_date).dt.days
    m['h'] = ((gp >= 0) & (gp <= w)).fillna(False)
    q = m.groupby(['member_id', 'practice_id', 'service_date'], as_index=False).h.max()
    q = q.merge(ed, on=['member_id', 'practice_id', 'service_date'])
    q['post'] = (q.mnum >= 7).astype(int); q['h'] = q.h.astype(int)
    if w == 30:
        q = q[q.service_date <= '2025-12-15']  # avoid right-censoring (data end 2026-01-14)
    rep(f'{w}-day window', smf.ols('h ~ program*post', data=q).fit(
        cov_type='cluster', cov_kwds={'groups': q.practice_id}))

print('\n--- per-practice DiD spread (treated practices) ---')
pt = f.pivot_table(index=['practice_id', 'program'], columns='post', values='hit').reset_index()
pt['chg'] = 100 * (pt[1] - pt[0])
print(pt.groupby('program').chg.describe().round(2).to_string())
print('treated practices with change <= control mean change:',
      (pt[pt.program == 1].chg <= pt[pt.program == 0].chg.mean()).sum(), 'of 30')
f.to_csv('/tmp/work/panel_channels.csv', index=False)
