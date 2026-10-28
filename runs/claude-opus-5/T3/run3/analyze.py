import sys
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
import statsmodels.api as sm
from scipy import stats

e = pd.read_csv(sys.argv[1])
e['ed_date'] = pd.to_datetime(e['ed_date'])
e['t'] = (e.ed_date.dt.year - 2025) * 12 + e.ed_date.dt.month - 6   # months rel. to June 2025
e['gxp'] = e.program * e.post
G = e.practice_id.nunique()

def did(data, y, formula=None, label=''):
    f = formula or f'{y} ~ program + post + program:post'
    m = smf.ols(f, data=data).fit(cov_type='cluster', cov_kwds={'groups': data.practice_id})
    key = [k for k in m.params.index if k in ('program:post', 'gxp')][0]
    b, se = m.params[key] * 100, m.bse[key] * 100
    crit = stats.t.ppf(0.975, G - 1)
    print(f'{label or f:<62s} b={b:7.3f} se={se:6.3f} ci=[{b-crit*se:7.3f},{b+crit*se:7.3f}] p={2*stats.t.sf(abs(b/se), G-1):.4f}')
    return b, se, m

print('=== MAIN definition (office PCP E&M + hospital-based family-practice clinic G0463/0517) ===')
b_main, se_main, m_main = did(e, 'fu_main', label='S1 2x2 LPM, cluster practice')
did(e, 'fu_main', 'fu_main ~ gxp + C(practice_id) + C(month)', 'S2 TWFE (practice + month FE)')
did(e, 'fu_main', 'fu_main ~ gxp + C(practice_id) + C(month) + C(acuity)', 'S3 TWFE + ED acuity controls')
did(e, 'fu_main', 'fu_main ~ program + post + program:post + program:t', 'S4 2x2 + group-specific linear trend')

# practice-period collapsed
col = e.groupby(['practice_id', 'program', 'post']).fu_main.agg(['mean', 'size']).reset_index()
m = smf.ols('mean ~ program + post + program:post', data=col).fit()
b = m.params['program:post'] * 100; se = m.bse['program:post'] * 100
crit = stats.t.ppf(0.975, m.df_resid)
print(f'{"S5 practice-period collapsed (unweighted, HC0-free OLS)":<62s} b={b:7.3f} se={se:6.3f} ci=[{b-crit*se:7.3f},{b+crit*se:7.3f}]')
mw = smf.wls('mean ~ program + post + program:post', data=col, weights=col['size']).fit()
bw, sew = mw.params['program:post'] * 100, mw.bse['program:post'] * 100
print(f'{"S6 practice-period collapsed (visit-weighted)":<62s} b={bw:7.3f} se={sew:6.3f} ci=[{bw-crit*sew:7.3f},{bw+crit*sew:7.3f}]')

# practice-level DiD of changes (60 obs -> t-test on diff-in-diff of practice deltas)
w = col.pivot_table(index=['practice_id', 'program'], columns='post', values='mean').reset_index()
w['delta'] = w[1] - w[0]
tt = stats.ttest_ind(w[w.program == 1].delta, w[w.program == 0].delta, equal_var=False)
d1, d0 = w[w.program == 1].delta, w[w.program == 0].delta
dm = (d1.mean() - d0.mean()) * 100
sed = np.sqrt(d1.var(ddof=1) / len(d1) + d0.var(ddof=1) / len(d0)) * 100
print(f'{"S7 t-test on practice-level pre/post changes (Welch)":<62s} b={dm:7.3f} se={sed:6.3f} ci=[{dm-2.0*sed:7.3f},{dm+2.0*sed:7.3f}] p={tt.pvalue:.4g}')

# logit average marginal effect of interaction (discrete DiD of predicted probs)
lg = smf.logit('fu_main ~ program + post + program:post', data=e).fit(disp=0,
      cov_type='cluster', cov_kwds={'groups': e.practice_id})
import itertools
def p(pg, po):
    x = pd.DataFrame({'program': [pg], 'post': [po]})
    return lg.predict(x)[0]
print(f'{"S8 logit, DiD of predicted probabilities":<62s} b={((p(1,1)-p(1,0))-(p(0,1)-p(0,0)))*100:7.3f}')

print()
print('=== alternative PCP definitions / windows (2x2 LPM, cluster practice) ===')
for y in ['fu_profonly', 'fu_wide', 'fu_anyoffice', 'fu_main_7d', 'fu_main_30d', 'fu_main_excl_sameday']:
    did(e, y, label=f'S: {y}')

print()
print('=== event study (fu_main, ref = 2025-06), coef on program x month, pp ===')
months = sorted(e.month.unique())
ref = '2025-06'
ivars = []
for mo in months:
    if mo == ref:
        continue
    v = 'g_' + mo.replace('-', '_')
    e[v] = ((e.month == mo) & (e.program == 1)).astype(int)
    ivars.append((mo, v))
es = smf.ols('fu_main ~ C(practice_id) + C(month) + ' + ' + '.join(v for _, v in ivars),
             data=e).fit(cov_type='cluster', cov_kwds={'groups': e.practice_id})
crit = stats.t.ppf(0.975, G - 1)
rows = []
for mo, v in ivars:
    b, se = es.params[v] * 100, es.bse[v] * 100
    rows.append((mo, b, se, b - crit * se, b + crit * se))
for mo, b, se, lo, hi in sorted(rows):
    print(f'  {mo}  {b:7.2f}  se {se:5.2f}  [{lo:7.2f},{hi:7.2f}]')

print()
print('=== pre-trend tests (pre-period only, Jan-Jun 2025) ===')
pre = e[e.post == 0].copy()
mt = smf.ols('fu_main ~ program + t + program:t', data=pre).fit(
        cov_type='cluster', cov_kwds={'groups': pre.practice_id})
b, se = mt.params['program:t'] * 100, mt.bse['program:t'] * 100
print(f'  differential pre-trend per month: {b:.3f} pp (se {se:.3f}), p={2*stats.t.sf(abs(b/se), G-1):.3f}')
# joint test of pre-period event-study interactions
pres = [v for mo, v in ivars if mo < '2025-07']
wt = es.f_test([f'{k} = 0' for k in pres])
print(f'  joint F-test, pre-period program x month interactions = 0: F={float(wt.fvalue):.2f}, p={float(wt.pvalue):.3f}')
# placebo: within pre-period, fake launch Apr 1
pre['fpost'] = (pre.ed_date >= pd.Timestamp('2025-04-01')).astype(int)
mp = smf.ols('fu_main ~ program + fpost + program:fpost', data=pre).fit(
        cov_type='cluster', cov_kwds={'groups': pre.practice_id})
b, se = mp.params['program:fpost'] * 100, mp.bse['program:fpost'] * 100
print(f'  placebo DiD (fake launch 2025-04-01, pre-period only): {b:.3f} pp (se {se:.3f}), p={2*stats.t.sf(abs(b/se), G-1):.3f}')

print()
print('=== balance / composition checks ===')
print('ED visits per practice-half:'); print(e.groupby(['program', 'post']).size().unstack())
print('ED volume DiD (visits per practice):')
vc = e.groupby(['practice_id', 'program', 'post']).size().reset_index(name='n')
mv = smf.ols('n ~ program + post + program:post', data=vc).fit()
print(f'  b={mv.params["program:post"]:.2f} visits (se {mv.bse["program:post"]:.2f}), p={mv.pvalues["program:post"]:.3f}')
print('ED acuity mix by group/post (share):')
print(pd.crosstab([e.program, e.post], e.acuity, normalize='index').round(4))
print('unique members per group/post (ED):')
print(e.groupby(['program', 'post']).member_id.nunique().unstack())
print('repeat ED visits share:')
print(e.assign(rep=e.duplicated(['member_id'])).groupby(['program', 'post']).rep.mean().round(4).unstack())

np.save('/tmp/main_point.npy', np.array([b_main, se_main]))
