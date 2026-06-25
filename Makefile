SHELL := /bin/bash

.PHONY: .build .clean-stale \
        .drop-database .migrate-database .load-test-data \
        postgres-up postgres-down postgres-login postgres-status postgres-status-full \
        postgres-drop postgres-migrate postgres-load postgres-drop-migrate postgres-drop-migrate-load postgres-auditlog \
        postgres-count \
        generate-area-sql \
        dbgate-up dbgate-down dbgate-restart dbgate-status \
        .keycloak-wait .keycloak-realm .keycloak-admin .keycloak-roles .keycloak-machine-clients .get-client-credentials \
        keycloak-up keycloak-down \
        backend-up backend-down backend-restart \
        up down restart status \
        .is-up .ensure-up .clean-testrun .postgres-up-unless-ci test-full test-full-keep test-full-verbose test-ca test-str test-rep test-smoke test-security test-integration test-migrations \
        test-malware \
        test-perf test-perf-keep test-perf-verbose \
        test test-keep \
        trivy \
        ci \
        all \
        postgres-logs keycloak-logs backend-logs dbgate-logs fullstack-logs \
        md-format md-lint \
        help

.DEFAULT_GOAL := help

ifndef CI
-include .env
-include .env.extra
endif

POSTGRES_HOST ?= localhost
export POSTGRES_HOST POSTGRES_PORT POSTGRES_DB_NAME POSTGRES_DB_USER POSTGRES_DB_PASSWORD

DOCKER_COMPOSE := docker compose --env-file .env $(if $(wildcard .env.extra),--env-file .env.extra,)

# Disable BuildKit provenance/SBOM attestations. With the containerd image store,
# attestations wrap the image in a manifest list and embed build timestamps, so
# every build — even a fully cached one — yields a new image digest. That makes
# `docker compose up -d` needlessly recreate the backend container on each `make up`.
export BUILDX_NO_DEFAULT_ATTESTATIONS := 1

DBGATE_PID_FILE := /tmp/dbgate.pid
DBGATE_PROCESS_PATTERN := /tmp/.mount_[d]bgate.*/dbgate|dbgate-7\.1\.2-linux_x86_64\.AppImage

# Common helpers

.build: ## Build
	@echo "🐳 Building fullstack..."
	$(DOCKER_COMPOSE) build
	@echo "✅ Fullstack built successfully!"
	@echo "📊 Images"
	@set -a && source .env && set +a && docker images | grep $$APP_PREFIX

.clean-stale: ## Remove stale containers
	@echo "🧹 Cleaning stale containers..."
	@set -a && source .env && set +a && \
	docker ps -a --filter "name=$$APP_PREFIX" --filter "status=exited" -q | xargs -r docker rm -f || true
	@$(DOCKER_COMPOSE) rm -f initdb 2>/dev/null || true
	@echo "✅ Stale containers cleaned!"

##@ Postgres

.drop-database: ## Drop database
	@set -a && source .env && set +a && \
	echo "🗑️ Dropping database $$POSTGRES_DB_NAME..." && \
	docker exec -i sdep-postgres psql -U $$POSTGRES_SUPER_USER -d postgres < postgres/clean-app.sql
	@echo "✅ Database dropped!"

.migrate-database: ## Migrate database (create/update tables)
	@echo "🔄 Running database migrations..."
	@docker exec -i $$($(DOCKER_COMPOSE) ps -q backend) alembic upgrade head
	@echo "✅ Database migrations completed!"

.load-test-data: ## Load test data into database
	@echo "🐳 Initializing test data..."
	@set -a && source .env && set +a && \
	echo "Using PostgreSQL user: $$POSTGRES_SUPER_USER" && \
	echo "Connecting to database: $$POSTGRES_DB_NAME" && \
	echo "Executing SQL initialization files..." && \
	for sql_file in $$(ls test-data/*.sql 2>/dev/null | sort); do \
		echo "  Executing: $$sql_file"; \
		docker exec -i sdep-postgres psql -U $$POSTGRES_SUPER_USER -d $$POSTGRES_DB_NAME -v ON_ERROR_STOP=1 < "$$sql_file"; \
	done
	@echo "✅ Test data initialized!"

postgres-up: .clean-stale ## Start postgres
	@echo "🚀 Starting postgres..."
	$(DOCKER_COMPOSE) up -d postgres
	@echo "✅ Postgres started!"

postgres-down: ## Stop and remove postgres (including volumes)
	@echo "🛑 Stopping postgres..."
	$(DOCKER_COMPOSE) stop postgres
	$(DOCKER_COMPOSE) rm -f -v postgres
	@docker volume rm $$(docker volume ls -q | grep postgres_data) 2>/dev/null || true
	@echo "✅ Postgres stopped, removed, and volumes cleaned!"

postgres-login: ## Login to postgres
	@echo "🔐 Connecting to PostgreSQL..."
	docker exec -it $$($(DOCKER_COMPOSE) ps -q postgres) psql -U postgres -d sdep-data

postgres-status: ## Show postgres tables
	@set -a && source .env && set +a && \
	echo "Showing tables for database $$POSTGRES_DB_NAME..." && \
	docker exec sdep-postgres psql -U $$POSTGRES_DB_USER -d $$POSTGRES_DB_NAME -c "\\dt"
	@echo ""
	@echo "Showing structure of each table..."
	@set -a && source .env && set +a && \
	docker exec sdep-postgres psql -U $$POSTGRES_DB_USER -d $$POSTGRES_DB_NAME -t -c "SELECT tablename FROM pg_tables WHERE schemaname='public'" | \
	while read -r table; do \
		if [ -n "$$table" ]; then \
			echo ""; \
			echo "=== Table: $$table ==="; \
			docker exec sdep-postgres psql -U $$POSTGRES_DB_USER -d $$POSTGRES_DB_NAME -c "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='$$table' ORDER BY ordinal_position"; \
		fi; \
	done

postgres-status-full: postgres-status ## Show postgres tables with full details
	@echo ""
	@echo "Showing full structure of each table..."
	@set -a && source .env && set +a && \
	docker exec sdep-postgres psql -U $$POSTGRES_DB_USER -d $$POSTGRES_DB_NAME -t -c "SELECT tablename FROM pg_tables WHERE schemaname='public'" | \
	while read -r table; do \
		if [ -n "$$table" ]; then \
			echo ""; \
			echo "=== Table: $$table (full details) ==="; \
			docker exec sdep-postgres psql -U $$POSTGRES_DB_USER -d $$POSTGRES_DB_NAME -c "\\d+ $$table"; \
		fi; \
	done

##@ Postgres Data

postgres-drop: .clean-stale ## Drop postgres (drop tables)
	@echo "🚀 Dropping sdep-database tables..."
	@$(MAKE) --no-print-directory .drop-database
	@echo "✅ SDEP database dropped!"

postgres-migrate: ## Migrate postgres (create/update tables)
	@echo "🚀 Migrating sdep-database..."
	@$(MAKE) --no-print-directory .migrate-database
	@echo "✅ SDEP database migrated!"

postgres-load: .clean-stale ## Load test data (01-competent-authority.sql + 02-area-generated.sql)
	@echo "🚀 Loading test data into sdep-database..."
	@$(MAKE) --no-print-directory .load-test-data
	@echo "✅ SDEP test data loaded!"

postgres-drop-migrate: .clean-stale ## Drop postgres (drop + migrate)
	@echo "🚀 Resetting sdep-database in postgres ..."
	@$(MAKE) --no-print-directory .drop-database .migrate-database
	@echo "✅ SDEP database reset!"

postgres-drop-migrate-load: .clean-stale ## Drop postgres (drop + migrate + load)
	@echo "🚀 Resetting and loading sdep-database in postgres ..."
	@$(MAKE) --no-print-directory .drop-database .migrate-database .load-test-data
	@echo "✅ SDEP database reset and loaded!"

postgres-auditlog: ## Show audit log
	@set -a && source .env && set +a && \
	echo "Showing audit log for database $$POSTGRES_DB_NAME..." && \
	docker exec sdep-postgres psql -U $$POSTGRES_DB_USER -d $$POSTGRES_DB_NAME -c "SELECT * FROM audit_log"

postgres-count: ## Count all tables in database
	@set -a && source .env && set +a && \
	docker exec sdep-postgres psql -U $$POSTGRES_DB_USER -d $$POSTGRES_DB_NAME -c " \
	  SELECT \
	    (SELECT COUNT(*) FROM activity) AS activity, \
	    (SELECT COUNT(*) FROM area) AS area, \
	    (SELECT COUNT(*) FROM platform) AS platform, \
	    (SELECT COUNT(*) FROM competent_authority) AS competent_authority, \
	    (SELECT COUNT(*) FROM audit_log) AS audit_log;"

generate-area-sql: ## Generate test-data/02-area-generated.sql (when shapefiles changed)
	@echo "🔄 Generating area SQL file with embedded shapefile data..."
	@./test-data/generate-area-sql.sh
	@echo "✅ Area SQL file generated"

##@ DBGate (optional)

dbgate-up: ## Launch DBGate and show local PostgreSQL connection details
	@DBGATE_PIDS=$$(pgrep -f "$(DBGATE_PROCESS_PATTERN)" || true); \
	if [ -n "$$DBGATE_PIDS" ]; then \
		echo "⚠️  DBGate is already running (PID(s): $$DBGATE_PIDS)."; \
		echo "   Use: make dbgate-status"; \
		echo "   Use: make dbgate-restart"; \
		exit 1; \
	fi
	@set -a && source .env && set +a && \
	POSTGRES_STATUS=$$(docker inspect --format='{{.State.Health.Status}}' $$POSTGRES_CONTAINER_NAME 2>&1 | grep -v "^Error" || echo "not-running"); \
	if [ "$$POSTGRES_STATUS" != "healthy" ]; then \
		echo "⚠️  PostgreSQL container '$$POSTGRES_CONTAINER_NAME' is '$$POSTGRES_STATUS' (expected healthy)."; \
		echo "   Start it with: make postgres-up"; \
	fi; \
	echo "🚀 Starting DBGate..." && \
	echo "Use these PostgreSQL connections:" && \
	echo "" && \
	echo "SDEP app database:" && \
	printf "  %-12s %s\n" "Host:" "localhost" && \
	printf "  %-12s %s\n" "Port:" "$$POSTGRES_PORT" && \
	printf "  %-12s %s\n" "Database:" "$$POSTGRES_DB_NAME" && \
	printf "  %-12s %s\n" "User:" "$$POSTGRES_DB_USER" && \
	printf "  %-12s %s\n" "Password:" "$$POSTGRES_DB_PASSWORD" && \
	printf "  %-12s %s\n" "URL (opt):" "postgresql://$$POSTGRES_DB_USER:$$POSTGRES_DB_PASSWORD@localhost:$$POSTGRES_PORT/$$POSTGRES_DB_NAME" && \
	echo "" && \
	echo "Keycloak database:" && \
	printf "  %-12s %s\n" "Host:" "localhost" && \
	printf "  %-12s %s\n" "Port:" "$$POSTGRES_PORT" && \
	printf "  %-12s %s\n" "Database:" "keycloak" && \
	printf "  %-12s %s\n" "User:" "$$KC_DB_USERNAME" && \
	printf "  %-12s %s\n" "Password:" "$$KC_DB_PASSWORD" && \
	printf "  %-12s %s\n" "URL (opt):" "postgresql://$$KC_DB_USERNAME:$$KC_DB_PASSWORD@localhost:$$POSTGRES_PORT/keycloak" && \
	echo "" && \
	echo "Tip: save 2 DBGate connections (local-sdep + local-keycloak)." && \
	echo "Then click the target DB node (sdep-data or keycloak) and Refresh."
	@set -a && source .env && set +a && nohup dbgate "postgresql://$$POSTGRES_DB_USER:$$POSTGRES_DB_PASSWORD@localhost:$$POSTGRES_PORT/$$POSTGRES_DB_NAME" >/tmp/dbgate.log 2>&1 & echo $$! > "$(DBGATE_PID_FILE)"
	@echo "✅ DBGate launched in background (logs: /tmp/dbgate.log)"
	@echo "🌐 DBGate web UI: http://localhost:3000"

dbgate-down: ## Stop DBGate
	@PIDS=""; \
	if [ -f "$(DBGATE_PID_FILE)" ]; then \
		PID_FROM_FILE=$$(cat "$(DBGATE_PID_FILE)" 2>/dev/null || true); \
		if [ -n "$$PID_FROM_FILE" ] && kill -0 "$$PID_FROM_FILE" 2>/dev/null; then \
			PIDS="$$PID_FROM_FILE"; \
		fi; \
	fi; \
	if [ -z "$$PIDS" ]; then \
		PIDS=$$(pgrep -f "$(DBGATE_PROCESS_PATTERN)" || true); \
	fi; \
	if [ -n "$$PIDS" ]; then \
		echo "🛑 Stopping DBGate..."; \
		kill $$PIDS; \
		rm -f "$(DBGATE_PID_FILE)"; \
		echo "✅ DBGate stopped"; \
	else \
		rm -f "$(DBGATE_PID_FILE)"; \
		echo "ℹ️  DBGate is not running"; \
	fi

dbgate-restart: dbgate-down dbgate-up ## Restart DBGate

dbgate-status: ## Show DBGate and Postgres status
	@set -a && source .env && set +a && \
	POSTGRES_STATUS=$$(docker inspect --format='{{.State.Health.Status}}' $$POSTGRES_CONTAINER_NAME 2>&1 | grep -v "^Error" || echo "not-running"); \
	DBGATE_PS=$$(pgrep -af "$(DBGATE_PROCESS_PATTERN)" || true); \
	PID_FILE_INFO="missing"; \
	if [ -f "$(DBGATE_PID_FILE)" ]; then PID_FILE_INFO=$$(cat "$(DBGATE_PID_FILE)" 2>/dev/null || echo "invalid"); fi; \
	echo "🔍 Postgres status"; \
	printf "  %-12s %s\n" "Postgres:" "$$POSTGRES_STATUS"; \
	echo ""; \
	echo "🔍 DBGate status (optional)"; \
	printf "  %-16s %s\n" "DBGate pid file:" "$$PID_FILE_INFO"; \
	if [ -n "$$DBGATE_PS" ]; then \
		printf "  %-16s %s\n" "DBGate:" "running"; \
		echo "  Processes:"; \
		echo "$$DBGATE_PS"; \
	else \
		printf "  %-16s %s\n" "DBGate:" "stopped"; \
	fi; \
	printf "  %-16s %s\n" "DBGate UI:" "http://localhost:3000"; \
	printf "  %-16s %s\n" "SDEP URL:" "postgresql://$$POSTGRES_DB_USER:$$POSTGRES_DB_PASSWORD@localhost:$$POSTGRES_PORT/$$POSTGRES_DB_NAME"; \
	printf "  %-16s %s\n" "KC URL:" "postgresql://$$KC_DB_USERNAME:$$KC_DB_PASSWORD@localhost:$$POSTGRES_PORT/keycloak"

##@ Keycloak

.keycloak-wait: ## Wait until keycloak allows to authenticate
	@./keycloak/wait.sh
	@set -a && source .env && set +a && echo "✅ $$KC_BASE_URL"

.keycloak-realm: .keycloak-wait ## Create realm
	@set -a && source .env && set +a && ./keycloak/add-realm.sh

.keycloak-admin: .keycloak-realm ## Create (CI/CD) admin account in realm
	@mkdir -p ./tmp
	@set -a && source .env && set +a && \
	KC_APP_REALM_ADMIN_SECRET=$$(bash keycloak/add-realm-admin.sh | grep "Client Secret:" | cut -d' ' -f3) && \
	echo "$$KC_APP_REALM_ADMIN_SECRET" > ./tmp/KC_APP_REALM_ADMIN_SECRET.txt

.keycloak-roles: .keycloak-admin ## Create roles in realm (keycloak/roles.yaml)
	@set -a && source .env && set +a && \
	export KC_APP_REALM_ADMIN_SECRET=$$(cat ./tmp/KC_APP_REALM_ADMIN_SECRET.txt) && \
	./keycloak/add-realm-roles.sh

.keycloak-machine-clients: .keycloak-roles ## Create machine clients in realm (keycloak/machine-clients.yaml)
	@set -a && source .env && set +a && \
	export KC_APP_REALM_ADMIN_SECRET=$$(cat ./tmp/KC_APP_REALM_ADMIN_SECRET.txt) && \
	./keycloak/add-realm-machine-clients.sh

.get-client-credentials: ## Retrieve client credentials from Keycloak
	@set -a && source .env && set +a && \
	export KC_APP_REALM_ADMIN_SECRET=$$(cat ./tmp/KC_APP_REALM_ADMIN_SECRET.txt) && \
	source ./keycloak/get-client-secret.sh && \
	CA1_CLIENT_ID=sdep-test-ca.01 && KC_APP_REALM_CLIENT_ID=$$CA1_CLIENT_ID && get_client_secret && CA1_CLIENT_SECRET=$$KC_APP_REALM_CLIENT_SECRET && \
	CA2_CLIENT_ID=sdep-test-ca.02 && KC_APP_REALM_CLIENT_ID=$$CA2_CLIENT_ID && get_client_secret && CA2_CLIENT_SECRET=$$KC_APP_REALM_CLIENT_SECRET && \
	STR_CLIENT_ID=sdep-test-str.01 && KC_APP_REALM_CLIENT_ID=$$STR_CLIENT_ID && get_client_secret && STR_CLIENT_SECRET=$$KC_APP_REALM_CLIENT_SECRET && \
	REP_CLIENT_ID=sdep-test-rep.01 && KC_APP_REALM_CLIENT_ID=$$REP_CLIENT_ID && get_client_secret && REP_CLIENT_SECRET=$$KC_APP_REALM_CLIENT_SECRET && \
	echo "export CA1_CLIENT_ID=$$CA1_CLIENT_ID" > ./tmp/.credentials && \
	echo "export CA1_CLIENT_SECRET=$$CA1_CLIENT_SECRET" >> ./tmp/.credentials && \
	echo "export CA2_CLIENT_ID=$$CA2_CLIENT_ID" >> ./tmp/.credentials && \
	echo "export CA2_CLIENT_SECRET=$$CA2_CLIENT_SECRET" >> ./tmp/.credentials && \
	echo "export STR_CLIENT_ID=$$STR_CLIENT_ID" >> ./tmp/.credentials && \
	echo "export STR_CLIENT_SECRET=$$STR_CLIENT_SECRET" >> ./tmp/.credentials && \
	echo "export REP_CLIENT_ID=$$REP_CLIENT_ID" >> ./tmp/.credentials && \
	echo "export REP_CLIENT_SECRET=$$REP_CLIENT_SECRET" >> ./tmp/.credentials

keycloak-up: postgres-up ## Start and configure keycloak (realm, roles, machine-clients)
	@echo "🚀 Starting Keycloak..."
	$(DOCKER_COMPOSE) up -d keycloak
	@echo "✅ Keycloak started!"
	@echo "🚀 Configuring Keycloak..."
	@$(MAKE) --no-print-directory .keycloak-machine-clients
	@echo "✅ Keycloak configured!"

keycloak-down: ## Stop and remove keycloak (including volumes)
	@echo "🛑 Stopping Keycloak..."
	$(DOCKER_COMPOSE) stop keycloak
	$(DOCKER_COMPOSE) rm -f -v keycloak
	@echo "✅ Keycloak stopped, removed, and volumes cleaned!"

##@ Backend

backend-up: .build .clean-stale ## Start backend
	@echo "🚀 Starting backend..."
	$(DOCKER_COMPOSE) up -d backend
	@echo "✅ Backend started! "
	@echo "Run 'make status' to explore URLs"

backend-down: ## Stop and remove backend (including volumes)
	@echo "🛑 Stopping backend..."
	$(DOCKER_COMPOSE) stop backend
	$(DOCKER_COMPOSE) rm -f -v backend
	@echo "✅ Backend stopped, removed, and volumes cleaned!"

backend-restart: backend-down backend-up ## Stop and restart backend

##@ Fullstack (keycloak + postgres + backend, and load testdata)

up: .build .clean-stale ## Start
	@echo "🚀 Starting full-stack..."
	$(DOCKER_COMPOSE) up -d
	@echo "✅ Fullstack started!"

	@echo "🚀 Configuring Keycloak..."
	@$(MAKE) --no-print-directory .keycloak-machine-clients
	@echo "✅ Keycloak configured!"

	@echo "🚀 Initializing database..."
	@$(MAKE) --no-print-directory postgres-drop-migrate-load
	@echo "✅ Database initialized!"

	@echo "🚀 Showing stack status..."
	@$(MAKE) --no-print-directory status
	@echo "✅ Status shown!"

down: ## Stop and remove (including volumes)
	@echo "🛑 Stopping full-stack..."
	$(DOCKER_COMPOSE) down -v # Includes volume deletion
	@echo "✅ Fullstack stopped!"

restart: down up ## Stop and start

status: ## Show status
	@echo ""
	@echo "🔍 Images:"BACKEND_TEST_REPO
	@$(DOCKER_COMPOSE) ps
	@echo ""
	@echo "🔍 Use these URLs when images are running:"
	@set -a && source .env && set +a && \
	printf "  %-42s %s\n" "Backend API docs (version independent):" "$$BACKEND_BASE_URL/api/docs" && \
	printf "  %-42s %s\n" "Backend API docs (auth):" "$$BACKEND_BASE_URL/api/auth/v1/docs" && \
	printf "  %-42s %s\n" "Backend API docs (ca):" "$$BACKEND_BASE_URL/api/ca/v1/docs" && \
	printf "  %-42s %s\n" "Backend API docs (str):" "$$BACKEND_BASE_URL/api/str/v1/docs" && \
	printf "  %-42s %s\n" "Backend health:" "$$BACKEND_BASE_URL/api/health" && \
	printf "  %-42s %s\n" "Keycloak:" "$$KC_BASE_URL/admin"
	@echo ""

##@ Tests (Fullstack)

.is-up: ## Check if services are running
	@echo "🔍 Checking if services are up..." && \
	set -a && source .env && set +a && \
	POSTGRES_STATUS=$$(docker inspect --format='{{.State.Health.Status}}' $$POSTGRES_CONTAINER_NAME 2>&1 | grep -v "^Error" || echo "not-running"); \
	KC_STATUS=$$(docker inspect --format='{{.State.Status}}' $$KC_CONTAINER_NAME 2>&1 | grep -v "^Error" || echo "not-running"); \
	BACKEND_STATUS=$$(docker inspect --format='{{.State.Health.Status}}' $$BACKEND_CONTAINER_NAME 2>&1 | grep -v "^Error" || echo "not-running"); \
	ALL_UP=true; \
	echo ""; \
	printf "  %-15s %s\n" "Postgres:" "$$POSTGRES_STATUS"; \
	if [ "$$POSTGRES_STATUS" != "healthy" ]; then ALL_UP=false; fi; \
	printf "  %-15s %s\n" "Keycloak:" "$$KC_STATUS"; \
	if [ "$$KC_STATUS" != "running" ]; then ALL_UP=false; fi; \
	printf "  %-15s %s\n" "Backend:" "$$BACKEND_STATUS"; \
	if [ "$$BACKEND_STATUS" != "healthy" ]; then ALL_UP=false; fi; \
	echo ""; \
	if [ "$$ALL_UP" = "true" ]; then \
		echo "✅ All services are up and healthy!"; \
		exit 0; \
	else \
		echo "❌ Some services are not healthy!"; \
		echo ""; \
		echo "Please start all services first with:"; \
		echo "  make up"; \
		echo ""; \
		exit 1; \
	fi

.ensure-up: ## Start the stack only if it is not already running and healthy
	@$(MAKE) --no-print-directory .is-up >/dev/null 2>&1 || $(MAKE) --no-print-directory up

.clean-testrun: ## Clean sdep-test-* data from database
	@set -a && source .env && set +a && \
	docker exec -i sdep-postgres psql -U $$POSTGRES_SUPER_USER -d $$POSTGRES_DB_NAME \
		-v ON_ERROR_STOP=1 < postgres/clean-testrun.sql

test-full: .ensure-up ## Test fullstack (quiet)
	@set -a && source ./.env && set +a && \
	set -o pipefail && \
	$(MAKE) --no-print-directory test-full-verbose 2>&1 | sed -n '/^══ TEST RESULTS/,$$p'

test-full-keep: .ensure-up .get-client-credentials ## Test fullstack (quiet, keep generated data until either test without "keep")
	@set -a && source ./.env && set +a && \
	set -o pipefail && \
	KEEP_TEST_DATA=true $(CURDIR)/scripts/run-tests.sh 2>&1 | sed -n '/^══ TEST RESULTS/,$$p'

test-full-verbose: .ensure-up .get-client-credentials ## Test fullstack (verbose)
	@$(CURDIR)/scripts/run-tests.sh

test-ca: .ensure-up .get-client-credentials # Helper - Test only CA endpoints
	@set -a && source ./.env && source ./tmp/.credentials && set +a && set -o pipefail && \
	OUTPUT_FILE=$$(mktemp) && \
	trap "rm -f $$OUTPUT_FILE" EXIT && \
	echo "🏛️  Testing CA endpoints..." && \
	echo "BACKEND_BASE_URL: $$BACKEND_BASE_URL" && \
	echo "" && \
	if CLIENT_ID=$$CA1_CLIENT_ID CLIENT_SECRET=$$CA1_CLIENT_SECRET uv run --script tests/test_auth_client.py; then \
		echo "✅ CA client authorized"; \
	else \
		echo "❌ CA client authorization failed"; \
		exit 1; \
	fi && \
	uv run --script tests/test_health_ping.py 2>&1 | tee $$OUTPUT_FILE && \
	uv run --script tests/test_ca_areas.py 2>&1 | tee $$OUTPUT_FILE && \
	uv run --script tests/test_ca_activities.py 2>&1 | tee $$OUTPUT_FILE && \
	echo "✅ CA endpoints tested"

test-str: .ensure-up .get-client-credentials # Helper - Test only STR endpoints
	@set -a && source ./.env && source ./tmp/.credentials && set +a && set -o pipefail && \
	OUTPUT_FILE=$$(mktemp) && \
	trap "rm -f $$OUTPUT_FILE" EXIT && \
	echo "🏘️  Testing STR endpoints..." && \
	echo "BACKEND_BASE_URL: $$BACKEND_BASE_URL" && \
	echo "" && \
	if CLIENT_ID=$$STR_CLIENT_ID CLIENT_SECRET=$$STR_CLIENT_SECRET uv run --script tests/test_auth_client.py; then \
		echo "✅ STR client authorized"; \
	else \
		echo "❌ STR client authorization failed"; \
		exit 1; \
	fi && \
	uv run --script tests/test_health_ping.py 2>&1 | tee $$OUTPUT_FILE && \
	uv run --script tests/test_str_areas.py 2>&1 | tee $$OUTPUT_FILE && \
	uv run --script tests/test_str_activities_bulk.py 2>&1 | tee $$OUTPUT_FILE && \
	echo "✅ STR endpoints tested"

test-rep: .ensure-up .get-client-credentials # Helper - Test only REP endpoints
	@set -a && source ./.env && source ./tmp/.credentials && set +a && set -o pipefail && \
	OUTPUT_FILE=$$(mktemp) && \
	trap "rm -f $$OUTPUT_FILE" EXIT && \
	echo "📊 Testing REP endpoints..." && \
	echo "BACKEND_BASE_URL: $$BACKEND_BASE_URL" && \
	echo "" && \
	if CLIENT_ID=$$REP_CLIENT_ID CLIENT_SECRET=$$REP_CLIENT_SECRET uv run --script tests/test_auth_client.py; then \
		echo "✅ REP client authorized"; \
	else \
		echo "❌ REP client authorization failed"; \
		exit 1; \
	fi && \
	uv run --script tests/test_health_ping.py 2>&1 | tee $$OUTPUT_FILE && \
	uv run --script tests/test_rep_activities.py 2>&1 | tee $$OUTPUT_FILE && \
	echo "✅ REP endpoints tested"

test-smoke: .ensure-up ## Test smoke test (audit-excluded, no auth needed)
	@set -a && source ./.env && set +a && \
	echo "🔍 Testing smoke test endpoints..." && \
	uv run --script tests/test_smoketest.py && \
	echo "✅ Smoke test endpoints tested"

test-security: .ensure-up .get-client-credentials # Helper - Test only security (headers, unauthorized, credentials)
	@set -a && source ./.env && source ./tmp/.credentials && set +a && set -o pipefail && \
	OUTPUT_FILE=$$(mktemp) && \
	trap "rm -f $$OUTPUT_FILE" EXIT && \
	echo "🔒 Testing security..." && \
	echo "BACKEND_BASE_URL: $$BACKEND_BASE_URL" && \
	echo "" && \
	echo "Testing security headers..." && \
	uv run --script tests/test_auth_headers.py 2>&1 | tee $$OUTPUT_FILE && \
	echo "" && \
	echo "Testing unauthorized access..." && \
	uv run --script tests/test_auth_unauthorized.py 2>&1 | tee $$OUTPUT_FILE && \
	echo "" && \
	echo "Testing credentials..." && \
	uv run --script tests/test_auth_credentials.py 2>&1 | tee $$OUTPUT_FILE && \
	echo "" && \
	echo "Testing client-ID regex..." && \
	uv run --script tests/test_client_id_regex.py 2>&1 | tee $$OUTPUT_FILE && \
	echo "✅ Security tested"

# No .ensure-up here on purpose: the malware test talks directly to ClamAV (not the
# backend API), so it only needs its own clamav container, started below (idempotent
# if `make up` already started it). Bringing up the full stack would run a compose
# build/up that fails where there is no compose stack — this keeps test-malware able
# to run standalone in a CI/CD environment (which provides ClamAV as a service).
test-malware: # Helper - Test malware scanning (starts ClamAV via Docker Compose if not already running)
	@echo "🧪 Running malware scanning tests..."
	@if [ -z "$$CI" ]; then \
		$(DOCKER_COMPOSE) up -d clamav; \
		CLAMAV_CONTAINER_ID="$$($(DOCKER_COMPOSE) ps -q clamav)"; \
		CLAMAV_HEALTH="$$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' "$$CLAMAV_CONTAINER_ID")"; \
		if [ "$$CLAMAV_HEALTH" = "unhealthy" ]; then \
			echo "❌ ClamAV container is unhealthy; malware scan tests cannot run."; \
			echo ""; \
			echo "Docker healthcheck output:"; \
			docker inspect --format '{{range .State.Health.Log}}{{println .Output}}{{end}}' "$$CLAMAV_CONTAINER_ID"; \
			echo "Recent ClamAV logs:"; \
			$(DOCKER_COMPOSE) logs --tail=40 clamav; \
			exit 1; \
		fi; \
	fi
	uv run --script tests/malware/test_malware_scan.py
	@echo "✅ Malware scanning tests completed!"

test-migrations: .postgres-up-unless-ci # Helper - Test Alembic migrations against PostgreSQL
	@echo "🧪 Running migration integration checks..."
	@cd backend && uv run python scripts/wait_for_postgres.py
	@$(MAKE) -C backend --no-print-directory upgrade
	@uv run --script tests/test_postgres_check_constraints.py
	@echo "✅ Migration integration checks completed!"

.postgres-up-unless-ci:
	@if [ -z "$$CI" ]; then \
		$(MAKE) --no-print-directory postgres-up; \
	fi

test-integration: ## Test integration tests (migration and malware)
	@$(MAKE) --no-print-directory test-migrations
	@$(MAKE) --no-print-directory test-malware

##@ Tests (Performance)

PERF_ACTIVITIES_TARGET ?= 5000
PERF_MAX_DURATION_SECONDS ?= 300
PERF_BATCH_SIZE ?= 1000
PERF_USERS ?= 10
PERF_RAMP_UP ?= 1
PERF_KEEP_DATA ?= false
PERF_STOP_ON_TARGET ?= true
PERF_AUTO_CONFIRM ?= false

PERF_ENV = PERF_ACTIVITIES_TARGET=$(PERF_ACTIVITIES_TARGET) \
           PERF_USERS=$(PERF_USERS) \
           PERF_RAMP_UP=$(PERF_RAMP_UP) \
           PERF_MAX_DURATION_SECONDS=$(PERF_MAX_DURATION_SECONDS) \
           PERF_BATCH_SIZE=$(PERF_BATCH_SIZE) \
           PERF_KEEP_DATA=$(PERF_KEEP_DATA) \
           PERF_STOP_ON_TARGET=$(PERF_STOP_ON_TARGET) \
           PERF_AUTO_CONFIRM=$(PERF_AUTO_CONFIRM)

test-perf: .ensure-up .get-client-credentials ## Test bulk performance (PERF_AUTO_CONFIRM=true to skip confirmation)
	@$(PERF_ENV) $(CURDIR)/scripts/run-tests-perf.sh

test-perf-keep: .ensure-up .get-client-credentials ## Test bulk performance (keep generated data until either test without "keep")
	@$(PERF_ENV) PERF_KEEP_DATA=true $(CURDIR)/scripts/run-tests-perf.sh

test-perf-verbose: .ensure-up .get-client-credentials ## Test bulk performance with periodic Locust stats
	@$(PERF_ENV) PERF_VERBOSE=true $(CURDIR)/scripts/run-tests-perf.sh

##@ Tests (All)

test: ## Run all tests (fullstack + malware + migrations + performance)
	@echo "🧪 Running all tests..."
	@echo ""
	@echo "  1. Fullstack tests (test-full)"
	@echo "  2. Integration tests: migrations + malware (test-integration)"
	@echo "  3. Performance tests (test-perf)"
	@echo ""
	@$(MAKE) --no-print-directory test-full
	@$(MAKE) --no-print-directory test-integration
	@$(MAKE) --no-print-directory test-perf PERF_AUTO_CONFIRM=true
	@echo ""
	@echo "✅ All tests completed (fullstack + malware + migrations + performance)"
	@echo ""
	@$(MAKE) --no-print-directory postgres-count

test-keep: ## Run all tests, keeping generated data (fullstack + malware + migrations + performance)
	@echo "🧪 Running all tests (keep generated data)..."
	@echo ""
	@echo "  1. Fullstack tests (test-full-keep)"
	@echo "  2. Integration tests: migrations + malware (test-integration)"
	@echo "  3. Performance tests (test-perf-keep)"
	@echo ""
	@$(MAKE) --no-print-directory test-full-keep
	@$(MAKE) --no-print-directory test-integration
	@$(MAKE) --no-print-directory test-perf-keep PERF_AUTO_CONFIRM=true
	@echo ""
	@echo "✅ All tests completed (fullstack + malware + migrations + performance, data kept)"
	@echo ""
	@$(MAKE) --no-print-directory postgres-count

##@ Security Checks

trivy: export DOCKER_DEFAULT_PLATFORM := linux/amd64
# Scan a throwaway tag (local/sdep-backend:trivy-scan) instead of the dev image.
# The fresh --no-cache build below otherwise replaces local/sdep-backend:latest,
# which would make the next `make up` needlessly recreate the backend container.
trivy: export BACKEND_IMAGE_VERSION := trivy-scan
trivy: ## Run security checks (build and scan backend image with Trivy CVE allowlist checks)
	@echo "🔒 Running all security checks..."
	@echo ""
	@# Always build fresh (--pull --no-cache) so apt-get upgrade fetches current
	@# Debian security patches; a cached layer would mask already-fixed CVEs.
	@$(DOCKER_COMPOSE) build --pull --no-cache backend
	@mkdir -p tmp/trivy-scan
	@docker save "$(BACKEND_IMAGE_NAME):$(if $(BACKEND_IMAGE_VERSION),$(BACKEND_IMAGE_VERSION),latest)" -o tmp/trivy-scan/backend-image.tar
	@$(DOCKER_COMPOSE) run --rm -e TRIVY_INPUT=tmp/trivy-scan/backend-image.tar run-trivy-scan
	@echo ""
	@echo "✅ All security checks completed (trivy-scan)"

##@ Markdown

# markdownlint-cli2 runs via npx (the npm package) — needs only Node/npm on PATH
# This works both locally and in CI: the GitLab toolbox image has npm but no
# Docker mountpoint. mdformat runs via uv/uvx (Python): mdformat-gfm aligns tables and
# the local .mdformat-sdep plugin renders thematic breaks as "---" (house rule).
MARKDOWNLINT_VERSION := 0.18.1
MARKDOWNLINT := npx --yes markdownlint-cli2@$(MARKDOWNLINT_VERSION)
MARKDOWNLINT_FIX := $(MARKDOWNLINT) --fix
MDFORMAT := uvx --from mdformat==1.0.0 --with mdformat-gfm==1.0.0 --with ./.mdformat-sdep mdformat --number
MDFORMAT_FILES := README.md CLAUDE.md docs

md-lint: ## Lint Markdown (markdownlint + mdformat --check); CI gate
	@echo "🔍 Linting Markdown..."
	@$(MARKDOWNLINT)
	@$(MDFORMAT) --check $(MDFORMAT_FILES)
	@echo "✅ Markdown lint passed!"

md-format: ## Format Markdown (auto-fix: house rules + table alignment)
	@echo "📝 Formatting Markdown..."
	@$(MARKDOWNLINT_FIX) || true
	@$(MDFORMAT) $(MDFORMAT_FILES)
	@echo "✅ Markdown formatted!"

##@ All

# Mirrors the REQUIRED checks the GitLab pipeline runs on push (.gitlab-ci.yml + backend/.gitlab-ci.yml):
#   markdown:lint            -> md-lint
#   test:backend             -> make -C backend test (pytest + coverage)
#   test:database-migrations -> test-migrations
#   test:malware             -> test-malware
# Trivy (trivy:backend) is intentionally excluded: it is set to warning, not failure, so it is
# not a required gate. Run `make trivy` separately for the image CVE scan.
# Note: CI does NOT run the fullstack (test-full) or performance (test-perf) suites on push;
# those live in `make all`/`make test`. Keep this target in sync with the pipeline jobs.
ci: ## Run the required GitLab pipeline checks (md-lint + backend test + migrations + malware)
	@echo "🧪 Running CI checks (mirrors required GitLab pipeline gates)..."
	@echo ""
	@$(MAKE) --no-print-directory md-lint
	@$(MAKE) -C backend --no-print-directory test
	@$(MAKE) --no-print-directory test-migrations
	@$(MAKE) --no-print-directory test-malware
	@echo ""
	@echo "✅ CI checks completed (md-lint + backend test + migrations + malware)"

all: ## Run all tests, markdown lint and security checks (ensures fullstack is started)
	@echo "🧪 Running all tests, markdown lint and security checks..."
	@echo ""
	@$(MAKE) --no-print-directory md-lint
	@$(MAKE) --no-print-directory test
	@$(MAKE) --no-print-directory trivy
	@echo ""
	@echo "✅ All tests, markdown lint and security checks completed (md-lint + test + security)"

##@ Logs

postgres-logs: ## Show postgres logs
	$(DOCKER_COMPOSE) logs -f sdep-postgres

keycloak-logs: ## Show keycloak logs
	$(DOCKER_COMPOSE) logs -f sdep-keycloak

backend-logs: ## Show backend logs
	$(DOCKER_COMPOSE) logs -f backend

dbgate-logs: ## Show dbgate logs (optional)
	@touch /tmp/dbgate.log
	@echo "📜 Tailing /tmp/dbgate.log (Ctrl+C to stop)"
	@tail -f /tmp/dbgate.log

fullstack-logs: ## Show fullstack logs (postgres + keycloak + backend + dbgate/optional)
	$(DOCKER_COMPOSE) logs -f

##@ Help

help: ## Show help
	@echo "🤖 Make"
	@echo ""
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-40s\033[0m  %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
