# 2026-ei-aoopii-c26 
# Competitive Intelligence Agent

Trabalho da UC Aprendizagem Organizacional — Opção II (EI, 3.º ano)

## Grupo

- Diogo Gomes — 29206
- Micael Costa — 23121

## Tema

Monitorizar concorrentes no espaço dos frontier model labs e produzir um briefing semanal com o que mudou. As fontes são públicas: changelogs, pricing, blogs, jobs, docs. O agente vai buscar tudo, compara com a versão da semana passada, e escreve o relatório.

Concorrentes: OpenAI, Anthropic, Google / Gemini, xAI, Mistral AI.

## Como funciona

```
fetch-all  →  data/snapshots/{concorrente}/{fonte}/{data}.md
diff-all   →  data/diffs/{concorrente}/{fonte}/{data}.md
agente     →  reports/YYYY-WNN.md
e-mail     →  AgentMail (opcional)
```

Tudo está em `openclaw/workspace/scripts/`. O `weekly.sh` corre o pipeline completo (fetch → diff → agente → e-mail opcional) em sequência e é o entry point pensado para cron.

Todas as páginas são capturadas com o `agent-browser` (vercel-labs, Chromium headless), incluindo as SPAs com JS pesado (changelog do Copilot, releases do Zed) onde um fetch HTTP simples só apanharia o esqueleto da página. Cada fonte usa um selector CSS (`main` por defeito) com fallback para `body`.

## Stack

- **Agente:** OpenClaw (open-source, Node.js, corre local ou em VPS)
- **LLM:** OpenRouter (modelos grátis para dev local, modelos pagos/billing ativo para execução no cron)
- **Browser:** agent-browser (vercel-labs) + Chromium headless
- **E-mail:** AgentMail
- **Deploy:** DigitalOcean VPS (Ubuntu) — ver `openclaw/workspace/scripts/CRON.md`

Não treinámos nenhum modelo. O LLM é usado como ferramenta de raciocínio — o trabalho está na orquestração e no pipeline de delta detection.

## Estrutura do repo

```
.
├── docs/                    metodologia, fontes, desafios técnicos
├── openclaw/                lab isolado do OpenClaw
│   ├── config/              config do agente (openclaw.json versionado; .bak ignorados)
│   ├── workspace/
│   │   ├── AGENTS.md        regras do agente
│   │   ├── memory/          contexto persistente (concorrentes)
│   │   ├── skills/          skills versionadas (browser, humanizer, agentmail)
│   │   ├── scripts/         pipeline (fetch, diff, weekly, send-briefing, diagnose-vps)
│   │   ├── data/            snapshots + diffs (gitignored)
│   │   └── reports/         briefings semanais
│   ├── openclaw.patch.json5         patch para Linux (Micael)
│   ├── openclaw.patch.macos.json5   patch para macOS (Diogo)
│   └── Makefile             setup, smoke, sync-config
├── agent/                   experiência inicial com ZeroClaw (descontinuada)
└── README.md
```

## Como correr

Pré-requisitos: Node 22+, npm, jq.

```sh
# 1. instalar OpenClaw e agent-browser globalmente (uma vez)
npm install -g openclaw@latest agent-browser
agent-browser install

# 2. config do lab
cd openclaw
cp .env.example .env
# editar .env e meter OPENROUTER_API_KEY (https://openrouter.ai/keys)

make setup-full        # onboard + patch + auth
make smoke             # confirma que o agente fala com o LLM

# 3. correr o pipeline manualmente
./workspace/scripts/weekly.sh
```

O Makefile escolhe o patch certo automaticamente (macOS vs Linux) por `uname -s`. Os briefings ficam em `openclaw/workspace/reports/`.

Para automatizar semanalmente, ver `openclaw/workspace/scripts/CRON.md`.

## Estado actual

Pipeline end-to-end validado e em produção num VPS da DigitalOcean. O briefing é gerado de forma totalmente autónoma todas as segundas-feiras às 09:00 e enviado para a lista de distribuição via AgentMail. Para resolver problemas em produção ou validar a saúde do ambiente (como bibliotecas do Chromium, RAM, ou chaves de API), corre o script de diagnóstico: `bash workspace/scripts/diagnose-vps.sh`.

Entrega final: 14 de junho de 2026.
