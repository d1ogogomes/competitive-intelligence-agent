#!/usr/bin/env bash
# send-briefing.sh
# Sends the latest weekly briefing via the AgentMail API.
# Sends both plain text and simple HTML so the email is readable in normal
# clients while preserving the Markdown file as the source of truth.
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
html=$(BRIEFING_FILE="$briefing" python3 <<'PY'
import html
import os
import re
from pathlib import Path

path = Path(os.environ["BRIEFING_FILE"])
lines = path.read_text(encoding="utf-8").splitlines()

def inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    return escaped

LOGOS = {
    "Cursor": "https://www.google.com/s2/favicons?domain=cursor.com&sz=64",
    "GitHub Copilot": "https://www.google.com/s2/favicons?domain=github.com&sz=64",
    "Claude / Anthropic": "https://www.google.com/s2/favicons?domain=anthropic.com&sz=64",
    "Windsurf": "https://www.google.com/s2/favicons?domain=windsurf.com&sz=64",
    "Zed": "https://www.google.com/s2/favicons?domain=zed.dev&sz=64",
}

def heading(text: str, level: int) -> str:
    safe = inline(text)
    logo = LOGOS.get(text)
    if level == 2 and logo:
        alt = html.escape(text)
        return (
            f'<h2 class="brand-heading">'
            f'<img src="{logo}" alt="{alt}" width="24" height="24"> '
            f'<span>{safe}</span></h2>'
        )
    return f"<h{level}>{safe}</h{level}>"

parts = ["""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { margin: 0; padding: 0; background: #f6f7f9; color: #17202a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    .wrap { max-width: 760px; margin: 0 auto; padding: 28px 18px; }
    .card { background: #ffffff; border: 1px solid #dfe3e8; border-radius: 8px; overflow: hidden; }
    .header { padding: 24px 28px; border-bottom: 1px solid #e7ebef; background: #101820; color: #ffffff; }
    h1 { margin: 0; font-size: 24px; line-height: 1.25; letter-spacing: 0; }
    .content { padding: 22px 28px 28px; }
    h2 { margin: 26px 0 10px; font-size: 17px; line-height: 1.3; border-bottom: 1px solid #e7ebef; padding-bottom: 7px; }
    h3 { margin: 18px 0 8px; font-size: 15px; line-height: 1.3; }
    .brand-heading { display: flex; align-items: center; gap: 9px; }
    .brand-heading img { display: inline-block; border-radius: 5px; vertical-align: middle; }
    p { margin: 8px 0; line-height: 1.55; }
    ul { margin: 8px 0 14px 0; padding-left: 22px; }
    li { margin: 6px 0; line-height: 1.5; }
    .meta { margin-top: 18px; color: #5d6975; font-size: 13px; }
  </style>
</head>
<body><div class="wrap"><div class="card">"""]

in_list = False
header_done = False

def close_list():
    global in_list
    if in_list:
        parts.append("</ul>")
        in_list = False

for raw in lines:
    line = raw.rstrip()
    if not line:
        close_list()
        continue
    if line.startswith("# "):
        close_list()
        if not header_done:
            parts.append(f'<div class="header"><h1>{inline(line[2:].strip())}</h1></div><div class="content">')
            header_done = True
        else:
            parts.append(f"<h1>{inline(line[2:].strip())}</h1>")
    elif line.startswith("## "):
        close_list()
        parts.append(heading(line[3:].strip(), 2))
    elif line.startswith("### "):
        close_list()
        parts.append(heading(line[4:].strip(), 3))
    elif line.startswith("- "):
        if not in_list:
            parts.append("<ul>")
            in_list = True
        parts.append(f"<li>{inline(line[2:].strip())}</li>")
    else:
        close_list()
        parts.append(f"<p>{inline(line.strip())}</p>")

close_list()
if header_done:
    parts.append('<p class="meta">Relatório gerado automaticamente a partir de snapshots públicos.</p></div>')
parts.append("</div></div></body></html>")
print("\n".join(parts))
PY
)

# AgentMail expects JSON; jq builds it safely (escaping newlines/quotes).
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
