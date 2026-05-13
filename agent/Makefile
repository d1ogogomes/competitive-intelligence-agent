ZEROCLAW_BIN := .bin/zeroclaw
PROJECT_HOME := $(CURDIR)/data
PROJECT_WORKSPACE := $(CURDIR)/workspace
PROJECT_CONFIG_DIR := $(PROJECT_HOME)/.zeroclaw

.PHONY: init cli daemon status auth-codex config sync-config check-bin search-duckduckgo search-brave browser-driver browser-driver-stop

init: check-bin
	mkdir -p data data/.zeroclaw workspace/scripts workspace/data/snapshots workspace/reports
	cp -n config/config.toml data/.zeroclaw/config.toml
	chmod 600 data/.zeroclaw/config.toml

check-bin:
	@test -x "$(ZEROCLAW_BIN)" || { echo "Missing $(ZEROCLAW_BIN). Put the zeroclaw binary there and run chmod +x $(ZEROCLAW_BIN)."; exit 1; }

config: check-bin
	mkdir -p data/.zeroclaw workspace/scripts workspace/data/snapshots workspace/reports
	cp -n config/config.toml data/.zeroclaw/config.toml
	chmod 600 data/.zeroclaw/config.toml

sync-config: check-bin
	mkdir -p data/.zeroclaw workspace/scripts workspace/data/snapshots workspace/reports
	cp config/config.toml data/.zeroclaw/config.toml
	chmod 600 data/.zeroclaw/config.toml

cli: config
	HOME="$(PROJECT_HOME)" ZEROCLAW_WORKSPACE="$(PROJECT_WORKSPACE)" $(ZEROCLAW_BIN) --config-dir "$(PROJECT_CONFIG_DIR)" agent

daemon: config
	HOME="$(PROJECT_HOME)" ZEROCLAW_WORKSPACE="$(PROJECT_WORKSPACE)" $(ZEROCLAW_BIN) --config-dir "$(PROJECT_CONFIG_DIR)" daemon

status: config
	HOME="$(PROJECT_HOME)" ZEROCLAW_WORKSPACE="$(PROJECT_WORKSPACE)" $(ZEROCLAW_BIN) --config-dir "$(PROJECT_CONFIG_DIR)" status

auth-codex: config
	cp "$(HOME)/.codex/auth.json" data/codex-auth.json
	chmod 600 data/codex-auth.json
	HOME="$(PROJECT_HOME)" ZEROCLAW_WORKSPACE="$(PROJECT_WORKSPACE)" $(ZEROCLAW_BIN) --config-dir "$(PROJECT_CONFIG_DIR)" auth login --provider openai-codex --import "$(PROJECT_HOME)/codex-auth.json"
	rm -f data/codex-auth.json

search-duckduckgo: config
	HOME="$(PROJECT_HOME)" ZEROCLAW_WORKSPACE="$(PROJECT_WORKSPACE)" $(ZEROCLAW_BIN) --config-dir "$(PROJECT_CONFIG_DIR)" config set web-search.provider duckduckgo

search-brave: config
	@test -n "$(BRAVE_API_KEY)" || { echo "Set BRAVE_API_KEY first."; exit 1; }
	HOME="$(PROJECT_HOME)" ZEROCLAW_WORKSPACE="$(PROJECT_WORKSPACE)" $(ZEROCLAW_BIN) --config-dir "$(PROJECT_CONFIG_DIR)" config set web-search.provider brave
	HOME="$(PROJECT_HOME)" ZEROCLAW_WORKSPACE="$(PROJECT_WORKSPACE)" $(ZEROCLAW_BIN) --config-dir "$(PROJECT_CONFIG_DIR)" config set web-search.brave-api-key "$(BRAVE_API_KEY)"

browser-driver:
	mkdir -p data/logs data/run
	@if [ -f data/run/chromedriver.pid ] && kill -0 "$$(cat data/run/chromedriver.pid)" 2>/dev/null; then \
		echo "chromedriver already running on http://127.0.0.1:9515"; \
	else \
		chromedriver --port=9515 --allowed-ips=127.0.0.1 > data/logs/chromedriver.log 2>&1 & echo $$! > data/run/chromedriver.pid; \
		echo "chromedriver started on http://127.0.0.1:9515"; \
	fi

browser-driver-stop:
	@if [ -f data/run/chromedriver.pid ]; then kill "$$(cat data/run/chromedriver.pid)" 2>/dev/null || true; rm -f data/run/chromedriver.pid; fi
