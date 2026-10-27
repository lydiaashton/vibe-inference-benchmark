#!/usr/bin/env bash
# LOCK (run only after Lydia approves B1-B5). Writes MANIFEST.sha256 over every task file,
# answer key, grader, runner and build script, commits, and prints the hashes for the README.
# After this, tasks/answer_key/grader are frozen; log any change in DEVIATIONS.md instead.
set -euo pipefail
cd "$(dirname "$0")"
[[ -z "$(ls runs 2>/dev/null)" ]] || { echo "runs/ is not empty; lock must precede runs." >&2; exit 1; }
find tasks answer_key grader runner build env/requirements.txt lock.sh -type f ! -name '.DS_Store' | LC_ALL=C sort | xargs shasum -a 256 > MANIFEST.sha256
MANIFEST_HASH=$(shasum -a 256 MANIFEST.sha256 | cut -d' ' -f1)
git add -A
git commit -q -m "LOCK v0: tasks, answer key, grader, runner (manifest sha256 ${MANIFEST_HASH})"
echo "lock commit: $(git rev-parse HEAD)"
echo "manifest sha256: ${MANIFEST_HASH}"
echo "Verify later with: shasum -a 256 -c MANIFEST.sha256"
