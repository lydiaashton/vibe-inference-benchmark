import pandas as pd, numpy as np
d = pd.read_csv('/Users/lydiaashton/vib-bench-runs/runs/claude-opus-5/T1/run3/data.csv')
print(d.shape, d.county_id.nunique(), d.year.min(), d.year.max())
print(d.isna().sum())
print("\nadoption cohorts:")
print(d.groupby('adoption_year').county_id.nunique())
print("\nnever treated counties:", d[d.adoption_year.isna()].county_id.nunique())
# check program consistency
d['implied'] = (d.year >= d.adoption_year).astype(int)
d.loc[d.adoption_year.isna(),'implied']=0
print("\nprogram mismatch rows:", (d.implied!=d.program).sum())
# panel balance
print("\nobs per county:", d.groupby('county_id').size().value_counts())
print("\ntreated county-years:", d.program.sum())
print(d.new_biz_per_10k.describe())
