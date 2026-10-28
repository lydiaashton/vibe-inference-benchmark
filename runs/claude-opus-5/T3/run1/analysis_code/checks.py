import pandas as pd, numpy as np, statsmodels.formula.api as smf, statsmodels.api as sm

f = pd.read_csv('/tmp/work/panel_main.csv', dtype={'practice_id': str, 'member_id': str})
f['service_date'] = pd.to_datetime(f.service_date)
f['mnum'] = f.service_date.dt.month

# ---- monthly means by arm ----
t = f.pivot_table(index='mnum', columns='program', values='hit', aggfunc=['mean', 'size'])
t.columns = ['ctrl_rate', 'prog_rate', 'ctrl_n', 'prog_n']
t['diff_pp'] = 100 * (t.prog_rate - t.ctrl_rate)
print((t * [100, 100, 1, 1, 1]).round(2).to_string())

# ---- event study (month relative to July, ref = June = -1) ----
f['rel'] = f.mnum - 7
rels = sorted(f.rel.unique())
ivars = []
for r_ in rels:
    if r_ == -1:
        continue
    col = f'ev{r_:+d}'.replace('+', 'p').replace('-', 'm')
    f[col] = ((f.rel == r_) & (f.program == 1)).astype(int)
    ivars.append((r_, col))
es = smf.ols('hit ~ C(practice_id) + C(rel) + ' + ' + '.join(c for _, c in ivars),
             data=f).fit(cov_type='cluster', cov_kwds={'groups': f.practice_id})
print('\nEvent study (practice FE + calendar-month FE), coef in pp, ref = June (rel -1):')
for r_, c in ivars:
    lo, hi = es.conf_int().loc[c] * 100
    print(f'  month {r_+7:2d} (rel {r_:+d}): {100*es.params[c]:7.3f} [{lo:7.3f},{hi:7.3f}]')

# ---- joint test of pre-period coefficients ----
pre = [c for r_, c in ivars if r_ < -1]
print('\nJoint F-test, pre-period interactions = 0:', es.f_test(' = 0, '.join(pre) + ' = 0'))

# ---- placebo DiD within pre-period (Jan-Mar vs Apr-Jun) ----
p = f[f.mnum <= 6].copy(); p['post'] = (p.mnum >= 4).astype(int)
r = smf.ols('hit ~ program*post', data=p).fit(cov_type='cluster', cov_kwds={'groups': p.practice_id})
ci = r.conf_int().loc['program:post'] * 100
print(f'\nPlacebo DiD (Apr-Jun vs Jan-Mar, pre only): {100*r.params["program:post"]:.3f} pp '
      f'[{ci[0]:.3f},{ci[1]:.3f}] p={r.pvalues["program:post"]:.3f}')

# ---- linear pre-trend difference ----
p2 = f[f.mnum <= 6].copy()
r2 = smf.ols('hit ~ program*mnum', data=p2).fit(cov_type='cluster', cov_kwds={'groups': p2.practice_id})
print(f'Differential linear pre-trend (pp/month): {100*r2.params["program:mnum"]:.3f} '
      f'p={r2.pvalues["program:mnum"]:.3f}')

# ---- main spec variants ----
print('\n--- Main-definition specification variants (DiD in pp) ---')


def rep(tag, r, key='program:post'):
    ci = r.conf_int().loc[key] * 100
    print(f'{100*r.params[key]:7.3f} [{ci[0]:7.3f},{ci[1]:7.3f}] p={r.pvalues[key]:.4g}  {tag}')
    return 100 * r.params[key], ci[0], ci[1], r.pvalues[key]


S = {}
S['plain LPM, cluster by practice'] = rep('plain LPM, cluster by practice',
    smf.ols('hit ~ program*post', data=f).fit(cov_type='cluster', cov_kwds={'groups': f.practice_id}))
S['LPM iid SE'] = rep('LPM, iid (unclustered) SE', smf.ols('hit ~ program*post', data=f).fit())
S['LPM HC1'] = rep('LPM, HC1 robust SE', smf.ols('hit ~ program*post', data=f).fit(cov_type='HC1'))
S['LPM cluster by member'] = rep('LPM, cluster by member',
    smf.ols('hit ~ program*post', data=f).fit(cov_type='cluster', cov_kwds={'groups': f.member_id}))
r = smf.ols('hit ~ program:post + C(practice_id) + C(mnum)', data=f).fit(
    cov_type='cluster', cov_kwds={'groups': f.practice_id})
S['TWFE'] = rep('two-way FE (practice + calendar month), cluster practice', r, 'program:post')
r = smf.ols('hit ~ program:post + C(practice_id) + C(mnum) + C(acuity)', data=f).fit(
    cov_type='cluster', cov_kwds={'groups': f.practice_id})
S['TWFE+acuity'] = rep('two-way FE + ED acuity controls', r, 'program:post')
# practice x period aggregate (unweighted and weighted)
agg = f.groupby(['practice_id', 'program', 'post'], as_index=False).hit.agg(['mean', 'size'])
agg.columns = ['practice_id', 'program', 'post', 'rate', 'n']
S['agg unweighted'] = rep('practice-level 2x2 aggregate, unweighted OLS',
    smf.ols('rate ~ program*post', data=agg).fit(cov_type='cluster', cov_kwds={'groups': agg.practice_id}))
S['agg weighted'] = rep('practice-level 2x2 aggregate, weighted by ED visits',
    smf.wls('rate ~ program*post', data=agg, weights=agg.n).fit(
        cov_type='cluster', cov_kwds={'groups': agg.practice_id}))
# practice-level DiD differences -> simple t-test across 60 practices
w = agg.pivot_table(index=['practice_id', 'program'], columns='post', values='rate').reset_index()
w['chg'] = w[1] - w[0]
a, b = w[w.program == 1].chg, w[w.program == 0].chg
import scipy.stats as st
tt = st.ttest_ind(a, b, equal_var=False)
se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
dfw = tt.df
crit = st.t.ppf(0.975, dfw)
print(f'{100*(a.mean()-b.mean()):7.3f} [{100*(a.mean()-b.mean()-crit*se):7.3f},'
      f'{100*(a.mean()-b.mean()+crit*se):7.3f}] p={tt.pvalue:.4g}  '
      f'practice-level diff-in-means t-test (Welch, 60 practices)')
# logit average marginal effect of interaction
lg = smf.logit('hit ~ program*post', data=f).fit(disp=0)
print('logit interaction coef (log-odds):', round(lg.params['program:post'], 4),
      'p=', round(lg.pvalues['program:post'], 5))

# ---- wild cluster bootstrap on the interaction ----
rng = np.random.default_rng(7)
X = pd.get_dummies(f[['program', 'post']].assign(ix=f.program * f.post)).astype(float)
X = sm.add_constant(X[['program', 'post', 'ix']])
y = f.hit.values
base = sm.OLS(y, X).fit()
gid = f.practice_id.values
# restricted model: impose interaction = 0
Xr = X.drop(columns='ix')
rfit = sm.OLS(y, Xr).fit()
resid = rfit.resid
fitted = rfit.fittedvalues
ug = pd.unique(gid)
tstats = []
bhat = base.params['ix']
se0 = sm.OLS(y, X).fit(cov_type='cluster', cov_kwds={'groups': gid}).bse['ix']
for _ in range(2000):
    w_ = pd.Series(rng.choice([-1.0, 1.0], len(ug)), index=ug).reindex(gid).values
    ystar = fitted + resid * w_
    fit = sm.OLS(ystar, X).fit(cov_type='cluster', cov_kwds={'groups': gid})
    tstats.append(fit.params['ix'] / fit.bse['ix'])
tstats = np.array(tstats)
tobs = bhat / se0
pboot = np.mean(np.abs(tstats) >= np.abs(tobs))
q = np.quantile(tstats, [0.025, 0.975])
print(f'\nWild cluster bootstrap (Rademacher, 2000 reps, 60 clusters): p={pboot:.4f}; '
      f'CI from bootstrap-t: [{100*(bhat-q[1]*se0):.3f},{100*(bhat-q[0]*se0):.3f}] pp')

# ---- randomization inference: permute program label across 60 practices ----
pr = f.groupby('practice_id').program.first()
obs = bhat
cnt = 0
NP = 2000
cell = f.groupby(['practice_id', 'post']).hit.agg(['sum', 'size']).unstack()
s0, s1 = cell['sum'][0].values, cell['sum'][1].values
n0, n1 = cell['size'][0].values, cell['size'][1].values
idx = np.arange(60)
def did_from(mask):
    tp = s1[mask].sum()/n1[mask].sum() - s0[mask].sum()/n0[mask].sum()
    cp = s1[~mask].sum()/n1[~mask].sum() - s0[~mask].sum()/n0[~mask].sum()
    return tp - cp
draws = []
for _ in range(NP):
    m = np.zeros(60, bool); m[rng.choice(60, 30, replace=False)] = True
    draws.append(did_from(m))
draws = np.array(draws)
m_obs = np.array([pr.loc[c] == 1 for c in cell.index])
obs_did = did_from(m_obs)
print(f'Randomization inference: observed DiD={100*obs_did:.3f} pp, '
      f'two-sided p={np.mean(np.abs(draws)>=abs(obs_did)):.4f}, '
      f'null 2.5/97.5 pct=[{100*np.quantile(draws,.025):.3f},{100*np.quantile(draws,.975):.3f}]')

# ---- composition checks ----
print('\nED visit counts & acuity mix by arm/period:')
print(f.groupby(['program', 'post']).size().rename('n_ed'))
print(pd.crosstab([f.program, f.post], f.acuity, normalize='index').round(4).to_string())
print('\nunique members with ED visit by arm/period:')
print(f.groupby(['program', 'post']).member_id.nunique())
print('\nED visits per member (repeat use):')
print(f.groupby(['program', 'post']).apply(lambda x: len(x)/x.member_id.nunique(), include_groups=False).round(3))

# ---- window sensitivity ----
print('\nAlternative follow-up windows handled in analyze2.py')
