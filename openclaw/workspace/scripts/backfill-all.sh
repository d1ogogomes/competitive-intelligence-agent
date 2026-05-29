#!/usr/bin/env bash
# backfill-all.sh
# Runs backfill-snapshot.sh for every (lab, source, url) defined in fetch-all.sh,
# so the diff/metrics pipeline gets a real "previous week" from the Wayback
# Machine. Single source of truth: it parses the run_fetch lines of fetch-all.sh.
#
# Usage:
#   ./backfill-all.sh [days_ago=30]
set -uo pipefail

script_dir=$(cd "$(dirname "$0")" && pwd)
days_ago="${1:-30}"
backfill="$script_dir/backfill-snapshot.sh"
fetch_all="$script_dir/fetch-all.sh"

failures=0
while read -r _ lab source url _rest; do
  [[ -z "${lab:-}" ]] && continue
  url="${url%\"}"; url="${url#\"}"   # strip surrounding quotes
  if ! "$backfill" "$lab" "$source" "$url" "$days_ago"; then
    echo "[backfill-all] FAILED $lab/$source" >&2
    failures=$((failures + 1))
  fi
done < <(grep -E '^run_fetch ' "$fetch_all")

echo "[backfill-all] done (${failures} failure(s))"
