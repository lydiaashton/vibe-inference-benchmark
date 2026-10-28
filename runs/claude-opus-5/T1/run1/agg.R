suppressMessages({library(did); library(data.table)})
x <- readRDS("/tmp/sbgrant/cs.rds")
cat("=== CS never-treated, SIMPLE aggregation (ATT over treated county-years) ===\n")
a <- aggte(x$cs_nt, type="simple", na.rm=TRUE); print(summary(a))
cat("\nestimate:", a$overall.att, " se:", a$overall.se,
    " ci:", a$overall.att-1.96*a$overall.se, a$overall.att+1.96*a$overall.se, "\n")

# verify "simple" weights == county-year weights by hand-computing weighted avg of ATT(g,t)
g <- x$cs_nt
dt <- data.table(group=g$group, t=g$t, att=g$att)
post <- dt[t>=group]
nsize <- c("2006"=146,"2011"=71,"2016"=57)
post[, w := nsize[as.character(group)]]
cat("\nhand-computed county-year-weighted mean of ATT(g,t) over treated cells:",
    round(sum(post$att*post$w)/sum(post$w),4), "\n")
cat("did::aggte(simple) :", round(a$overall.att,4), "\n")

cat("\n=== PRE-TREND tests (cohorts with >1 pre-period: 2011, 2016) ===\n")
pre <- dt[t<group & group>2006]
print(pre)
# joint Wald test on pre-period ATT(g,t) using CS influence-function vcov
idx <- which(g$t < g$group & g$group > 2006)
V <- g$V_analytical[idx, idx, drop=FALSE]
b <- g$att[idx]
W <- as.numeric(t(b) %*% solve(V) %*% b)
cat("\nJoint Wald stat:", round(W,3), " df:", length(idx),
    " p-value:", round(pchisq(W, length(idx), lower.tail=FALSE),4), "\n")
cat("max |pre ATT|:", round(max(abs(b)),3), "\n")
