.PHONY: help dev prod up down restart rebuild logs clean reset-db

help: ## Show this help message
	@echo "BookClub Development Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

init: ## Generate the secret key required for the project
	sed -i 's/change-this-to-a-random-secret-key-in-production/${shell openssl rand -hex 32}/g' bookclub.env

dev: ## Start in development mode (live code updates)
	docker compose -f docker-compose.dev.yml up -d

start: ## Start with default docker-compose.yml
	docker compose up -d

stop: ## Stop and remove containers
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

reset-db: ## Delete database (CAUTION: deletes all data!)
	@echo "WARNING: This will delete all your data!"
	@read -p "Are you sure? [Y/N] " answer; \
	if [ $$answer = 'Y' ]; then \
		docker compose down; \
		sudo rm -f data/bookclub.db; \
		echo "Database reset complete!"; \
	else \
		echo "Cancelled."; \
	fi