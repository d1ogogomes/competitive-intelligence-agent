# OpenClaw Lab

OpenClaw isolado para o projeto da cadeira. Nao usa `~/.openclaw` como state/config.

## Caminhos

```txt
OPENCLAW_STATE_DIR=./state
OPENCLAW_CONFIG_PATH=./config/openclaw.json
workspace=./workspace
gateway=127.0.0.1:42717
```

## Comandos

```sh
make setup
make sync-config
make validate
make models
make auth
make cli
make agent
make gateway
make skills
make plugins
make memory-status
make memory-index
make memory-search Q="project monitor"
```

## Config

- Modelo principal: `openai-codex/gpt-5.5`
- Thinking/reasoning: `low`
- Tools profile: `full`
- Exec approval: `tools.exec.ask = off`
- Web search/fetch: enabled
- Browser: Chromium nativo em headless
- Browser skills: `agent-browser`, `agent-browser-core`, `openclaw-agent-browser-clawdbot`, `browser-automation`
- Memory skills/plugins: `safe-memory-manager`, `memory-core`, `active-memory`, `memory-wiki`
- Memory search: memory + sessions, hybrid retrieval, file watch, compaction memory flush
- Memory embeddings: `github-copilot` no lab, para evitar depender de `node-llama-cpp`

O auth profile `openai-codex:default` fica declarado, mas os tokens reais nao sao copiados para este repo.

## Browser

As skills pessoais de browser foram copiadas para:

```txt
workspace/skills/agent-browser
workspace/skills/agent-browser-core
workspace/skills/openclaw-agent-browser-clawdbot
```

## Memoria

Memoria inicial do projeto:

```txt
workspace/MEMORY.md
workspace/memory/project.md
```

Indexar e testar:

```sh
make memory-index
make memory-search Q="AI competitor monitor"
```
