#!/usr/bin/env bash
# weekly.sh
# Single entry point for the weekly briefing pipeline.
#   1. fetch-all.sh        capture today's snapshots
#   2. diff-all.sh         compute per-pair diffs against the previous snapshot
#   3. agente OpenClaw     reads the diffs and writes reports/<YYYY>-W<NN>.md
#
# Designed to be the cron target. Run from anywhere; resolves its own paths.
#
# Required env (loaded from openclaw/.env if not already set):
#   OPENROUTER_API_KEY     so the agent can talk to the model

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

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "[weekly] OPENROUTER_API_KEY missing; cannot run agent." >&2
  exit 1
fi

export OPENCLAW_STATE_DIR="$openclaw_dir/state"
export OPENCLAW_CONFIG_PATH="$openclaw_dir/config/openclaw.json"

# ISO week number, e.g. 2026-W20.
year=$(date -u +%G)
week=$(date -u +%V)
week_id="${year}-W${week}"
session_id="weekly-${week_id}"

echo "[weekly] $week_id starting"

"$script_dir/fetch-all.sh"
"$script_dir/diff-all.sh"

# Compose a deterministic prompt for the agent. Keep instructions explicit
# because free models follow tool semantics imperfectly.
prompt=$(cat <<EOF
Lê todos os diffs em data/diffs/*/*/. Cada um descreve o que foi adicionado
e removido entre os dois snapshots mais recentes de um concorrente. Ignora
linhas de header repetidas (BACK TO BLOG, FILTERS, COPY RSS FEED URL, etc.)
e foca-te nas mudanças reais (releases, novas features, deprecations,
alterações de pricing).

Usa a tool 'write' (NÃO file_write) para guardar um briefing em
reports/${week_id}.md, seguindo a estrutura definida em AGENTS.md:

  # Briefing Semanal — Semana ${week_id}

  ## Resumo
  3-5 bullets do mais importante.

  ## <Concorrente>
  ### O que mudou
  ### Relevância

  ## Sinais cruzados
  Coisas que mais de um concorrente fez ao mesmo tempo.

  ## Fontes
  URLs + datas dos diffs.

Escreve em português, factual, sem marketing. Se um concorrente não tem
mudanças relevantes, escreve "Sem alterações relevantes nesta semana."
EOF
)

openclaw agent --local --thinking low --timeout 300 \
  --agent main \
  --session-id "$session_id" \
  --message "$prompt"

echo "[weekly] $week_id done -> workspace/reports/${week_id}.md"

# Optional email delivery via AgentMail. Skips silently if not configured.
if [[ -n "${AGENTMAIL_API_KEY:-}" && -n "${AGENTMAIL_INBOX_ID:-}" && -n "${BRIEFING_RECIPIENTS:-}" ]]; then
  "$script_dir/send-briefing.sh" "$workspace_dir/reports/${week_id}.md" || \
    echo "[weekly] email delivery failed (briefing was generated, just not sent)" >&2
else
  echo "[weekly] AgentMail env vars not set, skipping email delivery"
fi
