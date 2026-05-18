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

today=$(date -u +%Y-%m-%d)
# Resolve repo-relative paths regardless of where this script is invoked from.
script_dir=$(cd "$(dirname "$0")" && pwd)
workspace_dir=$(cd "$script_dir/.." && pwd)
out_dir="$workspace_dir/data/snapshots/$competitor/$source"
out_file="$out_dir/$today.md"

mkdir -p "$out_dir"

echo "[fetch-snapshot] $competitor/$source <- $url"

agent-browser open "$url" >/dev/null
agent-browser wait --load networkidle >/dev/null
content=$(agent-browser get text "$selector" 2>/dev/null || true)

# Fallback to body when the selector returned nothing useful.
if [[ -z "$content" || $(printf %s "$content" | wc -c) -lt 200 ]]; then
  echo "[fetch-snapshot] selector '$selector' too small, falling back to body"
  content=$(agent-browser get text body)
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
