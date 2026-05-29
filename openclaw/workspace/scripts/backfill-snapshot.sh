#!/usr/bin/env bash
# backfill-snapshot.sh
# Bootstraps a REAL "previous week" snapshot from the Wayback Machine so the
# diff/metrics pipeline has two real data points without waiting a week.
#
# Queries archive.org for the closest archived copy near <days_ago>, fetches the
# raw archived page (the `id_` modifier strips the Wayback toolbar), and saves it
# as data/snapshots/<lab>/<source>/<archived-date>.md — same format as
# fetch-snapshot.sh, but dated in the past so it sorts as the "previous" snapshot.
#
# Usage:
#   ./backfill-snapshot.sh <lab> <source> <url> [days_ago=30]
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <lab> <source> <url> [days_ago]" >&2
  exit 1
fi
lab="$1"; source="$2"; url="$3"; days_ago="${4:-30}"

script_dir=$(cd "$(dirname "$0")" && pwd)
workspace_dir=$(cd "$script_dir/.." && pwd)

# Target timestamp = today - days_ago (YYYYMMDD).
if date -v -1d >/dev/null 2>&1; then            # BSD/macOS date
  target=$(date -u -v -"${days_ago}"d +%Y%m%d)
else                                            # GNU date
  target=$(date -u -d "${days_ago} days ago" +%Y%m%d)
fi

api="https://archive.org/wayback/available?url=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=''))" "$url")&timestamp=$target"
json=$(curl -sS -m 30 "$api" || true)

read -r ts archived_ok < <(python3 - "$json" <<'PY'
import json, sys
try:
    d = json.loads(sys.argv[1])
    c = d.get("archived_snapshots", {}).get("closest", {})
    if c.get("available") and str(c.get("status", "")).startswith(("2", "3")):
        print(c.get("timestamp", ""), "1")
    else:
        print("", "0")
except Exception:
    print("", "0")
PY
)

if [[ "$archived_ok" != "1" || -z "$ts" ]]; then
  echo "[backfill] $lab/$source: sem cópia arquivada perto de $target — ignorado" >&2
  exit 0
fi

# Raw archived page (no Wayback chrome) via the id_ modifier.
archived_url="https://web.archive.org/web/${ts}id_/$url"
snap_date="${ts:0:4}-${ts:4:2}-${ts:6:2}"
out_dir="$workspace_dir/data/snapshots/$lab/$source"
out_file="$out_dir/$snap_date.md"
mkdir -p "$out_dir"

ua='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
echo "[backfill] $lab/$source <- archive $snap_date"
agent-browser open "$archived_url" --headers "{\"User-Agent\": \"$ua\"}" >/dev/null 2>&1 || true
agent-browser wait --load networkidle >/dev/null 2>&1 || true
content=$(agent-browser get text body 2>/dev/null || true)

if [[ -z "$content" || $(printf %s "$content" | wc -c) -lt 200 ]]; then
  echo "[backfill] $lab/$source: conteúdo arquivado vazio/curto — ignorado" >&2
  exit 0
fi

{
  echo "# $lab / $source — $snap_date (arquivo web.archive.org)"
  echo
  echo "Source: $url"
  echo "Archived: $archived_url"
  echo
  echo "---"
  echo
  printf '%s\n' "$content"
} > "$out_file"

bytes=$(wc -c < "$out_file" | tr -d ' ')
echo "[backfill] wrote $out_file ($bytes bytes)"
