suppressMessages({library(did); library(fixest); library(data.table)})
d <- fread('/Users/lydiaashton/vib-bench-runs/runs/claude-opus-5/T1/run1/data.csv')
d[, cohort := fifelse(is.na(adoption_year), 0L, as.integer(adoption_year))]
d[, rel := fifelse(cohort==0L, -1000L, year - cohort)]
cat("treated county-years:", sum(d$program), " total:", nrow(d), "\n")
cat("treated county-years by cohort:\n"); print(d[program==1, .N, by=cohort][order(cohort)])

cat("\n================ SPEC 1: static TWFE ================\n")
m1 <- feols(new_biz_per_10k ~ program | county_id + year, data=d, cluster=~county_id)
print(summary(m1))

cat("\n================ SPEC 2: TWFE event study (dynamic, all cohorts) ================\n")
d2 <- copy(d)[, relf := fifelse(cohort==0L, -1L, year-cohort)]
m2 <- feols(new_biz_per_10k ~ i(relf, cohort!=0, ref=-1) | county_id + year, data=d2, cluster=~county_id)
print(coeftable(m2))

cat("\n================ SPEC 3: Callaway-Sant'Anna, never-treated control ================\n")
cs_nt <- att_gt(yname="new_biz_per_10k", tname="year", idname="county_id", gname="cohort",
                xformla=~1, data=d, control_group="nevertreated", base_period="universal",
                bstrap=TRUE, biters=5000, clustervars="county_id", cband=FALSE)
print(summary(cs_nt))
cat("\n-- simple aggregation (ATT over treated county-years) --\n")
a_s <- aggte(cs_nt, type="simple", na.rm=TRUE); print(summary(a_s))
cat("\n-- dynamic (event-time) --\n")
a_d <- aggte(cs_nt, type="dynamic", na.rm=TRUE); print(summary(a_d))
cat("\n-- group (cohort) --\n")
a_g <- aggte(cs_nt, type="group", na.rm=TRUE); print(summary(a_g))

cat("\n================ SPEC 4: CS, not-yet-treated control ================\n")
cs_ny <- att_gt(yname="new_biz_per_10k", tname="year", idname="county_id", gname="cohort",
                xformla=~1, data=d, control_group="notyettreated", base_period="universal",
                bstrap=TRUE, biters=5000, clustervars="county_id", cband=FALSE)
print(summary(aggte(cs_ny, type="simple", na.rm=TRUE)))

cat("\n================ SPEC 5: Sun-Abraham (fixest sunab) ================\n")
d3 <- copy(d)[, coh := fifelse(cohort==0L, 10000L, cohort)]
m5 <- feols(new_biz_per_10k ~ sunab(coh, year) | county_id + year, data=d3, cluster=~county_id)
cat("SA aggregated ATT (att):\n"); print(summary(m5, agg="att"))

cat("\n================ SPEC 6: BJS imputation (manual) ================\n")
# estimate county+year FE on untreated obs only, impute counterfactual for treated obs
mu <- feols(new_biz_per_10k ~ 1 | county_id + year, data=d[program==0])
tr <- d[program==1]
tr[, yhat := predict(mu, newdata=tr)]
tr[, tau := new_biz_per_10k - yhat]
cat("BJS imputation ATT (unweighted mean over treated county-years):", round(mean(tr$tau, na.rm=TRUE),4),
    "  n used:", sum(!is.na(tr$tau)), "of", nrow(tr), "\n")
cat("by cohort:\n"); print(tr[, .(att=round(mean(tau,na.rm=TRUE),3), n=sum(!is.na(tau))), by=cohort][order(cohort)])
cat("by event time:\n"); print(tr[, .(att=round(mean(tau,na.rm=TRUE),3)), by=rel][order(rel)])

cat("\n================ SPEC 7: county-specific linear trends ================\n")
m7 <- feols(new_biz_per_10k ~ program | county_id + year + county_id[year], data=d, cluster=~county_id)
print(coeftable(m7))

saveRDS(list(cs_nt=cs_nt, cs_ny=cs_ny), "/tmp/sbgrant/cs.rds")
