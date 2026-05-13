ROOT := $(CURDIR)
STATE := $(ROOT)/state
CONFIG := $(ROOT)/config/openclaw.json
WORKSPACE := $(ROOT)/workspace

ENV := OPENCLAW_STATE_DIR="$(STATE)" OPENCLAW_CONFIG_PATH="$(CONFIG)"

.PHONY: env setup sync-config validate status models auth cli agent gateway health mcp tools skills plugins memory-status memory-index memory-search doctor

env:
	@echo OPENCLAW_STATE_DIR=$(STATE)
	@echo OPENCLAW_CONFIG_PATH=$(CONFIG)
	@echo WORKSPACE=$(WORKSPACE)

setup:
	mkdir -p config state workspace data reports scripts
	$(ENV) openclaw onboard --non-interactive --accept-risk --mode local --workspace "$(WORKSPACE)" --auth-choice skip --gateway-bind loopback --gateway-port 42717 --gateway-auth token --gateway-token dev-local-token --skip-channels --skip-daemon --skip-ui --skip-health
	$(MAKE) sync-config

sync-config:
	$(ENV) openclaw config patch --file openclaw.patch.json5

validate:
	$(ENV) openclaw config validate

status:
	$(ENV) openclaw status

models:
	$(ENV) openclaw models status --plain

auth:
	$(ENV) openclaw models auth list

cli:
	$(ENV) openclaw chat

agent:
	$(ENV) openclaw agent --local --message "Verifica modelo, reasoning low e tools de web/browser/exec disponíveis." --thinking low

gateway:
	$(ENV) openclaw gateway --port 42717

health:
	$(ENV) openclaw health

mcp:
	$(ENV) openclaw mcp list

tools:
	$(ENV) openclaw config get tools

skills:
	$(ENV) openclaw skills list

plugins:
	$(ENV) openclaw plugins list

memory-status:
	$(ENV) openclaw memory status

memory-index:
	$(ENV) openclaw memory index --force

memory-search:
	@test -n "$(Q)" || { echo "Usage: make memory-search Q='project monitor'"; exit 1; }
	$(ENV) openclaw memory search "$(Q)"

doctor:
	$(ENV) openclaw doctor
