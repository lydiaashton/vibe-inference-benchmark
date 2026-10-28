library(did); library(fixest)
d <- read.csv("/Users/lydiaashton/vib-bench-runs/runs/claude-opus-5/T1/run3/data.csv")
d$g <- ifelse(is.na(d$adoption_year), 0, d$adoption_year)
sink("spec3.txt")

cat("=== Exposure-weighted mean event time among treated county-years ===\n")
tr <- subset(d, program==1); tr$e <- tr$year - tr$g
cat("mean e =", mean(tr$e), "\n"); print(table(tr$e))

cat("\n=== Differential linear PRE-trend vs never-treated, by cohort ===\n")
for (gg in c(2011,2016)) {
  sub <- subset(d, (g==gg | g==0) & year < gg)
  sub$trt <- as.integer(sub$g==gg)
  m <- feols(new_biz_per_10k ~ trt:year | county_id + year, data=sub, cluster=~county_id)
  cat("cohort", gg, " npre =", length(unique(sub$year)), "\n")
  print(summary(m)); print(confint(m))
}
cat("\n--- pooled (2011+2016 cohorts, own pre-periods, common delta) ---\n")
sub <- subset(d, g!=2006 & (year < g | g==0))
sub$trt <- as.integer(sub$g!=0)
mp <- feols(new_biz_per_10k ~ trt:year | county_id + year, data=sub, cluster=~county_id)
print(summary(mp)); print(confint(mp))

cat("\n=== In-time PLACEBO: pretend 2016 cohort adopted in 2011, data<2016 only ===\n")
pl <- subset(d, (g==2016 | g==0) & year < 2016)
pl$gp <- ifelse(pl$g==2016, 2011, 0)
set.seed(1); csp <- att_gt("new_biz_per_10k","year","county_id","gp",data=pl,control_group="nevertreated",biters=2000)
print(aggte(csp, type="simple", na.rm=TRUE))

cat("\n=== In-time PLACEBO: pretend 2011 cohort adopted in 2008, data<2011 only ===\n")
pl2 <- subset(d, (g==2011 | g==0) & year < 2011)
pl2$gp <- ifelse(pl2$g==2011, 2008, 0)
set.seed(1); csp2 <- att_gt("new_biz_per_10k","year","county_id","gp",data=pl2,control_group="nevertreated",biters=2000)
print(aggte(csp2, type="simple", na.rm=TRUE))

cat("\n=== Cross-cohort consistency: ATT by event time within e=0..4 (common window) ===\n")
set.seed(1); cs <- att_gt("new_biz_per_10k","year","county_id","g",data=d,control_group="nevertreated",biters=2000)
res <- data.frame(g=cs$group, t=cs$t, att=cs$att, se=cs$se)
res$e <- res$t - res$g
print(subset(res, e>=0 & e<=4)[,c("g","e","att","se")], row.names=FALSE)
cat("\n--- CS restricted to e=0..4 only (balanced event window), simple-style ---\n")
print(aggte(cs, type="dynamic", min_e=0, max_e=4, balance_e=4, na.rm=TRUE))

cat("\n=== Sensitivity: linear-trend-adjusted ATT (treated-county-year weights) ===\n")
# weights = count of treated county-years per (g,t)
ncty <- c("2006"=146,"2011"=71,"2016"=57)
post <- subset(res, e>=0)
post$w <- ncty[as.character(post$g)]
att_simple <- sum(post$att*post$w)/sum(post$w)
cat("replicated simple ATT =", round(att_simple,4), "\n")
for (delta in c(0, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.1963)) {
  adj <- sum((post$att - delta*(post$e+1))*post$w)/sum(post$w)
  cat(sprintf("  delta=%.3f per yr -> trend-adjusted ATT = %.3f\n", delta, adj))
}
sink()
