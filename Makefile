IMAGE   ?= ghcr.io/domatron22/bookclub
VERSION ?= latest
APP_UID ?= 4001
APP_GID ?= 4001

.PHONY: help init start stop restart pull rebuild build-image push logs clean reset-db build-css watch-css install-deps check check-auth check-ui check-shell shots playwright-check

help: ## Show this help message
	@echo "Coverbound Development Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Deployment ───────────────────────────────────────────────────────────────

init: ## One-time setup: create data directory, env file, and secret key
	mkdir -p data
	sudo chown $(APP_UID):$(APP_GID) data
	@if [ ! -f coverbound.env ]; then \
		cp coverbound.env.example coverbound.env; \
		echo "* Created coverbound.env from coverbound.env.example"; \
	fi
	@if grep -q '^SECRET_KEY=change-this-to-a-random-secret-key-in-production$$' coverbound.env; then \
		sed -i "s|^SECRET_KEY=change-this-to-a-random-secret-key-in-production$$|SECRET_KEY=$$(openssl rand -hex 32)|" coverbound.env; \
		echo "* Generated a SECRET_KEY unique to this deployment"; \
	elif grep -q '^SECRET_KEY=..*$$' coverbound.env; then \
		echo "* SECRET_KEY is already set - leaving it alone"; \
	else \
		echo "coverbound.env has no SECRET_KEY to set. Copy coverbound.env.example over it and re-run." >&2; \
		exit 1; \
	fi

start: ## Start the container (pulls image if not present)
	APP_UID=$(APP_UID) APP_GID=$(APP_GID) docker compose up -d

stop: ## Stop and remove containers
	docker compose down

restart: ## Restart containers (keeps volumes)
	docker compose restart

pull: ## Pull the latest image from the registry
	docker compose pull

rebuild: ## Pull latest image and recreate containers
	docker compose pull
	APP_UID=$(APP_UID) APP_GID=$(APP_GID) docker compose up -d

logs: ## Follow container logs
	docker compose logs -f

clean: ## Stop containers and remove the local image
	docker compose down
	docker rmi $(IMAGE) 2>/dev/null || true

reset-db: ## Delete database (CAUTION: deletes all data!)
	@echo "WARNING: This will delete all your data!"
	@read -p "Are you sure? [Y/N] " answer; \
	if [ $$answer = 'Y' ]; then \
		docker compose down; \
		sudo rm -f data/coverbound.db; \
		echo "Database reset complete!"; \
	else \
		echo "Cancelled."; \
	fi

# ── Image publishing (maintainer) ────────────────────────────────────────────

build-image: build-css ## Build the Docker image
	docker build -t $(IMAGE):$(VERSION) -t $(IMAGE):latest .

push: build-image ## Build and push image to the registry
	docker push $(IMAGE):$(VERSION)
	docker push $(IMAGE):latest

# ── Local development ─────────────────────────────────────────────────────────

install-deps: ## Install Node dependencies for Tailwind
	npm install

build-css: install-deps ## Build Tailwind CSS for production
	npm run build:css

watch-css: ## Watch and rebuild CSS on changes
	npm run watch:css

# ── Checks ───────────────────────────────────────────────────────────────────
# The browser sweeps drive a running app, so start one first and point BASE at
# it. The scripts default to :8009; check-auth defaults to :8011 and needs the
# same SECRET_KEY the app is running with.

BASE   ?= http://127.0.0.1:8009
PYTHON ?= .venv/bin/python

check: check-auth check-ui ## Run every check (needs a running app)

check-auth: ## Auth/session regression harness (creates accounts - use a throwaway DB)
	$(PYTHON) scripts/check_auth.py

check-ui: playwright-check ## Full sweep: every screen, both themes, all breakpoints, plus flows
	BASE=$(BASE) node scripts/check_all.js

check-shell: playwright-check ## Narrower sweep: just the nav/header/footer shell
	BASE=$(BASE) node scripts/check_shell.js

shots: playwright-check ## Screenshot one page at all breakpoints/themes: make shots PATH_=/clubs/ABC123
	@test -n "$(PATH_)" || { echo "usage: make shots PATH_=/some/path [OUT=dir]" >&2; exit 1; }
	BASE=$(BASE) node scripts/shots.js "$(PATH_)" $(if $(OUT),--out "$(OUT)",)

playwright-check:  # internal: Playwright is intentionally not in package.json
	@node -e "require.resolve('playwright')" 2>/dev/null || { \
		echo "Playwright is not installed. It is deliberately kept out of"; \
		echo "package.json so 'npm ci' never pulls it into the production image."; \
		echo "Install it locally with:"; \
		echo "    npm install --no-save playwright && npx playwright install chromium"; \
		exit 1; }
