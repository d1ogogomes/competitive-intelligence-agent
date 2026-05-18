#!/usr/bin/env bash
# diff-snapshot.sh
# Compares the two most recent snapshots for a given competitor/source and
# emits the diff (added/removed lines) into data/diffs/<competitor>/<source>/<date>.md.
#
# A snapshot is considered "current" when its date is the latest for that
# competitor/source; the previous one is whatever came before. If only one
# snapshot exists, the script reports no baseline and exits cleanly.
#
# Usage:
#   ./diff-snapshot.sh <competitor> <source>
#
# Example:
#   ./diff-snapshot.sh cursor changelog

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <competitor> <source>" >&2
  exit 1
fi

competitor="$1"
source="$2"

script_dir=$(cd "$(dirname "$0")" && pwd)
workspace_dir=$(cd "$script_dir/.." && pwd)
snapshot_dir="$workspace_dir/data/snapshots/$competitor/$source"
diff_dir="$workspace_dir/data/diffs/$competitor/$source"

if [[ ! -d "$snapshot_dir" ]]; then
  echo "[diff-snapshot] no snapshot directory at $snapshot_dir" >&2
  exit 1
fi

# Sort snapshot files lexicographically; YYYY-MM-DD names sort by date.
# Avoid bash 4 mapfile because macOS still ships /bin/bash 3.x and shebangs
# that resolve via env can land on either; the read loop works everywhere.
snaps=()
while IFS= read -r line; do
  snaps+=("$line")
done < <(find "$snapshot_dir" -maxdepth 1 -type f -name "*.md" | sort)

if [[ ${#snaps[@]} -lt 2 ]]; then
  echo "[diff-snapshot] $competitor/$source has only ${#snaps[@]} snapshot(s); need 2 to diff"
  exit 0
fi

prev="${snaps[$((${#snaps[@]} - 2))]}"
curr="${snaps[$((${#snaps[@]} - 1))]}"
prev_date=$(basename "$prev" .md)
curr_date=$(basename "$curr" .md)

mkdir -p "$diff_dir"
out_file="$diff_dir/$curr_date.md"

# Use git diff --no-index for a colour-free, well-structured unified diff.
# It returns 1 when there are changes, which is fine — we only treat exit codes
# >1 as failures.
diff_text=$(git diff --no-index --unified=0 --no-color "$prev" "$curr" 2>/dev/null || true)

# Extract only added/removed content lines (drop diff headers and hunks).
added=$(printf '%s\n' "$diff_text" | grep -E '^\+[^+]' | sed 's/^+//' || true)
removed=$(printf '%s\n' "$diff_text" | grep -E '^-[^-]' | sed 's/^-//' || true)

{
  echo "# Diff — $competitor / $source"
  echo
  echo "Comparing $prev_date → $curr_date"
  echo
  echo "## Added"
  echo
  if [[ -n "$added" ]]; then
    printf '%s\n' "$added" | sed 's/^/+ /'
  else
    echo "(no additions)"
  fi
  echo
  echo "## Removed"
  echo
  if [[ -n "$removed" ]]; then
    printf '%s\n' "$removed" | sed 's/^/- /'
  else
    echo "(no removals)"
  fi
} > "$out_file"

added_count=$(printf '%s\n' "$added" | grep -c '^.' || true)
removed_count=$(printf '%s\n' "$removed" | grep -c '^.' || true)
echo "[diff-snapshot] $competitor/$source: +$added_count -$removed_count -> $out_file"
