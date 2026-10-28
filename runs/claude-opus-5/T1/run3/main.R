library(did); library(fixest)
d <- read.csv("/Users/lydiaashton/vib-bench-runs/runs/claude-opus-5/T1/run3/data.csv")
d$g <- ifelse(is.na(d$adoption_year), 0, d$adoption_year)

cat("==== 1. Static TWFE (county + year FE, cluster county) ====\n")
m1 <- feols(new_biz_per_10k ~ program | county_id + year, data=d, cluster=~county_id)
print(summary(m1))
cat("CI:", confint(m1)[1,1], confint(m1)[1,2], "\n")

cat("\n==== 2. CS: never-treated control, SIMPLE agg (ATT over treated county-years) ====\n")
set.seed(42)
cs_nev <- att_gt(yname="new_biz_per_10k", tname="year", idname="county_id", gname="g",
                 data=d, control_group="nevertreated", bstrap=TRUE, cband=FALSE, biters=5000)
print(aggte(cs_nev, type="simple", na.rm=TRUE))

cat("\n==== 3. CS: not-yet-treated control, SIMPLE agg ====\n")
set.seed(42)
cs_nyt <- att_gt(yname="new_biz_per_10k", tname="year", idname="county_id", gname="g",
                 data=d, control_group="notyettreated", bstrap=TRUE, cband=FALSE, biters=5000)
print(aggte(cs_nyt, type="simple", na.rm=TRUE))

cat("\n==== 4. CS group-time ATTs (never-treated) incl. pre-period placebos ====\n")
print(summary(cs_nev))

cat("\n==== 5. CS dynamic (event-time) agg, never-treated ====\n")
print(aggte(cs_nev, type="dynamic", na.rm=TRUE))
cat("\n==== 6. CS group agg ====\n")
print(aggte(cs_nev, type="group", na.rm=TRUE))
