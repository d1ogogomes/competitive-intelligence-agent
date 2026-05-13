# OpenClaw Lab

OpenClaw isolado para o projeto da cadeira. **Não** usa `~/.openclaw` como state/config.

## Caminhos

```txt
OPENCLAW_STATE_DIR=./state
OPENCLAW_CONFIG_PATH=./config/openclaw.json
workspace=./workspace
gateway=127.0.0.1:42717
```

## Pré-requisitos

- Node.js 22+ e npm
- OpenClaw CLI instalado globalmente: `npm install -g openclaw@latest`
- Chromium / Chrome (opcional, só para skills de browser)

## Patches

Há dois patches de config. O `Makefile` escolhe automaticamente com base em `uname -s`:

| Ficheiro | Quando é usado | Paths / modelo |
|----------|----------------|----------------|
| `openclaw.patch.json5` | Linux (Micael) | `/home/micael/...`, `openai-codex/gpt-5.5`, qmd habilitado |
| `openclaw.patch.macos.json5` | macOS (Diogo) | `/Users/diogogomes/...`, OpenRouter free router, qmd desligado |

Razões da divergência:

- **Modelo:** no Mac usamos o **Free Models Router** do OpenRouter (`openrouter/openrouter/free`) porque os IDs dos modelos free mudam com frequência e quebram a config com 404. O router absorve essas mudanças.
- **qmd:** é um binário Bun que o Micael tem local e não está em `/opt/homebrew`. Quando passarmos a Docker voltamos ao qmd.
- **Chromium path:** `/usr/bin/chromium` não existe no Mac. Deixamos o OpenClaw descobrir o binário por si.

## Arranque rápido (macOS)

```sh
# 1. Instala o OpenClaw CLI (uma vez):
npm install -g openclaw@latest

# 2. Vai para esta pasta e prepara a .env:
cp .env.example .env
# (edita .env e põe OPENROUTER_API_KEY=sk-or-v1-...)

# 3. Setup + aplicação do patch + registo da API key, tudo num passo:
make setup-full

# 4. Testa:
make smoke
```

Obtém uma OpenRouter API key gratuita em: https://openrouter.ai/keys

## Comandos principais

```sh
make env              # mostra paths, OS e patch ativo
make setup-full       # onboard + sync-config + guarda API key
make sync-config      # aplica o patch correto (voltar a correr após mexer no patch)
make validate         # valida o config
make status           # status geral
make models           # modelo default atual
make auth             # lista perfis de auth
make smoke            # dispara uma query de teste ao agente
make cli              # chat TUI local
make gateway          # corre o gateway
make memory-search Q="competitor monitor"
make reset            # limpa state/ workspace/ para recomeçar do zero
```

## Config resultante

Depois de `make setup-full`, o `config/openclaw.json` fica com:

- Modelo principal: `openrouter/openrouter/free` (alias `or-free`) — é o **Free Models Router** do OpenRouter. Rota automaticamente entre os modelos gratuitos que estão operacionais e suportam tools.
- Fallbacks: `openrouter/openrouter/auto`, `openrouter/owl-alpha`
- Thinking/reasoning: `low`
- Tools: `web_search`, `web_fetch`, `browser`, `exec`, `read`, `write`, `edit`, `memory_search`, `memory_get`
- Exec approval: `off` (autonomia total dentro do workspace)
- Web search: DuckDuckGo por default; trocar para Brave se `BRAVE_API_KEY` estiver em `.env`

### Redescobrir modelos livres

Quando um modelo parar de responder, descobre o estado atual com:

```sh
set -a; . ./.env; set +a
OPENCLAW_STATE_DIR=./state OPENCLAW_CONFIG_PATH=./config/openclaw.json \
  openclaw models scan --provider openrouter --yes --no-input
```

Isso testa os free models em tempo real e diz quais suportam tools. Atualiza o patch e corre `make sync-config`.

## Workspace

O `workspace/` é onde o agente trabalha. Convenções do projeto:

```txt
workspace/
├── scripts/           # scripts de scrape, diff, report
├── data/snapshots/    # snapshots por concorrente, por data
├── reports/           # briefings semanais em Markdown
└── memory/            # notas persistentes do agente
```

Estes subdirectórios são criados on demand pelo agente ou pelos scripts; não são versionados.

## Notas de segurança

- A OpenRouter API key vive em `.env` (gitignored) e, depois do setup, em `state/agents/main/agent/auth-profiles.json` (também gitignored via `state/`).
- O gateway está a escutar apenas em `127.0.0.1`. Se puseres isto num VPS, usa Tailscale / SSH tunnel / reverse proxy com TLS.
- `state/` inclui auth tokens e caches — nunca fazer `git add state/`.
