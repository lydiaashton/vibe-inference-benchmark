# Reference analyses on the exact task datasets (layer 2 of the answer key).
# Run from repo root: Rscript build/reference.R
# Writes answer_key/<T>/reference.json.
.libPaths(c("env/Rlib", .libPaths()))
suppressPackageStartupMessages({
  library(jsonlite); library(fixest); library(did);
  library(ivreg); library(sandwich); library(lmtest); library(estimatr); library(data.table)
})
set.seed(20261026)
out <- function(task, obj) writeLines(toJSON(obj, auto_unbox = TRUE, digits = 6, pretty = TRUE),
                                      file.path("answer_key", task, "reference.json"))

# ---- T1: staggered DiD
d <- read.csv("tasks/T1_staggered_did/data.csv")
d$gname <- ifelse(is.na(d$adoption_year), 0, d$adoption_year)
cs <- att_gt("new_biz_per_10k", tname = "year", idname = "county_id", gname = "gname", data = d,
             control_group = "nevertreated", bstrap = TRUE, cband = FALSE, biters = 999)
cs_s <- aggte(cs, type = "simple")
cs_ny <- aggte(att_gt("new_biz_per_10k", tname = "year", idname = "county_id", gname = "gname", data = d,
                      control_group = "notyettreated", bstrap = TRUE, biters = 999), type = "simple")
d$cohort <- ifelse(d$gname == 0, 10000, d$gname)
sa <- feols(new_biz_per_10k ~ sunab(cohort, year, att = TRUE) | county_id + year, d, cluster = ~county_id)
twfe <- feols(new_biz_per_10k ~ program | county_id + year, d, cluster = ~county_id)
ci <- function(est, se) c(est - 1.96 * se, est + 1.96 * se)
out("T1", list(
  method = "Callaway-Sant'Anna, never-treated controls, simple aggregation (= ATT over treated county-years), county bootstrap",
  estimate = cs_s$overall.att, se = cs_s$overall.se, ci = ci(cs_s$overall.att, cs_s$overall.se),
  robustness = list(
    cs_notyet = list(estimate = cs_ny$overall.att, ci = ci(cs_ny$overall.att, cs_ny$overall.se)),
    sun_abraham = list(estimate = unname(coef(sa)["ATT"]), ci = unname(unlist(confint(sa)["ATT", ])))),
  naive_twfe = list(estimate = unname(coef(twfe)), ci = unname(unlist(confint(twfe))))
))

# ---- T2: weak IV
d <- read.csv("tasks/T2_weak_iv/data.csv")
iv <- ivreg(log_wage ~ years_school + parent_educ + female | dist_college_miles + parent_educ + female, data = d)
ivs <- coeftest(iv, vcov = vcovHC(iv, type = "HC1"))
fs <- lm(years_school ~ dist_college_miles + parent_educ + female, d)
F_rob <- unname(coeftest(fs, vcov = vcovHC(fs, "HC1"))["dist_college_miles", "t value"]^2)
F_hom <- unname(summary(fs)$coefficients["dist_college_miles", "t value"]^2)
grid <- seq(-2, 2, by = 0.0005)
acc <- sapply(grid, function(b) {
  m <- lm(I(log_wage - b * years_school) ~ dist_college_miles + parent_educ + female, d)
  coeftest(m, vcov = vcovHC(m, "HC1"))["dist_college_miles", 4] > 0.05
})
ar <- grid[acc]
runs <- rle(acc)
ar_shape <- if (!any(acc)) "empty" else if (acc[1] || acc[length(acc)]) "unbounded (accepts grid endpoints)" else if (sum(runs$values) > 1) "disjoint" else "bounded"
ols <- lm(log_wage ~ years_school + parent_educ + female, d)
out("T2", list(
  method = "Anderson-Rubin 95% CI (HC1), single instrument; grid [-2,2] step .0005",
  estimate_2sls = unname(coef(iv)["years_school"]),
  ar_ci = c(min(ar), max(ar)), ar_shape = ar_shape, ar_includes_zero = any(abs(ar) < 1e-9) || (min(ar) <= 0 && max(ar) >= 0),
  ar_includes_truth = any(abs(ar - 0.05) < 2.5e-4),
  conventional_2sls_ci = unname(ivs["years_school", 1] + c(-1.96, 1.96) * ivs["years_school", 2]),
  first_stage_F_robust = F_rob, first_stage_F_homoskedastic = F_hom,
  naive_ols = list(estimate = unname(coef(ols)["years_school"]), ci = unname(confint(ols)["years_school", ]))
))

# ---- T3: claims follow-up. Independent rebuild of the encounter file from claim lines (data.table), then fixest.
L <- fread(cmd = "gunzip -c tasks/T3_claims_followup/claim_lines.csv.gz",
           colClasses = list(character = c("pos", "cpt_hcpcs", "revenue_code", "rendering_specialty")))
L[, service_date := as.IDate(service_date)]
pr <- fread("tasks/T3_claims_followup/practices.csv")
ed <- unique(L[(startsWith(revenue_code, "045") | cpt_hcpcs %in% as.character(99281:99285)) & service_date <= as.IDate("2025-12-31"),
               .(member_id, practice_id, service_date)], by = c("member_id", "service_date"))
pcp <- unique(L[(claim_type == "professional" & cpt_hcpcs %in% as.character(c(99202:99205, 99211:99215)) &
                 rendering_specialty %in% c("Family Medicine", "Internal Medicine")) | revenue_code == "0517",
                .(member_id, pcp_date = service_date)])
ed[, id := .I]
m <- pcp[ed, on = "member_id", allow.cartesian = TRUE, nomatch = 0]
hit <- unique(m[as.integer(pcp_date - service_date) %between% c(0L, 14L), id])
ed[, followed := as.numeric(id %in% hit)]
ed <- pr[ed, on = "practice_id"]
ed[, `:=`(post = as.integer(service_date >= as.IDate("2025-07-01")), month = month(service_date))]
did <- feols(followed ~ program * post, ed, cluster = ~practice_id)
fe <- feols(followed ~ program:post | practice_id + month, ed, cluster = ~practice_id)
out("T3", list(
  method = "R/data.table rebuild (member-day ED encounters, PCP = office E/M FM/IM or rev 0517), fixest 2x2 DiD clustered by practice",
  n_ed_encounters = nrow(ed),
  estimate = 100 * unname(coef(did)["program:post"]), ci = 100 * unname(unlist(confint(did)["program:post", ])),
  practice_month_fe = list(estimate = 100 * unname(coef(fe)["program:post"]), ci = 100 * unname(unlist(confint(fe)["program:post", ])))
))

# ---- T4: null HTE
d <- read.csv("tasks/T4_null_hte/data.csv")
ate <- lm_robust(outcome ~ treat, d)
ate_adj <- lm_robust(outcome ~ treat + age + income_k + baseline_score + tenure_months + sessions_prior_30d +
                       female + urban + first_gen + mobile_primary + region + education + employment, d)
out("T4", list(
  method = "difference in means (HC2); covariate-adjusted as robustness; heterogeneity via omnibus Wald (see dgp.json, Python)",
  estimate = unname(coef(ate)["treat"]), ci = unname(c(ate$conf.low["treat"], ate$conf.high["treat"])),
  adjusted = list(estimate = unname(coef(ate_adj)["treat"]), ci = unname(c(ate_adj$conf.low["treat"], ate_adj$conf.high["treat"])))
))
cat("reference.R done\n")
