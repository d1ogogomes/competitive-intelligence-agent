#!/usr/bin/env bash
# send-briefing.sh
# Sends the latest weekly briefing via the AgentMail API.
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

basename=$(basename "$briefing" .md)
subject="Competitive Intelligence — ${basename}"
body=$(cat "$briefing")

# AgentMail expects JSON; jq builds it safely (escaping newlines/quotes).
payload=$(jq -n \
  --arg subject "$subject" \
  --arg text "$body" \
  --arg recipients "$BRIEFING_RECIPIENTS" \
  '{
    to: ($recipients | split(",") | map(. | gsub("^\\s+|\\s+$"; ""))),
    subject: $subject,
    text: $text
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
