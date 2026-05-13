ROOT := $(CURDIR)
STATE := $(ROOT)/state
CONFIG := $(ROOT)/config/openclaw.json
WORKSPACE := $(ROOT)/workspace
PATCH_LINUX := $(ROOT)/openclaw.patch.json5
PATCH_MACOS := $(ROOT)/openclaw.patch.macos.json5
ENV_FILE := $(ROOT)/.env

UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
  PATCH := $(PATCH_MACOS)
else
  PATCH := $(PATCH_LINUX)
endif

ENV := OPENCLAW_STATE_DIR="$(STATE)" OPENCLAW_CONFIG_PATH="$(CONFIG)"

.PHONY: env setup setup-full onboard sync-config validate status models auth auth-openrouter smoke cli agent gateway health mcp tools skills install-skill update-skills plugins memory-status memory-index memory-search doctor reset

env:
	@echo OPENCLAW_STATE_DIR=$(STATE)
	@echo OPENCLAW_CONFIG_PATH=$(CONFIG)
	@echo WORKSPACE=$(WORKSPACE)
	@echo OS=$(UNAME_S) PATCH=$(PATCH)

setup: onboard sync-config
	@echo "Setup complete. Next: make auth-openrouter (requires OPENROUTER_API_KEY in .env)"

# One-shot setup that also registers the OpenRouter API key in a single pass.
# Safe to re-run.
setup-full:
	@test -f $(ENV_FILE) || { echo "Missing $(ENV_FILE). Copy .env.example to .env and fill OPENROUTER_API_KEY."; exit 1; }
	@set -a; . ./.env; set +a; \
	  test -n "$$OPENROUTER_API_KEY" || { echo "OPENROUTER_API_KEY is empty in $(ENV_FILE)"; exit 1; }; \
	  mkdir -p config state workspace; \
	  $(ENV) openclaw onboard \
	    --non-interactive --accept-risk --mode local \
	    --workspace "$(WORKSPACE)" \
	    --auth-choice openrouter-api-key \
	    --openrouter-api-key "$$OPENROUTER_API_KEY" \
	    --gateway-bind loopback --gateway-port 42717 \
	    --gateway-auth token --gateway-token dev-local-token \
	    --skip-channels --skip-daemon --skip-ui --skip-health \
	    --skip-skills --skip-search --skip-bootstrap
	$(MAKE) sync-config
	@echo "setup-full done. Run 'make smoke' to test."

onboard:
	mkdir -p config state workspace
	$(ENV) openclaw onboard \
	  --non-interactive --accept-risk --mode local \
	  --workspace "$(WORKSPACE)" \
	  --auth-choice skip \
	  --gateway-bind loopback --gateway-port 42717 \
	  --gateway-auth token --gateway-token dev-local-token \
	  --skip-channels --skip-daemon --skip-ui --skip-health \
	  --skip-skills --skip-search --skip-bootstrap

sync-config:
	$(ENV) openclaw config patch --file $(PATCH)

validate:
	$(ENV) openclaw config validate

status:
	$(ENV) openclaw status

models:
	$(ENV) openclaw models status --plain

auth:
	$(ENV) openclaw models auth list

# Loads OPENROUTER_API_KEY from .env and stores it as an OpenClaw auth profile.
# The key stays inside state/ (gitignored) and is never committed.
auth-openrouter:
	@test -f $(ENV_FILE) || { echo "Missing $(ENV_FILE). Copy .env.example to .env and fill OPENROUTER_API_KEY."; exit 1; }
	@set -a; . $(ENV_FILE); set +a; \
	  test -n "$$OPENROUTER_API_KEY" || { echo "OPENROUTER_API_KEY is empty in $(ENV_FILE)"; exit 1; }; \
	  $(ENV) openclaw models auth paste-token \
	    --provider openrouter \
	    --profile-id openrouter:default \
	    <<< "$$OPENROUTER_API_KEY"

cli:
	$(ENV) openclaw chat

agent:
	$(ENV) openclaw agent --local --message "Confirma qual modelo estás a usar e lista as tools disponíveis." --thinking low

# Quick end-to-end test: asks the embedded agent a trivial question and prints
# the response. Fails loud if the model chain does not respond.
smoke:
	@set -a; . ./.env; set +a; \
	  $(ENV) openclaw agent --local --thinking low --timeout 90 \
	    --agent main --session-id smoke-test-$$$$ \
	    --message "Reply with exactly one sentence: confirm you reached the model and compute 7*6."
	@rm -f state/agents/main/sessions/smoke-test-*

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

install-skill:
	@test -n "$(SLUG)" || { echo "Usage: make install-skill SLUG=humanizer"; exit 1; }
	$(ENV) openclaw skills install "$(SLUG)"

update-skills:
	$(ENV) openclaw skills update

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

reset:
	rm -rf state workspace config/openclaw.json.bak*
	@echo "Cleared state/ workspace/ and config backups. Run 'make setup' to start over."
