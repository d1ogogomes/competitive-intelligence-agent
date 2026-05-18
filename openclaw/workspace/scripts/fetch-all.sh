#!/usr/bin/env bash
# fetch-all.sh
# Calls fetch-snapshot.sh for every competitor we track. Stops on first failure
# so a broken source surfaces fast; comment out the `set -e` to make it
# resilient and continue with the rest.
#
# Run from anywhere:
#   ./openclaw/workspace/scripts/fetch-all.sh

set -euo pipefail

script_dir=$(cd "$(dirname "$0")" && pwd)
fetch="$script_dir/fetch-snapshot.sh"

"$fetch" cursor          changelog  "https://cursor.com/changelog"
"$fetch" github-copilot  changelog  "https://github.blog/changelog/label/copilot/"
"$fetch" claude          docs       "https://docs.anthropic.com/en/docs/about-claude/models"
"$fetch" windsurf        changelog  "https://windsurf.com/changelog"
"$fetch" zed             releases   "https://zed.dev/releases"

echo "[fetch-all] done"
