#!/usr/bin/env bash
# send-briefing.sh
# Sends the latest weekly briefing via the AgentMail API.
# Sends both plain text (the Markdown) and a rich HTML body with a ranking
# table + weekly rank-evolution chart, so the email is readable and visual.
#
# Pipeline:
#   1. compute-metrics.py     deterministic metrics from snapshots -> data/metrics.csv + ranks.csv
#   2. render-briefing-html.py  build the HTML body (markdown + ranks table + QuickChart)
#   3. curl                   POST to AgentMail
#
# Required env (loaded from openclaw/.env):
#   AGENTMAIL_API_KEY      starts with "am_..." (https://agentmail.to dashboard)
#   AGENTMAIL_INBOX_ID     full inbox address, e.g. "intelagent@agentmail.to"
#   BRIEFING_RECIPIENTS    comma-separated list of recipient emails
#
# Usage:
#   ./send-briefing.sh                    # sends the most recent reports/*.md
#   ./send-briefing.sh reports/2026-W20.md  # sends a specific file

set -euo pipefail

script_dir=$(cd "$(dirname "$0")" && pwd)
workspace_dir=$(cd "$script_dir/.." && pwd)
openclaw_dir=$(cd "$workspace_dir/.." && pwd)

if [[ -f "$openclaw_dir/.env" ]]; then
  set -a
  # shellcheck disable=SC1090,SC1091
  . "$openclaw_dir/.env"
  set +a
fi

: "${AGENTMAIL_API_KEY:?AGENTMAIL_API_KEY missing in openclaw/.env}"
: "${AGENTMAIL_INBOX_ID:?AGENTMAIL_INBOX_ID missing in openclaw/.env (e.g. intelagent@agentmail.to)}"
: "${BRIEFING_RECIPIENTS:?BRIEFING_RECIPIENTS missing in openclaw/.env (comma-separated emails)}"

# Pick the latest briefing if none was given.
if [[ $# -ge 1 ]]; then
  briefing="$1"
else
  briefing=$(ls -1t "$workspace_dir/reports/"*.md 2>/dev/null | head -n1 || true)
fi

if [[ -z "$briefing" || ! -f "$briefing" ]]; then
  echo "[send-briefing] no briefing found in workspace/reports/" >&2
  exit 1
fi

ranks_csv="$workspace_dir/data/ranks.csv"
week_id=$(basename "$briefing" .md | grep -oE '[0-9]{4}-W[0-9]{1,2}' || true)

# 1. Compute deterministic metrics from the snapshots -> data/metrics.csv + ranks.csv.
#    Score/ranking come from real signals (Δ price, new models, ...), not the LLM.
if ! python3 "$script_dir/compute-metrics.py" "${week_id:-}" "$workspace_dir/data/snapshots"; then
  echo "[send-briefing] WARN: compute-metrics falhou (sem snapshots para comparar?)" >&2
fi

if ! python3 "$script_dir/extract-pricing.py" "${week_id:-}" "$workspace_dir/data/snapshots"; then
  echo "[send-briefing] WARN: extract-pricing falhou" >&2
fi

basename=$(basename "$briefing" .md)
subject="Competitive Intelligence — ${basename}"
body=$(cat "$briefing")

# 2. Build the rich HTML body.
html=$(python3 "$script_dir/render-briefing-html.py" "$briefing" "$ranks_csv")

# 3. AgentMail expects JSON; jq builds it safely (escaping newlines/quotes).
payload=$(jq -n \
  --arg subject "$subject" \
  --arg text "$body" \
  --arg html "$html" \
  --arg recipients "$BRIEFING_RECIPIENTS" \
  '{
    to: ($recipients | split(",") | map(. | gsub("^\\s+|\\s+$"; ""))),
    subject: $subject,
    text: $text,
    html: $html
  }')

echo "[send-briefing] $briefing -> $BRIEFING_RECIPIENTS"

response=$(curl -sS -X POST \
  "https://api.agentmail.to/v0/inboxes/${AGENTMAIL_INBOX_ID}/messages/send" \
  -H "Authorization: Bearer ${AGENTMAIL_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "$payload" \
  -w "\nHTTP_STATUS:%{http_code}")

status=${response##*HTTP_STATUS:}
body_resp=${response%HTTP_STATUS:*}

if [[ "$status" =~ ^2 ]]; then
  echo "[send-briefing] sent (status $status)"
  echo "$body_resp"
else
  echo "[send-briefing] FAILED (status $status)" >&2
  echo "$body_resp" >&2
  exit 1
fi
