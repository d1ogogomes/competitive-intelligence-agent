# Agent

Projeto para monitorizar fontes web sobre concorrentes/produtos de IA, guardar snapshots, detetar mudancas e gerar relatorios semanais.

## Stack

- ZeroClaw em modo nativo local
- Auth por Codex subscription profile (`openai-codex` + `gpt-5.5`)
- Reasoning em modo `low`
- `config/config.toml` versionado
- `data/` local ignorado no Git para auth, memoria, cache e import temporario do Codex auth
- `workspace/` para scripts, snapshots e relatorios

## Arranque rapido

```sh
make init
make auth-codex
make cli
```

O gateway fica exposto apenas no host local:

```txt
127.0.0.1:42617
```

## Comandos

```sh
make init        # cria data/, workspace/ e config ativa
make auth-codex  # importa ~/.codex/auth.json para data/
make cli         # abre o CLI/agent local
make daemon      # corre o daemon local
make status      # mostra status local
make sync-config # aplica config/config.toml em data/.zeroclaw/config.toml
make browser-driver # inicia chromedriver para browser/screenshot
make search-duckduckgo  # search sem API key, mas menos fiavel
BRAVE_API_KEY=... make search-brave  # search mais fiavel com Brave API
```

O `Makefile` força `HOME` e `ZEROCLAW_WORKSPACE` para esta pasta:

```txt
data/       -> auth, memoria, cache e config ativa
workspace/  -> scripts, snapshots e relatorios
.bin/       -> binario local do ZeroClaw ignorado no Git
```

## Estrutura

```txt
.
├── .bin/
├── .gitignore
├── Makefile
├── config/
│   └── config.toml
├── workspace/
│   ├── scripts/
│   ├── data/
│   └── reports/
├── docs/
│   ├── project-challenges.md
│   └── technical-challenges.md
└── README.md
```

## Web search e tools

A configuracao aprova automaticamente as tools principais para este projeto:

- `web_search_tool`
- `web_fetch`
- `web_search`
- `browser_search`
- `browser_fetch`
- `browser`
- `browser_open`
- `screenshot`
- `http_fetch`
- `content_search`
- `glob_search`
- `file_read`
- `file_write`
- `file_edit`
- `git_operations`
- `memory_recall`
- `memory_store`
- `calculator`

Isto permite ao agente pesquisar fontes, abrir paginas, comparar conteudo, editar scripts e gerar relatorios mantendo o modo de autonomia como `supervised`.

Por defeito o provider de search é `duckduckgo`, porque não precisa de chave. Se devolver resultados vazios em queries que existem, muda para Brave Search com `BRAVE_API_KEY=... make search-brave`.

Para browser/screenshot, a config aponta para Chromium nativo:

```txt
browser.backend = "native"
browser.native_chrome_path = "/usr/bin/chromium"
browser.native_webdriver_url = "http://127.0.0.1:9515"
```

Antes de pedir screenshots ao agente, inicia o driver:

```sh
make browser-driver
make cli
```

## Notas de seguranca

Nao exponhas `0.0.0.0:42617` diretamente a internet sem autenticacao. Em VPS, usa Tailscale, Cloudflare Tunnel, SSH tunnel ou reverse proxy com HTTPS, autenticacao e firewall.
