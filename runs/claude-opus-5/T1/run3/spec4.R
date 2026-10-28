library(did)
d <- read.csv("/Users/lydiaashton/vib-bench-runs/runs/claude-opus-5/T1/run3/data.csv")
d$g <- ifelse(is.na(d$adoption_year), 0, d$adoption_year)
sink("spec4.txt")
set.seed(1); cs <- att_gt("new_biz_per_10k","year","county_id","g",data=d,control_group="nevertreated",biters=2000)
res <- data.frame(g=cs$group,t=cs$t,att=cs$att); res$e <- res$t-res$g
ncty <- c("2006"=146,"2011"=71,"2016"=57); post <- subset(res,e>=0); post$w <- ncty[as.character(post$g)]
cat("mean (e+1) weighted =", sum((post$e+1)*post$w)/sum(post$w), "\n")
cat("\n=== full linear-trend sensitivity ===\n")
for (delta in c(0,0.027,0.069,0.1,0.2,0.3,0.5,0.75,1.0,1.1963,1.2)) {
  adj <- sum((post$att - delta*(post$e+1))*post$w)/sum(post$w)
  cat(sprintf("delta=%.4f -> ATT=%.3f\n", delta, adj))
}

cat("\n=== Nonparametric cluster (county) bootstrap of CS simple ATT, 400 reps ===\n")
ids <- unique(d$county_id); B <- 400; out <- numeric(B); set.seed(7)
for (b in 1:B) {
  s <- sample(ids, length(ids), replace=TRUE)
  db <- do.call(rbind, lapply(seq_along(s), function(i){x<-d[d$county_id==s[i],]; x$county_id<-i*100000; x}))
  r <- try({cc <- att_gt("new_biz_per_10k","year","county_id","g",data=db,control_group="nevertreated",bstrap=FALSE)
            aggte(cc,type="simple",na.rm=TRUE,bstrap=FALSE)$overall.att}, silent=TRUE)
  out[b] <- if(inherits(r,"try-error")) NA else r
}
out <- out[!is.na(out)]
cat("reps ok:", length(out), " boot SE =", sd(out), "\n")
cat("percentile CI:", quantile(out, c(.025,.975)), "\n")
sink()
