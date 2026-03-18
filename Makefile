IMAGE   ?= ghcr.io/domatron22/bookclub
VERSION ?= latest
APP_UID ?= 4001
APP_GID ?= 4001

.PHONY: help init start stop restart pull rebuild build-image push logs clean reset-db build-css watch-css install-deps

help: ## Show this help message
	@echo "Coverbound Development Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Deployment ───────────────────────────────────────────────────────────────

init: ## One-time setup: create data directory and generate secret key
	mkdir -p data
	sudo chown $(APP_UID):$(APP_GID) data
	sed -i 's/change-this-to-a-random-secret-key-in-production/${shell openssl rand -hex 32}/g' coverbound.env

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
