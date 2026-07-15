# TNSVT V2 - Makefile
# Comandos principales para gestionar el monorepo

.PHONY: help up down logs status test build clean restart ps shell \
        db-shell redis-cli nats-cli migrate seed backup restore \
        lint format deps-update docs-build docs-serve

# Variables
COMPOSE_FILE = docker-compose.dev.yml
DOCKER = docker compose -f $(COMPOSE_FILE)

help: ## Mostrar ayuda
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║                  TNSVT V2 - Comandos                        ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Stack:"
	@echo "  make up              - Levantar todo el stack (Docker Compose)"
	@echo "  make down            - Detener todo"
	@echo "  make restart         - Reiniciar todos los servicios"
	@echo "  make logs            - Ver logs (follow)"
	@echo "  make ps              - Ver estado de contenedores"
	@echo ""
	@echo "Servicios individuales:"
	@echo "  make status          - Estado de servicios (script bash)"
	@echo "  make shell SERVICE=x - Shell en un servicio"
	@echo "  make logs-svc S=x    - Logs de un servicio específico"
	@echo ""
	@echo "Desarrollo:"
	@echo "  make build           - Build imágenes Docker"
	@echo "  make test            - Correr tests"
	@echo "  make lint            - Linter"
	@echo "  make format          - Formatear código"
	@echo "  make deps-update     - Actualizar dependencias"
	@echo ""
	@echo "Database:"
	@echo "  make db-shell        - Shell PostgreSQL"
	@echo "  make migrate         - Correr migraciones"
	@echo "  make seed            - Cargar datos de prueba"
	@echo "  make backup          - Backup de DB"
	@echo "  make restore F=file  - Restaurar backup"
	@echo ""
	@echo "Utilidades:"
	@echo "  make redis-cli       - Conectar a Redis"
	@echo "  make nats-cli        - Conectar a NATS"
	@echo "  make clean           - Limpiar todo (volúmenes + contenedores)"

up: ## Levantar stack
	@echo "▶ Levantando stack..."
	$(DOCKER) up -d
	@echo "✓ Stack levantado. Esperando 10s para health checks..."
	@sleep 10
	@echo ""
	@make status

down: ## Detener stack
	@echo "▶ Deteniendo stack..."
	$(DOCKER) down
	@echo "✓ Stack detenido"

restart: ## Reiniciar stack
	@echo "▶ Reiniciando stack..."
	$(DOCKER) restart
	@echo "✓ Stack reiniciado"

logs: ## Ver logs
	$(DOCKER) logs -f --tail=100

ps: ## Ver contenedores
	$(DOCKER) ps

status: ## Estado de servicios
	@bash scripts/status.sh

shell: ## Shell en un servicio (make shell SERVICE=postgres)
	$(DOCKER) exec -it $(SERVICE) /bin/sh

logs-svc: ## Logs de un servicio (make logs-svc SERVICE=postgres)
	$(DOCKER) logs -f --tail=200 $(SERVICE)

build: ## Build imágenes
	@echo "▶ Building imágenes..."
	$(DOCKER) build --parallel
	@echo "✓ Build completo"

test: ## Correr tests
	@bash scripts/test-all.sh

lint: ## Linter
	@echo "▶ Linting Go..."
	@cd shared/go-common && go vet ./... && cd ../..
	@echo "▶ Linting Python..."
	@find apps -name "*.py" -not -path "*/venv/*" -exec python -m py_compile {} \;
	@echo "✓ Lint completo"

format: ## Formatear código
	@echo "▶ Formatting Go..."
	@cd shared/go-common && gofmt -w . && cd ../..
	@echo "▶ Formatting Python..."
	@find apps -name "*.py" -not -path "*/venv/*" -exec black {} \; 2>/dev/null || true
	@echo "✓ Format completo"

deps-update: ## Actualizar dependencias
	@echo "▶ Actualizando Go modules..."
	@find apps shared -name "go.mod" -exec dirname {} \; | while read dir; do \
		cd $$dir && go mod tidy && cd - > /dev/null; \
	done
	@echo "▶ Actualizando Python deps..."
	@find apps -name "requirements.txt" -exec pip install -U -r {} \; 2>/dev/null || true
	@echo "✓ Dependencias actualizadas"

db-shell: ## Shell PostgreSQL
	$(DOCKER) exec -it postgres psql -U tnsvt -d tnsvt

redis-cli: ## Redis CLI
	$(DOCKER) exec -it redis redis-cli

nats-cli: ## NATS CLI
	$(DOCKER) exec -it nats nats sub ">"
	@echo "Para más: make nats-cli-pub SUBJ=trading.signal"

migrate: ## Correr migraciones
	@echo "▶ Corriendo migraciones..."
	@bash scripts/migrate.sh

seed: ## Cargar datos de prueba
	@echo "▶ Cargando datos..."
	@bash scripts/seed.sh

backup: ## Backup DB
	@echo "▶ Backup PostgreSQL..."
	@mkdir -p backups
	$(DOCKER) exec postgres pg_dump -U tnsvt -d tnsvt > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "✓ Backup guardado en backups/"

restore: ## Restaurar backup (F=backups/file.sql)
	@echo "▶ Restaurando $(F)..."
	cat $(F) | $(DOCKER) exec -T postgres psql -U tnsvt -d tnsvt
	@echo "✓ Restore completo"

docs-build: ## Regenerar Word + PDF desde Markdown
	@echo "▶ Regenerando documentos..."
	@python convert_docs.py
	@python convert_pdf.py
	@echo "✓ Documentos regenerados"

clean: ## Limpiar todo
	@echo "▶ Limpiando..."
	$(DOCKER) down -v --remove-orphans
	@echo "✓ Limpieza completa"