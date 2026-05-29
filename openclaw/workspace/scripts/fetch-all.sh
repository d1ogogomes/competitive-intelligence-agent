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

# Frontier model labs. 4 sources each: models, pricing, blog (news), jobs.
# Competitor set switched 2026-05-29 (was coding assistants). See memory/competitors.md.

run_fetch openai models "https://platform.openai.com/docs/models"
run_fetch openai pricing "https://openai.com/api/pricing/"
run_fetch openai blog "https://openai.com/news/"
run_fetch openai jobs "https://openai.com/careers/search/"
run_fetch openai changelog "https://platform.openai.com/docs/changelog"

run_fetch anthropic models "https://docs.anthropic.com/en/docs/about-claude/models"
run_fetch anthropic pricing "https://www.anthropic.com/pricing"
run_fetch anthropic blog "https://www.anthropic.com/news"
run_fetch anthropic jobs "https://www.anthropic.com/careers"
run_fetch anthropic changelog "https://docs.anthropic.com/en/release-notes/whats-new"

run_fetch google models "https://ai.google.dev/gemini-api/docs/models"
run_fetch google pricing "https://ai.google.dev/pricing"
run_fetch google blog "https://blog.google/technology/ai/"
run_fetch google jobs "https://deepmind.google/about/careers/"
run_fetch google changelog "https://ai.google.dev/gemini-api/docs/release-notes"

run_fetch xai models "https://docs.x.ai/docs/models"
run_fetch xai pricing "https://docs.x.ai/docs/models"
run_fetch xai blog "https://x.ai/news"
run_fetch xai jobs "https://x.ai/careers"
run_fetch xai changelog "https://docs.x.ai/docs"

run_fetch mistral models "https://docs.mistral.ai/getting-started/models/models_overview/"
run_fetch mistral pricing "https://mistral.ai/pricing"
run_fetch mistral blog "https://mistral.ai/news"
run_fetch mistral jobs "https://mistral.ai/careers"
run_fetch mistral changelog "https://docs.mistral.ai/changelog/"

if [[ "$failures" -gt 0 ]]; then
  echo "[fetch-all] done with $failures failure(s)" >&2
else
  echo "[fetch-all] done"
fi
