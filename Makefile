.PHONY: help dev prod up down restart rebuild logs clean reset-db

help: ## Show this help message
	@echo "BookClub Development Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

dev: ## Start in development mode (live code updates)
	docker compose -f docker-compose.dev.yml up -d

prod: ## Start in production mode (requires rebuild for changes)
	docker compose -f docker-compose.prod.yml up -d

up: ## Start with default docker-compose.yml
	docker compose up -d

down: ## Stop and remove containers
	docker compose down

restart: ## Restart containers (keeps volumes)
	docker compose restart

rebuild: ## Rebuild and restart (for when dependencies change)
	docker compose down
	docker compose build --no-cache
	docker compose up -d

logs: ## Show container logs (follow mode)
	docker compose logs -f

clean: ## Stop containers and remove all images
	docker compose down
	docker rmi bookclub-bookclub 2>/dev/null || true

reset-db: ## Delete database and restart (CAUTION: deletes all data!)
	@echo "WARNING: This will delete all your data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker compose down; \
		rm -rf data/bookclub.db; \
		docker compose up -d; \
		echo "Database reset complete!"; \
	else \
		echo "Cancelled."; \
	fi