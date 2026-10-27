#!/usr/bin/env bash
# Headless runner. Usage:
#   runner/run.sh T1            # runs 1..3 for one task
#   runner/run.sh T1 1          # a single run (dry run)
#   runner/run.sh all           # all 4 tasks x 3 runs, sequentially
#   RUNS_DIR="$PWD/dryrun" runner/run.sh T2 1   # pre-lock dry run, kept out of runs/ and the grader
#
# Each run works in an ISOLATED folder outside this repo ($RUN_ROOT/<task>/run<k>), so the
# model cannot see answer_key/, build/ or any parent CLAUDE.md. Afterwards the folder is
# copied back to runs/<task>/run<k>/ (trace.jsonl, answer.json, all model-written files).
# Billing: refuses to start if ANTHROPIC_API_KEY is set, unless ALLOW_API_KEY=1 (the
# API fallback, only with Lydia's approval). On a usage-limit error it stops; no retries.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
RUN_ROOT="${RUN_ROOT:-$HOME/vib-bench-runs}"
RUNS_DIR="${RUNS_DIR:-$REPO/runs}"   # set RUNS_DIR=$REPO/dryrun for a pre-lock dry run
MODEL="${MODEL:-opus}"          # alias; the exact model string is read from the trace
MAX_TURNS="${MAX_TURNS:-60}"
TIMEOUT_MIN="${TIMEOUT_MIN:-45}"
ALLOWED_TOOLS="Read,Write,Edit,Bash,Glob,Grep"
DISALLOWED_TOOLS="WebFetch,WebSearch,Agent,Task,NotebookEdit"

if [[ -n "${ANTHROPIC_API_KEY:-}" && "${ALLOW_API_KEY:-0}" != "1" ]]; then
  echo "ANTHROPIC_API_KEY is set; this would bill the API, not the subscription. Unset it (or ALLOW_API_KEY=1 for the approved fallback)." >&2
  exit 2
fi
if [[ "${ALLOW_API_KEY:-0}" != "1" ]]; then
  claude auth status 2>/dev/null | grep -q '"authMethod": "claude.ai"' || { echo "Not logged in with a Claude subscription." >&2; exit 2; }
fi

taskdir() {  # bash 3.2 (macOS) has no associative arrays
  case "$1" in T1) echo T1_staggered_did;; T2) echo T2_weak_iv;;
    T3) echo T3_claims_followup;; T4) echo T4_null_hte;; *) echo "unknown task $1 (tasks: T1 T2 T3 T4)" >&2; exit 2;; esac
}
with_timeout() {  # macOS has no coreutils timeout; perl alarm kills the run after TIMEOUT_MIN
  perl -e 'alarm shift @ARGV; exec @ARGV or die "exec: $!"' "$(( TIMEOUT_MIN * 60 ))" "$@"
}

setup_env() {
  # Analysis environment the model gets: its own venv + copy of the R library, outside the repo.
  local env="$RUN_ROOT/.analysis-env"
  if [[ ! -x "$env/py/bin/python" ]]; then
    mkdir -p "$env"
    python3 -m venv "$env/py"
    "$env/py/bin/pip" install -q -r "$REPO/env/requirements.txt"
  fi
  if [[ ! -d "$env/Rlib/fixest" ]]; then
    mkdir -p "$env/Rlib" && cp -R "$REPO/env/Rlib/." "$env/Rlib/"
  fi
  export PATH="$env/py/bin:$PATH" R_LIBS_USER="$env/Rlib" VIRTUAL_ENV="$env/py"
}

run_one() {
  local t="$1" k="$2" src; src="$REPO/tasks/$(taskdir "$1")"
  local work="$RUN_ROOT/$(basename "$RUNS_DIR")/$t/run$k" dest="$RUNS_DIR/$t/run$k"
  if [[ -e "$dest/trace.jsonl" ]]; then echo "skip $t run$k (exists)"; return 0; fi
  rm -rf "$work"; mkdir -p "$work"
  cp "$src"/* "$work"/                       # tasks/ never contains truth files
  [[ ! -e "$work/truth.json" && ! -e "$work/dgp.json" ]] || { echo "truth file in task folder!" >&2; exit 3; }
  echo "[$(date '+%F %T')] $t run$k  model=$MODEL max_turns=$MAX_TURNS"
  local start=$(date +%s) rc=0
  ( cd "$work" && with_timeout claude -p "$(cat prompt.md)" \
      --output-format stream-json --verbose --safe-mode \
      --model "$MODEL" --max-turns "$MAX_TURNS" \
      --tools "$ALLOWED_TOOLS" --allowedTools "$ALLOWED_TOOLS" --disallowedTools "$DISALLOWED_TOOLS" \
      --strict-mcp-config --no-session-persistence < /dev/null > trace.jsonl 2> stderr.log ) || rc=$?
  local secs=$(( $(date +%s) - start ))
  mkdir -p "$dest"; cp -R "$work"/. "$dest"/
  python3 "$REPO/runner/run_meta.py" "$dest" "$rc" "$secs" "$MODEL" | tee "$dest/run_meta.json"
  if grep -qiE 'usage limit|rate.?limit|limit reached|quota' "$dest/stderr.log" "$dest/run_meta.json" 2>/dev/null; then
    echo "Usage limit hit at $t run$k. Stopping (no retries). Resume later with the same command; finished runs are skipped." >&2
    exit 4
  fi
}

setup_env
if [[ "${1:-}" == "all" ]]; then
  for t in T1 T2 T3 T4; do for k in 1 2 3; do run_one "$t" "$k"; done; done
else
  t="${1:?task}"; shift
  ks="${*:-1 2 3}"
  for k in $ks; do run_one "$t" "$k"; done
fi
