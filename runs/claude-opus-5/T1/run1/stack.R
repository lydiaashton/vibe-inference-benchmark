suppressMessages({library(data.table); library(fixest)})
d <- fread('/Users/lydiaashton/vib-bench-runs/runs/claude-opus-5/T1/run1/data.csv')
d[, cohort := fifelse(is.na(adoption_year), 0L, as.integer(adoption_year))]
# stacked DiD: one sub-experiment per cohort, controls = never-treated only (clean controls)
L <- list()
for (gg in c(2006L,2011L,2016L)) {
  sub <- d[cohort %in% c(gg,0L)]
  sub[, `:=`(stk=gg, tr=as.integer(cohort==gg), post=as.integer(year>=gg))]
  L[[as.character(gg)]] <- sub
}
s <- rbindlist(L)
s[, `:=`(fe_id=paste(stk,county_id), fe_t=paste(stk,year))]
m <- feols(new_biz_per_10k ~ I(tr*post) | fe_id + fe_t, data=s, cluster=~county_id)
cat("=== Stacked DiD (clean never-treated controls, equal-weighted sub-experiments) ===\n")
print(coeftable(m))
# reweight stack so treated county-years match the target weights
s[, w := 1]
m2 <- feols(new_biz_per_10k ~ I(tr*post) | fe_id + fe_t, data=s, weights=~w, cluster=~county_id)
cat("\n=== Sun-Abraham recheck with explicit cohort weights ===\n")
d3 <- copy(d)[, coh := fifelse(cohort==0L, 10000L, cohort)]
m5 <- feols(new_biz_per_10k ~ sunab(coh, year) | county_id + year, data=d3, cluster=~county_id)
print(summary(m5, agg="att")$coeftable)
