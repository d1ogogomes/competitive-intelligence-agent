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

skip_qa=false
skip_fetch=false
for arg in "$@"; do
  case "$arg" in
    --skip-qa) skip_qa=true ;;
    --skip-fetch) skip_fetch=true ;;  # reuse existing snapshots/diffs/metrics (no re-scrape)
  esac
done

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

if [[ "$skip_fetch" == "true" ]]; then
  echo "[weekly] --skip-fetch: a reutilizar snapshots/diffs/métricas existentes"
else
  "$script_dir/fetch-all.sh"
  "$script_dir/diff-all.sh"
  # Deterministic scoring from the snapshots (Δ price, new models, blog, jobs) ->
  # data/metrics.csv + data/ranks.csv. The agent writes the qualitative analysis;
  # the numbers come from here, not from the LLM.
  python3 "$script_dir/compute-metrics.py" "$week_id" "$workspace_dir/data/snapshots" || \
    echo "[weekly] compute-metrics falhou (baseline sem comparação?)" >&2
  python3 "$script_dir/extract-pricing.py" "$week_id" "$workspace_dir/data/snapshots" || \
    echo "[weekly] extract-pricing falhou" >&2
fi

# Compose a deterministic prompt for the agent. Keep instructions explicit
# because free models follow tool semantics imperfectly.
prompt=$(cat <<EOF
És um analista de competitive intelligence sobre os frontier model labs:
OpenAI, Anthropic, Google / Gemini, xAI e Mistral AI.

Lê o ficheiro 'memory/competitors.md' para saberes as URLs públicas oficiais de cada concorrente/fonte (ex: o pricing da Anthropic é https://www.anthropic.com/pricing).

Lê todos os diffs em data/diffs/*/*/. Cada um descreve o que foi adicionado
e removido entre os dois snapshots mais recentes de um lab. Ignora linhas de
header repetidas (menus, FILTERS, COPY RSS FEED URL, etc.) e foca-te nas
mudanças reais (novos modelos, alterações de pricing, features de API,
deprecations, contratações que revelem direção).

Se uma fonte ainda só tiver um snapshot e portanto não houver diff, trata essa
execução como baseline inicial: diz isso explicitamente e não apresentes sinais
estáticos como se fossem mudanças verificadas.

Usa a tool 'write' (NÃO file_write) para guardar um briefing em
reports/${week_id}.md, seguindo EXATAMENTE esta estrutura:

  # Briefing Semanal — Semana ${week_id}

  ## Resumo
  3-5 bullets do mais importante da semana, com números concretos quando existirem.

  ## OpenAI
  ### O que mudou
  - <facto verificável e específico> — Fonte: <url_publica_oficial> (<data>)
  - <outro facto> — Fonte: <url_publica_oficial> (<data>)
  ### Porque importa
  <2-3 frases: implicações competitivas, não repetir o facto>
  ### O que fazer
  - <ação concreta ou sinal a vigiar para a próxima semana>

  ## Anthropic
  (mesma estrutura: O que mudou / Porque importa / O que fazer)

  ## Google / Gemini
  (mesma estrutura)

  ## xAI
  (mesma estrutura)

  ## Mistral AI
  (mesma estrutura)

  ## Sinais cruzados
  Padrões que mais de um lab fez ao mesmo tempo (ex: guerra de preços, ciclos de release alinhados).

  ## Fontes
  Lista de URLs consultados com data.

REGRAS DE QUALIDADE (isto é um produto pago — rigor acima de tudo):
- CADA bullet em "O que mudou" TEM de terminar com a URL pública oficial do concorrente extraída de 'memory/competitors.md'. Exemplo: "— Fonte: https://www.anthropic.com/pricing (2026-05-29)".
- **PROIBIDO**: Nunca uses caminhos de ficheiros locais (ex: 'data/diffs/...' ou 'reports/...') como fonte. A fonte deve ser sempre a URL web pública oficial.
- Só afirmas o que está REALMENTE nos diffs. Nada de inventar números, modelos ou preços. Se não há prova, não existe.
- "Porque importa" é análise (o "e depois?"), não repetição do facto.
- "O que fazer" é acionável: o que o leitor deve vigiar ou decidir.
- Se um lab não mudou, escreve só "Sem alterações relevantes nesta semana." em "O que mudou" e deixa as outras secções curtas.
- Português, factual, zero marketing. Não narres o teu processo ("criei", "corri").

NOTA: o score/ranking de cada lab é calculado por uma ferramenta a partir dos snapshots (Δ de preços, modelos novos, etc.) — tu NÃO escreves scores.
EOF
)

# The Gemini free tier returns 429/503 under load; retry with backoff before giving up.
# IMPORTANT: `openclaw agent` exits 0 even when the run errors (isError=true) and
# never writes the report. So we cannot trust its exit code. Instead we verify the
# report file was actually (re)written during THIS run by comparing against a marker
# created before the agent starts. This also prevents shipping a stale report that
# happens to already exist on disk (e.g. carried over from a previous run).
report_path="$workspace_dir/reports/${week_id}.md"
run_marker=$(mktemp)
agent_ok=false
for attempt in 1 2 3; do
  echo "[weekly] agente (tentativa $attempt/3)..."
  openclaw agent --local --thinking low --timeout 300 \
    --agent main --session-id "${session_id}-${attempt}" --message "$prompt" || true
  if [[ -f "$report_path" && "$report_path" -nt "$run_marker" ]]; then
    agent_ok=true
    break
  fi
  echo "[weekly] tentativa $attempt não gerou briefing novo (provável 429/quota); backoff..." >&2
  sleep $((attempt * 60))  # 60s/120s: deixa o limite por-minuto do free tier recuperar
done
rm -f "$run_marker"
if [[ "$agent_ok" != "true" ]]; then
  echo "[weekly] ERRO: agente não produziu um briefing novo em 3 tentativas (provável quota/429). Sem envio." >&2
  exit 1
fi

echo "[weekly] $week_id done -> workspace/reports/${week_id}.md"

# Run Automated QA Guardrail
if [[ "$skip_qa" == "true" ]]; then
  echo "[weekly] QA Guardrail SKIPPED via --skip-qa flag"
else
  echo "[weekly] Running Automated QA Guardrail..."
  if ! python3 "$script_dir/qa-check.py" "$workspace_dir/reports/${week_id}.md" "$workspace_dir/data/metrics.csv"; then
    echo "[weekly] ERROR: QA Guardrail rejected the generated briefing!" >&2
    echo "[weekly] Email delivery BLOCKED to preserve subscription quality." >&2
    exit 1
  fi
fi

# Optional email delivery via AgentMail. Skips silently if not configured.
if [[ -n "${AGENTMAIL_API_KEY:-}" && -n "${AGENTMAIL_INBOX_ID:-}" && -n "${BRIEFING_RECIPIENTS:-}" ]]; then
  "$script_dir/send-briefing.sh" "$workspace_dir/reports/${week_id}.md" || \
    echo "[weekly] email delivery failed (briefing was generated, just not sent)" >&2
else
  echo "[weekly] AgentMail env vars not set, skipping email delivery"
fi
