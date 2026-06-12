#!/usr/bin/env bash
# fetch-all.sh
# Calls fetch-snapshot.sh for every competitor/source pair we track. Continues
# after a failed source so one broken page does not block the weekly briefing.
#
# Run from anywhere:
#   ./openclaw/workspace/scripts/fetch-all.sh

set -uo pipefail

script_dir=$(cd "$(dirname "$0")" && pwd)
fetch="$script_dir/fetch-snapshot.sh"
sources="$script_dir/sources.csv"
failures=0

run_fetch() {
  competitor="$1"
  source="$2"
  url="$3"
  selector="${4:-main}"

  if ! "$fetch" "$competitor" "$source" "$url" "$selector"; then
    echo "[fetch-all] FAILED $competitor/$source <- $url" >&2
    failures=$((failures + 1))
  fi
}

if [[ ! -f "$sources" ]]; then
  echo "[fetch-all] source catalog missing: $sources" >&2
  exit 1
fi

# The source catalog is the single source of truth. Python's CSV parser keeps
# commas/quoting correct and emits tab-separated values for the shell loop.
while IFS=$'\t' read -r group owner source url selector; do
  [[ -n "$owner" && -n "$source" && -n "$url" ]] || continue
  run_fetch "$owner" "${group}-${source}" "$url" "${selector:-main}"
done < <(python3 - "$sources" <<'PY'
import csv, sys
with open(sys.argv[1], newline="", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        if row.get("enabled") == "1":
            print("\t".join([row["group"], row["owner"], row["source"], row["url"], row.get("selector") or "main"]))
PY
)

if [[ "$failures" -gt 0 ]]; then
  echo "[fetch-all] done with $failures failure(s)" >&2
else
  echo "[fetch-all] done"
fi
