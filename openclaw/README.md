# OpenClaw

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
- OpenClaw CLI + agent-browser globais: `npm i -g openclaw@2026.5.7 agent-browser@0.27.0`
- Chromium (necessário para o fetch dos snapshots): `npx playwright install --with-deps chromium`

## Patches

Há dois patches de config. O `Makefile` escolhe automaticamente com base em `uname -s`:

| Ficheiro | Quando é usado | Paths / modelo |
|----------|----------------|----------------|
| `openclaw.patch.json5` | Linux (Micael) | `/home/micael/...`, LM Studio local, qmd habilitado |
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
make skills           # lista skills disponíveis
make install-skill SLUG=humanizer
make update-skills
make memory-search Q="competitor monitor"
make reset            # limpa state/ workspace/ para recomeçar do zero
```

## Config resultante

Depois de `make setup-full`, o `config/openclaw.json` fica com:

- Modelo principal: `lmstudio/google/gemma-4-e4b` (alias `gemma-local`) via `http://192.168.1.91:1234/v1`.
- Fallbacks: `openrouter/google/gemma-4-31b-it:free`, `openrouter/openrouter/free`, `openrouter/openrouter/auto`, `openrouter/owl-alpha`
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

## Pipeline semanal

O `workspace/scripts/weekly.sh` é o ponto de entrada único (alvo do cron):

1. `fetch-all.sh` — captura os snapshots de hoje de cada fonte.
2. `diff-all.sh` — calcula o diff de cada par contra o snapshot anterior.
3. **agente OpenClaw** — lê os diffs e escreve `reports/<ano>-W<semana>.md`.
4. `qa-check.py` — QA Guardrail (rastreabilidade das afirmações); bloqueia o envio se reprovar.
5. `send-briefing.sh` — envia o briefing por email (AgentMail), se as vars estiverem definidas.

**Fiabilidade do agente (importante):**

- O `openclaw agent` devolve **exit 0 mesmo quando falha** (`isError=true`) e não escreve o report. Por isso o `weekly.sh` **não confia no exit code**: cria um marcador antes da run e só dá a run por boa se o `reports/<semana>.md` ficar **mais recente** que o marcador. Se o agente falhar, o script **aborta sem enviar** — nunca reenvia um briefing antigo.
- **Modelos free não servem para esta run.** Tanto o `openrouter/openrouter/free` (narra em vez de chamar a tool `write`) como o `gemini-2.5-flash` **free tier** (429 por limite **por-minuto**, atingido a meio da run porque o agente faz dezenas de chamadas a ler diffs) falham de forma não-vigiável. Para correr no cron usa um **modelo pago** (OpenRouter pago, Gemini com billing, ou DigitalOcean Inference). Custo típico ~$0.10–0.40/run (≈ $5–20/ano).

## Deploy num VPS (DigitalOcean Droplet)

Testado em Ubuntu 24.04. O Chromium do `agent-browser` precisa de RAM — usa um Droplet de **≥ 2 GB**.

```sh
# --- no Droplet ---
timedatectl set-timezone Europe/Lisbon
apt-get update && apt-get install -y git jq python3 curl ca-certificates

# Node 22
curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y nodejs

# libs de sistema do Chromium headless
apt-get install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
  libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
  libasound2t64 libpango-1.0-0 libcairo2 fonts-liberation

# CLIs (fixar as mesmas versões que em dev) + Chromium do Playwright
npm i -g openclaw@2026.5.7 agent-browser@0.27.0
npx --yes playwright install --with-deps chromium
```

O repo é privado e os **secrets não vão no git** (`.env` e `state/.../auth-profiles.json` são gitignored). A forma mais simples é **sincronizar uma instância já configurada** a partir de uma máquina de dev (traz config + secrets + snapshots de baseline):

```sh
# --- a partir da máquina de dev (Mac/Linux) ---
rsync -az --exclude='*.log' --exclude='.DS_Store' \
  openclaw/ root@<IP>:/root/2026-ei-aoopii-c26/openclaw/
rsync -az docs/ root@<IP>:/root/2026-ei-aoopii-c26/docs/
```

Depois, **reescrever os paths absolutos** na config (foram gravados para a máquina de dev):

```sh
# --- no Droplet ---
cd ~/2026-ei-aoopii-c26/openclaw
sed -i 's#/Users/<user>/Documents/GitHub#/root#g' config/openclaw.json   # ou /home/<user>/...
```

> ⚠️ Não corras `make onboard`/`make setup` no Droplet: regeneram o `config/openclaw.json` e apagam a config afinada (provider/modelo, paths). Usa a config que veio no rsync.

Testar antes do cron:

```sh
export OPENCLAW_STATE_DIR="$PWD/state" OPENCLAW_CONFIG_PATH="$PWD/config/openclaw.json"
make smoke                                   # modelo responde?
agent-browser open https://zed.dev/releases && agent-browser get text body | head; agent-browser close
./workspace/scripts/weekly.sh                # pipeline inteiro
```

Cron semanal (o cron tem PATH mínimo — usa um wrapper):

```sh
cat > /root/run-briefing.sh <<'EOF'
#!/usr/bin/env bash
export PATH=/usr/local/bin:/usr/bin:/bin
cd /root/2026-ei-aoopii-c26/openclaw
export OPENCLAW_STATE_DIR="$PWD/state" OPENCLAW_CONFIG_PATH="$PWD/config/openclaw.json"
./workspace/scripts/weekly.sh >> /root/briefing.log 2>&1
EOF
chmod +x /root/run-briefing.sh
( crontab -l 2>/dev/null; echo "0 9 * * 1 /root/run-briefing.sh" ) | crontab -   # 2ª feira 09:00
```

> A key da OpenRouter (e da Gemini, se usada) vive em **dois sítios**: `.env` **e** `state/agents/main/agent/auth-profiles.json`. Ao rodar a key, atualiza os dois — senão o agente usa a antiga e dá `401`.

### Resolução de Problemas no VPS

Caso o e-mail semanal não seja enviado ou queiras testar a integridade do ambiente do VPS (verificar RAM/Swap, caminhos absolutos, variáveis do `.env`, chaves de API ou dependências do Chromium headless), corre o script de diagnóstico no VPS:

```sh
cd ~/2026-ei-aoopii-c26/openclaw
bash workspace/scripts/diagnose-vps.sh
```

## Notas de segurança

- A OpenRouter API key vive em `.env` (gitignored) e, depois do setup, em `state/agents/main/agent/auth-profiles.json` (também gitignored via `state/`).
- O gateway está a escutar apenas em `127.0.0.1`. Se puseres isto num VPS, usa Tailscale / SSH tunnel / reverse proxy com TLS.
- `state/` inclui auth tokens e caches — nunca fazer `git add state/`.
