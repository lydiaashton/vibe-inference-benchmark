import pandas as pd, numpy as np
d = pd.read_csv('/Users/lydiaashton/vib-bench-runs/runs/claude-opus-5/T1/run3/data.csv')
d['cohort']=d.adoption_year.fillna(0).astype(int)
p = d.pivot_table(index='year',columns='cohort',values='new_biz_per_10k',aggfunc='mean')
pd.set_option('display.width',200)
print(p.round(2))
print("\nfirst differences by cohort:")
print(p.diff().round(2))
