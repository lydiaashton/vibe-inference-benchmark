suppressMessages({library(did); library(data.table); library(fixest)})
x <- readRDS("/tmp/sbgrant/cs.rds"); g <- x$cs_nt
d <- fread('/Users/lydiaashton/vib-bench-runs/runs/claude-opus-5/T1/run1/data.csv')
d[, cohort := fifelse(is.na(adoption_year), 0L, as.integer(adoption_year))]

dt <- data.table(group=g$group, t=g$t, att=g$att, se=g$se)
dt[, e := t-group]
base <- dt[, .(bt=max(t[t<group])), by=group]   # universal base period = g-1
dt <- merge(dt, base, by="group")
pre <- dt[t<group & t!=bt]                       # exclude base period (att==0 by construction)
idx <- which(g$t < g$group & g$t != base$bt[match(g$group, base$group)])
V <- g$V_analytical[idx, idx, drop=FALSE]; b <- g$att[idx]
W <- as.numeric(t(b) %*% solve(V) %*% b)
cat("=== Joint pre-trend Wald test (", length(idx), "pre-period ATT(g,t), cohorts 2011 & 2016) ===\n")
cat("Wald:", round(W,3), " df:", length(idx), " p:", round(pchisq(W,length(idx),lower.tail=FALSE),4), "\n")
cat("max |pre-period ATT|:", round(max(abs(b)),3), "\n")
cat("NOTE: cohort 2006 contributes ZERO testable pre-periods (only 1 pre-year, 2005 = base).\n")

cat("\n=== Pre-trend SLOPE per cohort (regress pre-period ATT(g,t) on event time) ===\n")
for (gg in c(2011,2016)) {
  p <- dt[group==gg & t<group]
  fit <- lm(att ~ e, data=p); ci <- confint(fit)["e",]
  cat(sprintf("cohort %d: slope = %+.4f/yr  [%.4f, %.4f]  (n pre = %d)\n", gg,
      coef(fit)["e"], ci[1], ci[2], nrow(p)))
}
p <- dt[t<group]; fit <- lm(att ~ e, data=p); ci<-confint(fit)["e",]
cat(sprintf("pooled (2011+2016): slope = %+.4f/yr  [%.4f, %.4f]\n", coef(fit)["e"], ci[1], ci[2]))

cat("\n=== Effect GROWTH: slope of post-period ATT(g,t) on exposure, per cohort ===\n")
for (gg in c(2006,2011,2016)) {
  p <- dt[group==gg & t>=group]; fit <- lm(att ~ e, data=p)
  cat(sprintf("cohort %d: %+.4f per exposure-year (intercept %+.3f, n post = %d)\n",
      gg, coef(fit)["e"], coef(fit)[1], nrow(p)))
}

cat("\n=== Linear-trend sensitivity (Honest-DiD style, manual) ===\n")
tr <- d[program==1][, e := year-cohort]
mexp <- mean(tr$e + 1)
att <- 7.179282
cat("mean (exposure+1) over treated county-years:", round(mexp,3), "\n")
cat("break-even differential trend delta that drives ATT to 0:", round(att/mexp,4), "per year\n")
cat("  for scale: never-treated counties' own trend is 0.267/yr; measured pre-trend slopes ~0.00 +/- 0.05\n")
for (delta in c(0.05,0.1,0.2,0.3,0.5)) {
  cat(sprintf("  if delta = %.2f/yr -> bias-adjusted ATT = %.3f\n", delta, att - delta*mexp))
}

cat("\n=== Jackknife over the 26 never-treated control counties (thin control pool) ===\n")
nt <- unique(d[cohort==0L, county_id]); res <- numeric(0)
for (cc in nt) {
  dd <- d[county_id != cc]
  m <- att_gt(yname="new_biz_per_10k", tname="year", idname="county_id", gname="cohort",
              xformla=~1, data=dd, control_group="nevertreated", base_period="universal",
              bstrap=FALSE, cband=FALSE)
  res <- c(res, aggte(m, type="simple", na.rm=TRUE)$overall.att)
}
cat("ATT range dropping one never-treated county at a time: [",
    round(min(res),3), ",", round(max(res),3), "]  sd =", round(sd(res),4), "\n")

cat("\n=== CS with 1 anticipation period (robustness to anticipation) ===\n")
ma <- att_gt(yname="new_biz_per_10k", tname="year", idname="county_id", gname="cohort",
             xformla=~1, data=d, control_group="nevertreated", base_period="universal",
             anticipation=1, bstrap=TRUE, biters=2000, clustervars="county_id", cband=FALSE)
aa <- aggte(ma, type="simple", na.rm=TRUE)
cat("ATT:", round(aa$overall.att,4), " se:", round(aa$overall.se,4), "\n")

cat("\n=== CS restricted to cohorts with testable pre-trends (2011,2016; drop 2006) ===\n")
d2 <- d[cohort != 2006L]
m2 <- att_gt(yname="new_biz_per_10k", tname="year", idname="county_id", gname="cohort",
             xformla=~1, data=d2, control_group="nevertreated", base_period="universal",
             bstrap=TRUE, biters=2000, clustervars="county_id", cband=FALSE)
a2 <- aggte(m2, type="simple", na.rm=TRUE)
cat("ATT (2011+2016 treated county-years only):", round(a2$overall.att,4), " se:", round(a2$overall.se,4), "\n")
cat("  (different estimand - shorter exposures - not comparable to headline)\n")
