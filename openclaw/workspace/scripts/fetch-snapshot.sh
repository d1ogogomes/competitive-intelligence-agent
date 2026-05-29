#!/usr/bin/env bash
# fetch-snapshot.sh
# Fetches a single URL using the agent-browser CLI (headless Chromium) and
# saves the rendered text to data/snapshots/<competitor>/<source>/<YYYY-MM-DD>.md.
#
# Use this for pages that don't render content with a plain HTTP fetch
# (JS-heavy SPAs like GitHub Copilot's changelog or Zed's releases page).
#
# Usage:
#   ./fetch-snapshot.sh <competitor> <source> <url> [selector]
#
# Examples:
#   ./fetch-snapshot.sh github-copilot changelog https://github.blog/changelog/label/copilot/
#   ./fetch-snapshot.sh zed releases https://zed.dev/releases main
#
# Defaults to selector "main"; pass an explicit selector when "main" yields too
# little (some pages don't have a <main> element).

set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <competitor> <source> <url> [selector]" >&2
  exit 1
fi

competitor="$1"
source="$2"
url="$3"
selector="${4:-main}"

# Some sites (e.g. github.careers) 403 the default headless user-agent.
# Send a realistic desktop Chrome UA on every fetch.
user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

today=$(date -u +%Y-%m-%d)
# Resolve repo-relative paths regardless of where this script is invoked from.
script_dir=$(cd "$(dirname "$0")" && pwd)
workspace_dir=$(cd "$script_dir/.." && pwd)
out_dir="$workspace_dir/data/snapshots/$competitor/$source"
out_file="$out_dir/$today.md"

mkdir -p "$out_dir"

echo "[fetch-snapshot] $competitor/$source <- $url"

agent-browser open "$url" --headers "{\"User-Agent\": \"$user_agent\"}" >/dev/null
agent-browser wait --load networkidle >/dev/null
content=$(agent-browser get text "$selector" 2>/dev/null || true)

# Fallback to body when the selector returned nothing useful.
if [[ -z "$content" || $(printf %s "$content" | wc -c) -lt 200 ]]; then
  echo "[fetch-snapshot] selector '$selector' too small, falling back to body"
  content=$(agent-browser get text body)
fi

# Detect anti-bot / unrendered pages (e.g. OpenAI's Cloudflare JS challenge) so
# junk never becomes "intel". When blocked, fall back to the most recent
# Wayback Machine capture (real content, just a few days stale).
if printf %s "$content" | grep -qiE "Enable JavaScript and cookies|cf_chl_opt|Verification successful|Just a moment|challenge-platform|Checking your browser"; then
  echo "[fetch-snapshot] $competitor/$source: anti-bot detetado — a tentar fallback via web.archive.org" >&2
  now_ts=$(date -u +%Y%m%d)
  enc_url=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=''))" "$url")
  wb=$(curl -sS -m 30 "https://archive.org/wayback/available?url=${enc_url}&timestamp=${now_ts}" || true)
  arc_ts=$(python3 - "$wb" <<'PY'
import json, sys
try:
    c = json.loads(sys.argv[1]).get("archived_snapshots", {}).get("closest", {})
    print(c.get("timestamp", "") if c.get("available") else "")
except Exception:
    print("")
PY
)
  if [[ -n "$arc_ts" ]]; then
    arc_url="https://web.archive.org/web/${arc_ts}id_/$url"
    echo "[fetch-snapshot] $competitor/$source: usando arquivo ${arc_ts:0:8}" >&2
    agent-browser open "$arc_url" --headers "{\"User-Agent\": \"$user_agent\"}" >/dev/null 2>&1 || true
    agent-browser wait --load networkidle >/dev/null 2>&1 || true
    content=$(agent-browser get text body 2>/dev/null || true)
    url="$url (via web.archive.org ${arc_ts:0:8})"
  fi
  if [[ -z "$content" || $(printf %s "$content" | wc -c) -lt 200 ]] || \
     printf %s "$content" | grep -qiE "Enable JavaScript and cookies|cf_chl_opt|challenge-platform"; then
    echo "[fetch-snapshot] $competitor/$source: sem fallback utilizável — captura DESCARTADA" >&2
    exit 2
  fi
fi

{
  echo "# $competitor / $source — $today"
  echo
  echo "Source: $url"
  echo
  echo "---"
  echo
  printf '%s\n' "$content"
} > "$out_file"

bytes=$(wc -c < "$out_file" | tr -d ' ')
echo "[fetch-snapshot] wrote $out_file ($bytes bytes)"
