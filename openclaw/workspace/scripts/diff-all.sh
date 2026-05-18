#!/usr/bin/env bash
# diff-all.sh
# Iterates over every (competitor, source) pair we have snapshots for and runs
# diff-snapshot.sh on each. Pairs with only one snapshot are skipped (the diff
# script handles that gracefully).

set -euo pipefail

script_dir=$(cd "$(dirname "$0")" && pwd)
workspace_dir=$(cd "$script_dir/.." && pwd)
diff="$script_dir/diff-snapshot.sh"
snapshots_dir="$workspace_dir/data/snapshots"

if [[ ! -d "$snapshots_dir" ]]; then
  echo "[diff-all] no snapshots dir at $snapshots_dir" >&2
  exit 1
fi

# Each pair lives at snapshots/<competitor>/<source>/.
find "$snapshots_dir" -mindepth 2 -maxdepth 2 -type d | sort | while read -r dir; do
  rel=${dir#"$snapshots_dir"/}
  competitor=${rel%%/*}
  source=${rel#*/}
  "$diff" "$competitor" "$source"
done

echo "[diff-all] done"
