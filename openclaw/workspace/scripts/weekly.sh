#!/usr/bin/env bash
# weekly.sh
# AI Model & Provider Radar weekly pipeline.
# Captures official provider snapshots, computes deterministic model/provider scores,
# writes the executive dashboard, QA-checks it, then sends it.

set -euo pipefail

skip_qa=false
skip_fetch=false
for arg in "$@"; do
  case "$arg" in
    --skip-qa) skip_qa=true ;;
    --skip-fetch) skip_fetch=true ;;
  esac
done

script_dir=$(cd "$(dirname "$0")" && pwd)
workspace_dir=$(cd "$script_dir/.." && pwd)
openclaw_dir="$workspace_dir"

if [[ -f "$openclaw_dir/.env" ]]; then
  set -a
  # shellcheck disable=SC1090,SC1091
  . "$openclaw_dir/.env"
  set +a
fi

if [[ "${INTELAGENT_USE_LLM_REPORT:-false}" == "true" && -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "[weekly] OPENROUTER_API_KEY missing; cannot run agent." >&2
  exit 1
fi

export OPENCLAW_STATE_DIR="$openclaw_dir/state"
export OPENCLAW_CONFIG_PATH="$openclaw_dir/config/openclaw.json"

year=$(date -u +%G)
week=$(date -u +%V)
week_id="${year}-W${week}"
session_id="model-radar-${week_id}"
report_path="$workspace_dir/reports/${week_id}.md"
plan_path="$workspace_dir/docs/AI_MODEL_PROVIDER_RADAR_PLAN.md"

echo "[weekly] $week_id AI Model & Provider Radar starting"

if [[ "$skip_fetch" == "true" ]]; then
  echo "[weekly] --skip-fetch: reusing existing snapshots/diffs/pricing"
else
  "$script_dir/fetch-all.sh"
  "$script_dir/diff-all.sh"
  python3 "$script_dir/compute-metrics.py" "$week_id" "$workspace_dir/data/snapshots" || \
    echo "[weekly] compute-metrics failed (possibly baseline without comparison)" >&2
  python3 "$script_dir/extract-pricing.py" "$week_id" "$workspace_dir/data/snapshots" || \
    echo "[weekly] extract-pricing failed" >&2
fi

# Precompute deterministic model scores before the report is written. The visible
# intelligence section is rendered from Artificial Analysis Intelligence Index.
python3 "$script_dir/compute-model-radar.py" "$week_id" "$report_path" || \
  echo "[weekly] compute-model-radar pre-pass failed" >&2

prompt=$(cat <<EOF
És um analista executivo de IA. Tens de gerar o email semanal "AI Model & Provider Radar" em português europeu, curto, factual e orientado a decisão.

Lê obrigatoriamente estes ficheiros locais antes de escrever:
- ${plan_path}
- memory/competitors.md
- data/model-radar.csv
- data/pricing.csv, se existir
- data/diffs/*/*/, para mudanças semanais verificadas

Objetivo principal: responder "que modelo usar, testar, acompanhar ou evitar, e porquê?". O foco NÃO é quem foi mais ativo.

Guarda o output com a tool 'write' em reports/${week_id}.md.

Estrutura obrigatória, por esta ordem exata:
# AI Model & Provider Radar Semana ${week_id}
## 1. Mudanças críticas da semana
## 2. Decisão recomendada
## 3. Top picks por cenário
## 4. Ranking de modelos
## 5. Comparador preço / contexto / modalidades
## 6. Gráficos visuais
## 7. Riscos e depreciações
## 8. Fontes e metodologia

Regras obrigatórias:
- O briefing deve parecer um dashboard executivo visual, não um relatório longo.
- Máximo 3 mudanças críticas, 4 cards de decisão e frases curtas.
- Usar Nível de inteligência com Artificial Analysis Intelligence Index para a parte de inteligência.
- Não incluir um segundo ranking de produção.
- Não incluir ranking antigo com score interno no corpo principal.
- Modelos PREVIEW só podem aparecer como testar/acompanhar; nunca como recomendação de produção.
- Modelos DEPRECATED ou REMOVED devem ir para rever/evitar.
- Usar gráficos visuais para Nível de inteligência, preço output e custo vs capacidade.
- Substituir tabelas largas por cards compactos.
- Separar riscos reais de governança.
- Não incluir notas internas, resumo de alterações ou bastidores do processo.
- Acrescentar apenas uma secção chamada Conclusão antes das fontes.
- Não uses Activity Score como ranking central.
- Mantém separados Intelligence Index, Provider Score e Movement Score.
- Cada recomendação/top pick inclui apenas modelo, provider, uma métrica principal e estado.
- Nunca digas "melhor modelo" sem dizer melhor para quê, com base em que dados e com que confiança.
- Mudanças críticas no topo: apenas novos modelos, preço, API, contexto/modalidades, deprecated/removed, privacidade/enterprise ou incidente/status relevante. Se não houver prova nos diffs/fontes oficiais, escreve "sem alteração crítica verificada".
- Usa fontes oficiais dos providers e benchmarks independentes listados no plano. Não uses caminhos locais como fonte pública no email.
- Máximo 2-3 gráficos no corpo principal; usa gráficos ASCII/tabelas compatíveis com email em Markdown. Não mostres evolução histórica se houver menos de 3 semanas comparáveis; nesse caso escreve a frase indicada no plano.
- Inclui badges textuais quando aplicável: STABLE, PREVIEW, LOW COST, HIGH CONTEXT, MULTIMODAL, ENTERPRISE, DEPRECATED, WATCH.
- Português europeu, frases curtas, zero marketing, não narres o teu processo.
EOF
)

agent_ok=false
if [[ "${INTELAGENT_USE_LLM_REPORT:-false}" == "true" ]]; then
  run_marker=$(mktemp)
  for attempt in 1; do
    echo "[weekly] agente (tentativa $attempt/1)..."
    openclaw agent --local --thinking low --timeout 120 \
      --agent main --session-id "${session_id}-${attempt}" --message "$prompt" || true
    if [[ -f "$report_path" && "$report_path" -nt "$run_marker" ]]; then
      agent_ok=true
      break
    fi
    echo "[weekly] tentativa $attempt não gerou briefing novo; fallback será usado." >&2
  done
  rm -f "$run_marker"
else
  echo "[weekly] INTELAGENT_USE_LLM_REPORT=false; using deterministic dashboard generator"
fi

if [[ "$agent_ok" != "true" ]]; then
  python3 "$script_dir/generate-radar-report.py" "$week_id" "$report_path"
fi

python3 "$script_dir/compute-model-radar.py" "$week_id" "$report_path" || \
  echo "[weekly] compute-model-radar post-pass failed" >&2

echo "[weekly] $week_id done -> reports/${week_id}.md"

if [[ "$skip_qa" == "true" ]]; then
  echo "[weekly] QA Guardrail SKIPPED via --skip-qa flag"
else
  echo "[weekly] Running QA Guardrail..."
  python3 "$script_dir/qa-check.py" "$report_path" "$workspace_dir/data/model-radar.csv"
fi

if [[ -n "${AGENTMAIL_API_KEY:-}" && -n "${AGENTMAIL_INBOX_ID:-}" && -n "${BRIEFING_RECIPIENTS:-}" ]]; then
  "$script_dir/send-briefing.sh" "$report_path" || \
    echo "[weekly] email delivery failed (briefing was generated, just not sent)" >&2
else
  echo "[weekly] AgentMail env vars not set, skipping email delivery"
fi
