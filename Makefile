.PHONY: help dev prod build up down logs clean test shell migrate

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)MedBench Automation Testing Tool - Docker Commands$(NC)"
	@echo ""
	@echo "$(GREEN)Usage:$(NC)"
	@echo "  make [command]"
	@echo ""
	@echo "$(GREEN)Commands:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-15s$(NC) %s\n", $$1, $$2}'

dev: ## Start development environment with hot reload
	@echo "$(GREEN)Starting development environment...$(NC)"
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

dev-build: ## Build and start development environment
	@echo "$(GREEN)Building and starting development environment...$(NC)"
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build

dev-d: ## Start development environment in background
	@echo "$(GREEN)Starting development environment in background...$(NC)"
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

prod: ## Start production environment
	@echo "$(GREEN)Starting production environment...$(NC)"
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

prod-build: ## Build and start production environment
	@echo "$(GREEN)Building and starting production environment...$(NC)"
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml build
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

down: ## Stop all services
	@echo "$(YELLOW)Stopping all services...$(NC)"
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml down

down-v: ## Stop all services and remove volumes (WARNING: Deletes data)
	@echo "$(RED)Stopping services and removing volumes...$(NC)"
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml down -v

logs: ## View logs from all services
	docker-compose logs -f

logs-api: ## View API logs
	docker-compose logs -f api

logs-celery: ## View Celery worker logs
	docker-compose logs -f celery-worker

logs-db: ## View database logs
	docker-compose logs -f postgres

ps: ## Show running containers
	docker-compose ps

build: ## Build all Docker images
	@echo "$(GREEN)Building Docker images...$(NC)"
	docker-compose build

test: ## Run tests
	@echo "$(GREEN)Running tests...$(NC)"
	docker-compose exec api pytest

test-cov: ## Run tests with coverage
	@echo "$(GREEN)Running tests with coverage...$(NC)"
	docker-compose exec api pytest --cov=medbench_automation --cov-report=html

shell-api: ## Open shell in API container
	docker-compose exec api bash

shell-db: ## Open PostgreSQL shell
	docker-compose exec postgres psql -U medbench -d medbench_automation

shell-redis: ## Open Redis CLI
	docker-compose exec redis redis-cli

migrate: ## Run database migrations
	@echo "$(GREEN)Running database migrations...$(NC)"
	docker-compose exec api alembic upgrade head

migrate-create: ## Create new migration (usage: make migrate-create MSG="description")
	@echo "$(GREEN)Creating new migration...$(NC)"
	docker-compose exec api alembic revision --autogenerate -m "$(MSG)"

scale-workers: ## Scale Celery workers (usage: make scale-workers N=4)
	@echo "$(GREEN)Scaling Celery workers to $(N)...$(NC)"
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d --scale celery-worker=$(N)

health: ## Check service health
	@echo "$(BLUE)Checking service health...$(NC)"
	@echo "API Health:"
	@curl -s http://localhost:8000/api/health | python -m json.tool || echo "$(RED)API not responding$(NC)"
	@echo "\nPostgreSQL:"
	@docker-compose exec -T postgres pg_isready -U medbench || echo "$(RED)PostgreSQL not ready$(NC)"
	@echo "Redis:"
	@docker-compose exec -T redis redis-cli PING || echo "$(RED)Redis not responding$(NC)"

clean: ## Clean up Docker resources
	@echo "$(YELLOW)Cleaning up Docker resources...$(NC)"
	docker-compose down --rmi local --volumes --remove-orphans
	docker system prune -f

backup-db: ## Backup PostgreSQL database
	@echo "$(GREEN)Backing up database...$(NC)"
	docker-compose exec -T postgres pg_dump -U medbench medbench_automation > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)Backup completed: backup_$(shell date +%Y%m%d_%H%M%S).sql$(NC)"

restore-db: ## Restore PostgreSQL database (usage: make restore-db FILE=backup.sql)
	@echo "$(YELLOW)Restoring database from $(FILE)...$(NC)"
	docker-compose exec -T postgres psql -U medbench medbench_automation < $(FILE)
	@echo "$(GREEN)Database restored$(NC)"

env-copy: ## Copy environment template
	@echo "$(GREEN)Copying environment template...$(NC)"
	cp env.example .env
	@echo "$(YELLOW)Please edit .env and add your configuration$(NC)"

setup: env-copy ## Initial setup (copy env and start services)
	@echo "$(GREEN)Initial setup...$(NC)"
	@echo "$(YELLOW)Please edit .env and add your OPENAI_API_KEY$(NC)"
	@echo "$(YELLOW)Then run: make dev$(NC)"

flower: ## Open Flower UI in browser
	@echo "$(GREEN)Opening Flower UI...$(NC)"
	@python -m webbrowser http://localhost:5555 || echo "Visit: http://localhost:5555"

docs: ## Open API documentation in browser
	@echo "$(GREEN)Opening API docs...$(NC)"
	@python -m webbrowser http://localhost:8000/api/docs || echo "Visit: http://localhost:8000/api/docs"

restart: down dev ## Restart all services

restart-api: ## Restart API service only
	docker-compose restart api

restart-celery: ## Restart Celery workers
	docker-compose restart celery-worker

watch: ## Watch logs with auto-refresh
	watch -n 2 'docker-compose ps'









