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

run_fetch cursor changelog "https://cursor.com/changelog"
run_fetch cursor docs "https://docs.cursor.com"
run_fetch cursor pricing "https://cursor.com/pricing"
run_fetch cursor blog "https://cursor.com/blog"
run_fetch cursor jobs "https://cursor.com/careers"

run_fetch github-copilot changelog "https://github.blog/changelog/label/copilot/"
run_fetch github-copilot docs "https://docs.github.com/copilot"
run_fetch github-copilot pricing "https://github.com/features/copilot/plans"
run_fetch github-copilot blog "https://github.blog/ai-and-ml/"
run_fetch github-copilot jobs "https://github.careers"

run_fetch claude models "https://docs.anthropic.com/en/docs/about-claude/models"
run_fetch claude docs "https://docs.anthropic.com"
run_fetch claude pricing "https://www.anthropic.com/pricing"
run_fetch claude blog "https://www.anthropic.com/news"
run_fetch claude jobs "https://www.anthropic.com/careers"

run_fetch windsurf changelog "https://windsurf.com/changelog"
run_fetch windsurf docs "https://docs.windsurf.com"
run_fetch windsurf pricing "https://windsurf.com/pricing"
run_fetch windsurf blog "https://windsurf.com/blog"
run_fetch windsurf jobs "https://windsurf.com/careers"

run_fetch zed releases "https://zed.dev/releases"
run_fetch zed docs "https://zed.dev/docs"
run_fetch zed pricing "https://zed.dev/pricing"
run_fetch zed blog "https://zed.dev/blog"
run_fetch zed jobs "https://zed.dev/jobs"
run_fetch zed github "https://github.com/zed-industries/zed"

if [[ "$failures" -gt 0 ]]; then
  echo "[fetch-all] done with $failures failure(s)" >&2
else
  echo "[fetch-all] done"
fi
