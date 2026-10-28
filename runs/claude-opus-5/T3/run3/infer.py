import sys
import numpy as np, pandas as pd, statsmodels.formula.api as smf
from scipy import stats
pd.set_option('display.width', 250)
rng = np.random.default_rng(20250701)

e = pd.read_csv(sys.argv[1]); e['ed_date'] = pd.to_datetime(e['ed_date'])
e['gxp'] = e.program * e.post
G = e.practice_id.nunique(); crit = stats.t.ppf(0.975, G - 1)

y = e.fu_main.values
X = np.column_stack([np.ones(len(e)), e.program.values, e.post.values, e.gxp.values])
cl = pd.factorize(e.practice_id)[0]

def ols_cluster(y, X, cl):
    XtXi = np.linalg.inv(X.T @ X)
    b = XtXi @ X.T @ y
    u = y - X @ b
    meat = np.zeros((X.shape[1],) * 2)
    for g in np.unique(cl):
        Xg, ug = X[cl == g], u[cl == g]
        s = Xg.T @ ug
        meat += np.outer(s, s)
    n, k = X.shape; ng = len(np.unique(cl))
    adj = ng / (ng - 1) * (n - 1) / (n - k)
    V = XtXi @ meat @ XtXi * adj
    return b, np.sqrt(np.diag(V))

b, se = ols_cluster(y, X, cl)
print(f'point estimate (CR1, cluster practice): {b[3]*100:.3f} pp, se {se[3]*100:.3f}, '
      f'95% CI [{(b[3]-crit*se[3])*100:.3f},{(b[3]+crit*se[3])*100:.3f}]')

# --- wild cluster bootstrap-t (Rademacher), unrestricted (percentile-t CI) ---
B = 2000
Xr = X[:, :3]                      # restricted design (H0: beta3 = 0) for p-value
br, _ = ols_cluster(y, Xr, cl)
ur = y - Xr @ br
tstats = np.empty(B); bstar = np.empty(B)
u_full = y - X @ b
gids = np.unique(cl)
for i in range(B):
    w = rng.choice([-1.0, 1.0], size=len(gids))[cl]
    ys = Xr @ br + ur * w                       # null-imposed -> p-value
    bb, ss = ols_cluster(ys, X, cl)
    tstats[i] = bb[3] / ss[3]
    ys2 = X @ b + u_full * w                    # unrestricted -> CI
    bb2, ss2 = ols_cluster(ys2, X, cl)
    bstar[i] = (bb2[3] - b[3]) / ss2[3]
t_obs = b[3] / se[3]
p_wb = (np.sum(np.abs(tstats) >= abs(t_obs)) + 1) / (B + 1)
lo, hi = np.quantile(bstar, [0.025, 0.975])
print(f'wild cluster bootstrap (Rademacher, B={B}): p={p_wb:.4f}, '
      f'percentile-t 95% CI [{(b[3]-hi*se[3])*100:.3f},{(b[3]-lo*se[3])*100:.3f}]')

# --- randomization inference: reassign program status across 60 practices ---
pp = e[['practice_id']].drop_duplicates().reset_index(drop=True)
real = b[3] * 100
nperm = 2000
draws = np.empty(nperm)
pmap = {p: i for i, p in enumerate(pp.practice_id)}
pidx = e.practice_id.map(pmap).values
post = e.post.values
for i in range(nperm):
    assign = rng.permutation(np.r_[np.ones(30), np.zeros(30)])
    g = assign[pidx]
    Xp = np.column_stack([np.ones(len(e)), g, post, g * post])
    bp = np.linalg.lstsq(Xp, y, rcond=None)[0]
    draws[i] = bp[3] * 100
p_ri = (np.sum(np.abs(draws) >= abs(real)) + 1) / (nperm + 1)
print(f'randomization inference (2000 draws, permuting program across practices): p={p_ri:.4f}, '
      f'RI null sd={draws.std():.3f} pp, RI 95% range [{np.quantile(draws,.025):.2f},{np.quantile(draws,.975):.2f}]')

# --- practice-level DiD distribution ---
col = e.groupby(['practice_id', 'program', 'post']).fu_main.mean().unstack()
col['d'] = (col[1] - col[0]) * 100
col = col.reset_index()
print()
print('practice-level pre->post change in follow-up rate (pp):')
print(col.groupby('program').d.describe().round(2).to_string())
print('share of program practices with positive change:',
      round((col[col.program == 1].d > 0).mean(), 3),
      '| control:', round((col[col.program == 0].d > 0).mean(), 3))

# --- leave-one-practice-out robustness ---
outs = []
for p in e.practice_id.unique():
    s = e[e.practice_id != p]
    r = smf.ols('fu_main ~ program + post + gxp', data=s).fit()
    outs.append(r.params['gxp'] * 100)
print(f'leave-one-practice-out DiD range: [{min(outs):.3f},{max(outs):.3f}] pp')

# --- falsification outcomes (should be ~0) ---
print()
print('=== falsification / balance outcomes, same DiD design ===')
for col_, lab in [('fu_spec14', 'specialist office visit within 14d of ED'),
                  ('fu_lab14', 'lab within 14d of ED'),
                  ('fu_pre14', 'PCP visit in the 14 days BEFORE the ED visit')]:
    if col_ in e.columns:
        r = smf.ols(f'{col_} ~ program + post + gxp', data=e).fit(cov_type='cluster', cov_kwds={'groups': e.practice_id})
        bb, ss = r.params['gxp'] * 100, r.bse['gxp'] * 100
        print(f'  {lab:<48s} b={bb:7.3f} se={ss:5.3f} p={2*stats.t.sf(abs(bb/ss),G-1):.3f}')
