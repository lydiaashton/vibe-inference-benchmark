import pandas as pd, numpy as np, statsmodels.formula.api as smf

f = pd.read_csv('/tmp/work/panel_channels.csv', dtype={'practice_id': str, 'member_id': str})
f['t'] = f.mnum - 6.5

# ---- event study per channel ----
for ch in ['off', 'hos', 'hit']:
    rels = sorted(set(f.mnum - 7))
    cols = []
    g = f.copy()
    for r_ in rels:
        if r_ == -1: continue
        c = 'e' + str(r_).replace('-', 'm')
        g[c] = ((g.mnum - 7 == r_) & (g.program == 1)).astype(int)
        cols.append((r_, c))
    r = smf.ols(f'{ch} ~ C(practice_id) + C(mnum) + ' + ' + '.join(c for _, c in cols),
                data=g).fit(cov_type='cluster', cov_kwds={'groups': g.practice_id})
    pre = [c for k, c in cols if k < -1]
    ft = r.f_test(' = 0, '.join(pre) + ' = 0')
    print(f'== channel {ch}: pre-period joint F p={float(ft.pvalue):.4f}; coefs (pp):',
          {k + 7: round(100 * r.params[c], 2) for k, c in cols})

# ---- pre-period slope: robustness to dropping each pre month ----
print('\nPre-period differential slope (pp/month), leave-one-month-out:')
for drop in [None] + list(range(1, 7)):
    p = f[(f.mnum <= 6) & (f.mnum != drop)]
    r = smf.ols('hit ~ program*t', data=p).fit(cov_type='cluster', cov_kwds={'groups': p.practice_id})
    print(f'  drop month {drop}: {100*r.params["program:t"]:6.3f}  p={r.pvalues["program:t"]:.3f}')
print('\nArm-specific pre-period slopes (pp/month):')
for a in [0, 1]:
    p = f[(f.mnum <= 6) & (f.program == a)]
    r = smf.ols('hit ~ t', data=p).fit(cov_type='cluster', cov_kwds={'groups': p.practice_id})
    print(f'  arm {a}: {100*r.params["t"]:6.3f} p={r.pvalues["t"]:.3f}')

# ---- pre-trend-extrapolation-adjusted DiD with practice cluster bootstrap CI ----
def est(df):
    pre = df[df.mnum <= 6]
    s = smf.ols('hit ~ program*t', data=pre).fit().params['program:t']
    b = smf.ols('hit ~ program*post', data=df).fit().params['program:post']
    return b - 6 * s, b, s

pt, b0, s0 = est(f)
print(f'\nPre-trend-extrapolated DiD: {100*pt:.3f} pp (naive {100*b0:.3f} minus 6 x {100*s0:.3f})')
rng = np.random.default_rng(11)
prs = f.practice_id.unique()
byp = {k: v for k, v in f.groupby('practice_id')}
boot = []
for _ in range(600):
    pick = rng.choice(prs, len(prs), replace=True)
    df = pd.concat([byp[p].assign(practice_id=f'{p}_{i}') for i, p in enumerate(pick)])
    try:
        boot.append(est(df)[0])
    except Exception:
        pass
boot = np.array(boot)
print(f'  cluster-bootstrap 95% CI: [{100*np.quantile(boot,.025):.3f},{100*np.quantile(boot,.975):.3f}] '
      f'({len(boot)} reps); share of reps > 0: {np.mean(boot>0):.3f}')

# ---- how large a differential trend would be needed to explain away the effect ----
print(f'\nDifferential trend needed to explain naive DiD of {100*b0:.2f} pp over 6-month gap in '
      f'period midpoints: {100*b0/6:.2f} pp/month (vs estimated pre-trend {100*s0:.2f} pp/month)')
