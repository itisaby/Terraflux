.PHONY: help setup install clean dev test lint format docker-build docker-up docker-down

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Infrastructure Provisioning Agent - Available Commands"
	@echo "======================================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Run initial project setup
	@echo "🏗️  Setting up Infrastructure Provisioning Agent..."
	python3 setup.py

install: ## Install Python dependencies
	@echo "📦 Installing dependencies..."
	pip install -r requirements.txt

install-dev: ## Install development dependencies
	@echo "📦 Installing development dependencies..."
	pip install -r requirements.txt
	pip install black flake8 mypy pylint

clean: ## Clean temporary files and caches
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache dist build

init-db: ## Initialize database tables
	@echo "🗄️  Initializing database..."
	python -c "from database.session import init_db; init_db()"

reset-db: ## Reset database (WARNING: Deletes all data!)
	@echo "⚠️  Resetting database..."
	@read -p "Are you sure? This will delete all data! (y/N): " confirm && \
	if [ "$$confirm" = "y" ]; then \
		python -c "from database.session import engine, Base; Base.metadata.drop_all(engine); Base.metadata.create_all(engine); print('Database reset complete')"; \
	else \
		echo "Cancelled."; \
	fi

create-admin: ## Create admin user
	@echo "👤 Creating admin user..."
	python -c "from database.session import SessionLocal, create_test_user; db = SessionLocal(); create_test_user(db, 'admin', 'admin123'); db.close()"

dev: ## Run both API and frontend in development mode
	@echo "🚀 Starting development servers..."
	@trap 'kill 0' INT; \
	python app.py & \
	sleep 2 && streamlit run frontend/streamlit_app.py

api: ## Run API server only
	@echo "🚀 Starting API server..."
	python app.py

frontend: ## Run frontend only
	@echo "🚀 Starting frontend..."
	streamlit run frontend/streamlit_app.py

test: ## Run tests
	@echo "🧪 Running tests..."
	pytest tests/ -v

test-coverage: ## Run tests with coverage report
	@echo "🧪 Running tests with coverage..."
	pytest tests/ -v --cov=. --cov-report=html --cov-report=term

lint: ## Run linters
	@echo "🔍 Running linters..."
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

format: ## Format code with Black
	@echo "🎨 Formatting code..."
	black .

type-check: ## Run type checking with mypy
	@echo "🔎 Type checking..."
	mypy . --ignore-missing-imports

check: lint type-check ## Run all checks (lint + type check)

docker-build: ## Build Docker image
	@echo "🐳 Building Docker image..."
	docker build -t infrastructure-agent:latest .

docker-up: ## Start services with Docker Compose
	@echo "🐳 Starting Docker services..."
	docker-compose up -d

docker-down: ## Stop Docker services
	@echo "🐳 Stopping Docker services..."
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f

terraform-init: ## Initialize Terraform
	@echo "🏗️  Initializing Terraform..."
	cd terraform && terraform init

terraform-plan: ## Run Terraform plan
	@echo "🏗️  Running Terraform plan..."
	cd terraform && terraform plan

logs: ## View application logs
	tail -f logs/infraagent.log

logs-error: ## View error logs only
	tail -f logs/infraagent.log | grep ERROR

backup-db: ## Backup database
	@echo "💾 Backing up database..."
	@mkdir -p backups
	pg_dump $(DATABASE_URL) > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "Backup created in backups/"

restore-db: ## Restore database from backup
	@echo "📥 Restoring database..."
	@read -p "Enter backup file path: " backup_file && \
	psql $(DATABASE_URL) < $$backup_file

generate-secret: ## Generate new secret keys
	@echo "🔑 Generating new secret keys..."
	@python -c "from cryptography.fernet import Fernet; print('SECRET_KEY=' + Fernet.generate_key().decode()); print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"

run-migrations: ## Run database migrations
	@echo "🔄 Running migrations..."
	alembic upgrade head

create-migration: ## Create a new migration
	@read -p "Enter migration message: " message && \
	alembic revision --autogenerate -m "$$message"

shell: ## Open Python shell with app context
	@python -c "from database.session import SessionLocal; from database.models import *; db = SessionLocal(); print('Database session available as: db'); import code; code.interact(local=locals())"

info: ## Show project information
	@echo "Infrastructure Provisioning Agent"
	@echo "=================================="
	@echo "Python: $$(python --version)"
	@echo "Terraform: $$(terraform --version 2>/dev/null | head -n1 || echo 'Not installed')"
	@echo "PostgreSQL: $$(psql --version 2>/dev/null || echo 'Not installed')"
	@echo ""
	@echo "Project directories:"
	@echo "  - Workspaces: terraform/workspaces/"
	@echo "  - Logs: logs/"
	@echo "  - Templates: mcp/server/templates/"
