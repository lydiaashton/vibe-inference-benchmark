import sys
import numpy as np, pandas as pd, statsmodels.formula.api as smf
from scipy import stats
pd.set_option('display.width', 250)
e = pd.read_csv(sys.argv[1], dtype={'member_id': str, 'practice_id': str, 'claim_id': str})
e['ed_date'] = pd.to_datetime(e['ed_date']); e['gxp'] = e.program * e.post
e['t'] = e.ed_date.dt.month - 6
G = 60; crit = stats.t.ppf(0.975, G - 1)

def did(data, y='fu_main', f=None, lab='', cl='practice_id'):
    f = f or f'{y} ~ program + post + program:post'
    r = smf.ols(f, data=data).fit(cov_type='cluster', cov_kwds={'groups': data[cl]})
    k = 'program:post' if 'program:post' in r.params.index else 'gxp'
    b, se = r.params[k] * 100, r.bse[k] * 100
    print(f'{lab:<60s} n={len(data):6d} b={b:7.3f} se={se:6.3f} [{b-crit*se:7.3f},{b+crit*se:7.3f}] p={2*stats.t.sf(abs(b/se),G-1):.4f}')
    return b, se

did(e, lab='REFERENCE: 2x2 LPM, visit level, cluster practice')
# ED unit = member-day instead of claim
md = e.sort_values('acuity', ascending=False).drop_duplicates(['member_id', 'ed_date'])
did(md, lab='ED unit = member-day (dedup 11 same-day double claims)')
# drop repeat ED visits within 14 days of a previous ED visit (index visits only)
e2 = e.sort_values(['member_id', 'ed_date']).copy()
e2['prev'] = e2.groupby('member_id').ed_date.shift()
e2['gapprev'] = (e2.ed_date - e2.prev).dt.days
did(e2[~(e2.gapprev <= 14)], lab='index ED visits only (drop repeats within 14d of prior ED)')
# first ED visit per member per period
did(e.sort_values('ed_date').drop_duplicates(['member_id', 'post']), lab='first ED visit per member per period')
# cluster by member instead of practice
did(e, lab='cluster SE by member instead of practice', cl='member_id')
# practice-month aggregation with FE, weighted
pm = e.groupby(['practice_id', 'program', 'month']).agg(y=('fu_main', 'mean'), n=('fu_main', 'size')).reset_index()
pm['post'] = (pm.month >= '2025-07').astype(int)
r = smf.wls('y ~ gxp + C(practice_id) + C(month)', data=pm.assign(gxp=pm.program * pm.post), weights=pm.n).fit(
    cov_type='cluster', cov_kwds={'groups': pm.practice_id})
b, se = r.params['gxp'] * 100, r.bse['gxp'] * 100
print(f'{"practice-month panel, TWFE, visit-weighted":<60s} n={len(pm):6d} b={b:7.3f} se={se:6.3f} [{b-crit*se:7.3f},{b+crit*se:7.3f}]')
r = smf.ols('y ~ gxp + C(practice_id) + C(month)', data=pm.assign(gxp=pm.program * pm.post)).fit(
    cov_type='cluster', cov_kwds={'groups': pm.practice_id})
b, se = r.params['gxp'] * 100, r.bse['gxp'] * 100
print(f'{"practice-month panel, TWFE, unweighted":<60s} n={len(pm):6d} b={b:7.3f} se={se:6.3f} [{b-crit*se:7.3f},{b+crit*se:7.3f}]')
# drop July (ramp-up month)
did(e[e.month != '2025-07'], lab='drop launch month (July 2025)')
# symmetric windows around launch: Apr-Jun vs Jul-Sep
did(e[e.month.isin(['2025-04', '2025-05', '2025-06', '2025-07', '2025-08', '2025-09'])],
    lab='narrow window Apr-Jun vs Jul-Sep')
did(e[e.month.isin(['2025-05', '2025-06', '2025-07', '2025-08'])], lab='narrow window May-Jun vs Jul-Aug')
# how large a differential trend would be needed to explain the estimate?
dt = e[e.post == 1].t.mean() - e[e.post == 0].t.mean()
b0 = 7.869
print(f'\nrequired differential linear trend to fully explain main estimate: {b0/dt:.3f} pp/month '
      f'(pre-period estimated differential trend = 0.909 +/- 0.402 pp/month)')
print(f'required trend for the hospital-clinic channel (6.239 pp): {6.239/dt:.3f} pp/month '
      f'(its pre-period differential trend = 0.092 +/- 0.187 pp/month)')
