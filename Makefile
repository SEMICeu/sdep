SHELL := /bin/bash

.PHONY: help up down restart status test test-quiet logs postgres-up postgres-down keycloak-up keycloak-down backend-up backend-down \
        postgres-clean postgres-load .build .is-up .clean-stale .drop-database .migrate-database .generate-area-sql \
        .keycloak-wait .keycloak-realm .keycloak-admin .keycloak-roles .keycloak-machine-clients .get-client-credentials \
        .clean-testrun test-security test-str test-ca \
        postgres-login postgres-status postgres-full \
        backend-logs postgres-logs keycloak-logs

.DEFAULT_GOAL := help

# Helpers

.clean-stale: ## Remove stale containers
	@echo "🧹 Cleaning stale containers..."
	@set -a && source .env && set +a && \
	docker ps -a --filter "name=$$APP_PREFIX" --filter "status=exited" -q | xargs -r docker rm -f || true
	@docker compose rm -f initdb 2>/dev/null || true
	@echo "✅ Stale containers cleaned!"


.drop-database: ## Drop database
	@set -a && source .env && set +a && \
	echo "🧹 Cleaning database $$POSTGRES_DB_NAME..." && \
	docker exec -i sdep-postgres psql -U $$POSTGRES_SUPER_USER -d postgres < postgres/clean-app.sql
	@echo "✅ Database cleaned!"

.migrate-database: ## Migrate database (create/update tables)
	@echo "🔄 Running database migrations..."
	@docker exec -i $$(docker compose ps -q backend) alembic upgrade head
	@echo "✅ Database migrations completed!"

.generate-area-sql: ## Helper to generate 02-area-generated.sql with embedded shapefile data
	@echo "🔄 Generating area SQL file with embedded shapefile data..."
	@./test-data/generate-area-sql.sh
	@echo "✅ Area SQL file generated"

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
	KC_APP_REALM_CLIENT_ID=sdep-test-ca01 && get_client_secret && CA_CLIENT_ID=$$KC_APP_REALM_CLIENT_ID && CA_CLIENT_SECRET=$$KC_APP_REALM_CLIENT_SECRET && \
	KC_APP_REALM_CLIENT_ID=sdep-test-str01 && get_client_secret && STR_CLIENT_ID=$$KC_APP_REALM_CLIENT_ID && STR_CLIENT_SECRET=$$KC_APP_REALM_CLIENT_SECRET && \
	echo "export CA_CLIENT_ID=$$CA_CLIENT_ID" > ./tmp/.credentials && \
	echo "export CA_CLIENT_SECRET=$$CA_CLIENT_SECRET" >> ./tmp/.credentials && \
	echo "export STR_CLIENT_ID=$$STR_CLIENT_ID" >> ./tmp/.credentials && \
	echo "export STR_CLIENT_SECRET=$$STR_CLIENT_SECRET" >> ./tmp/.credentials

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

.build: ## Build
	@echo "🐳 Building fullstack..."
	docker compose build
	@echo "✅ Fullstack built successfully!"
	@echo "📊 Images"
	@set -a && source .env && set +a && docker images | grep $$APP_PREFIX

##@ Postgres

postgres-up: .clean-stale ## Start postgres
	@echo "🚀 Starting postgres..."
	docker compose up -d postgres
	@echo "✅ Postgres started!"

postgres-down: ## Stop and remove postgres (including volumes)
	@echo "🛑 Stopping postgres..."
	docker compose stop postgres
	docker compose rm -f -v postgres
	@docker volume rm $$(docker volume ls -q | grep postgres_data) 2>/dev/null || true
	@echo "✅ Postgres stopped, removed, and volumes cleaned!"

postgres-login: ## Login to postgres
	@echo "🔐 Connecting to PostgreSQL..."
	docker exec -it $$(docker compose ps -q postgres) psql -U postgres -d sdep-data

postgres-status: ## Show postgres tables (SDEP)
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

postgres-full: postgres-status ## Show postgres tables with full details (SDEP)
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

postgres-clean: .clean-stale ## Clean postgres (drop, migrate)
	@echo "🚀 Resetting sdep-database in postgres ..."
	@$(MAKE) --no-print-directory .drop-database .migrate-database
	@echo "✅ SDEP database reset!"

postgres-load: .generate-area-sql ## Load test data
	@echo "🐳 Initializing test data..."
	@set -a && source .env && set +a && \
	echo "Using PostgreSQL user: $$POSTGRES_SUPER_USER" && \
	echo "Connecting to database: $$POSTGRES_DB_NAME" && \
	sleep 3
	@echo "Executing SQL initialization files..."
	@set -a && source .env && set +a && \
	for sql_file in $$(ls test-data/*.sql 2>/dev/null | sort); do \
		echo "  Executing: $$sql_file"; \
		docker exec -i sdep-postgres psql -U $$POSTGRES_SUPER_USER -d $$POSTGRES_DB_NAME -v ON_ERROR_STOP=1 < "$$sql_file"; \
	done
	@echo "✅ Test data initialized"

postgres-logs: ## Show postgres logs
	docker compose logs -f sdep-postgres

##@ Keycloak

keycloak-up: postgres-up ## Start keycloak
	@echo "🚀 Starting Keycloak..."
	docker compose up -d keycloak
	@echo "✅ Keycloak started!"
	@echo "🚀 Configuring Keycloak..."
	@$(MAKE) --no-print-directory .keycloak-realm || echo Realm already added
	@$(MAKE) --no-print-directory .keycloak-roles || echo Roles already added
	@$(MAKE) --no-print-directory .keycloak-machine-clients || echo Machine clients already added
	@echo "✅ Keycloak configured!"

keycloak-down: ## Stop and remove keycloak (including volumes)
	@echo "🛑 Stopping Keycloak..."
	docker compose stop keycloak
	docker compose rm -f -v keycloak
	@echo "✅ Keycloak stopped, removed, and volumes cleaned!"

keycloak-logs: ## Show keycloak logs
	docker compose logs -f sdep-keycloak

##@ Backend

backend-up: .build .clean-stale ## Start backend
	@echo "🚀 Starting backend..."
	docker compose up -d backend
	@echo "✅ Backend started! "
	@echo "Run 'make status' to explore URLs"

backend-down: ## Stop and remove backend (including volumes)
	@echo "🛑 Stopping backend..."
	docker compose stop backend
	docker compose rm -f -v backend
	@echo "✅ Backend stopped, removed, and volumes cleaned!"

backend-restart: backend-down backend-up ## Stop and restart backend

backend-logs: ## Show backend logs
	docker compose logs -f backend

##@ Fullstack (keycloak + postgres + backend + testdata)

up: .build .clean-stale ## Start
	@echo "🚀 Starting full-stack..."
	docker compose up -d
	@echo "✅ Fullstack started!"

	@echo "🚀 Configuring Keycloak..."
	@$(MAKE) --no-print-directory .keycloak-realm
	@$(MAKE) --no-print-directory .keycloak-roles
	@$(MAKE) --no-print-directory .keycloak-machine-clients
	@echo "✅ Keycloak configured!"

	@echo "🚀 Initializing database..."
	@$(MAKE) --no-print-directory postgres-clean
	@$(MAKE) --no-print-directory postgres-load
	@echo "✅ Database initialized!"

	@echo "🚀 Showing stack status..."
	@$(MAKE) --no-print-directory status
	@echo "✅ Status shown!"

down: ## Stop and remove
	@echo "🛑 Stopping full-stack..."
	docker compose down -v # Includes volume deletion
	@echo "✅ Fullstack stopped!"

restart: down up ## Stop and start

status: ## Show status
	@echo ""
	@echo "🔍 Images:"BACKEND_TEST_REPO
	@docker compose ps
	@echo ""
	@echo "🔍 Use these URLs when images are running:"
	@set -a && source .env && set +a && \
	printf "  %-30s %s\n" "Backend API docs:" "$$BACKEND_BASE_URL/api/v0/docs" && \
	printf "  %-30s %s\n" "Backend health:" "$$BACKEND_BASE_URL/api/health" && \
	printf "  %-30s %s\n" "Keycloak:" "$$KC_BASE_URL/admin"
	@echo ""

logs: ## Show logs
	docker compose logs -f

##@ Test

.clean-testrun: ## Clean sdep-test-* data from database
	@set -a && source .env && set +a && \
	docker exec -i sdep-postgres psql -U $$POSTGRES_SUPER_USER -d $$POSTGRES_DB_NAME \
		-v ON_ERROR_STOP=1 < postgres/clean-testrun.sql

test-security: .is-up .get-client-credentials ## Test security (headers, unauthorized, credentials)
	@set -a && source ./.env && source ./tmp/.credentials && set +a && set -o pipefail && \
	OUTPUT_FILE=$$(mktemp) && \
	trap "rm -f $$OUTPUT_FILE" EXIT && \
	echo "🔒 Testing security..." && \
	echo "BACKEND_BASE_URL: $$BACKEND_BASE_URL" && \
	echo "" && \
	echo "Testing security headers..." && \
	./tests/test_auth_headers.sh 2>&1 | tee $$OUTPUT_FILE && \
	echo "" && \
	echo "Testing unauthorized access..." && \
	./tests/test_auth_unauthorized.sh 2>&1 | tee $$OUTPUT_FILE && \
	echo "" && \
	echo "Testing credentials..." && \
	./tests/test_auth_credentials.sh 2>&1 | tee $$OUTPUT_FILE && \
	echo "✅ Security tested"

test-ca: .is-up .get-client-credentials ## Test CA endpoints
	@set -a && source ./.env && source ./tmp/.credentials && set +a && set -o pipefail && \
	OUTPUT_FILE=$$(mktemp) && \
	trap "rm -f $$OUTPUT_FILE" EXIT && \
	echo "🏛️  Testing CA endpoints..." && \
	echo "BACKEND_BASE_URL: $$BACKEND_BASE_URL" && \
	echo "" && \
	if CLIENT_ID=$$CA_CLIENT_ID CLIENT_SECRET=$$CA_CLIENT_SECRET ./tests/test_auth_client.sh; then \
		echo "✅ CA client authorized"; \
	else \
		echo "❌ CA client authorization failed"; \
		exit 1; \
	fi && \
	./tests/test_health_ping.sh 2>&1 | tee $$OUTPUT_FILE && \
	./tests/test_ca_areas.sh 2>&1 | tee $$OUTPUT_FILE && \
	./tests/test_ca_activities.sh 2>&1 | tee $$OUTPUT_FILE && \
	echo "✅ CA endpoints tested"

test-str: .is-up .get-client-credentials ## Test STR endpoints
	@set -a && source ./.env && source ./tmp/.credentials && set +a && set -o pipefail && \
	OUTPUT_FILE=$$(mktemp) && \
	trap "rm -f $$OUTPUT_FILE" EXIT && \
	echo "🏘️  Testing STR endpoints..." && \
	echo "BACKEND_BASE_URL: $$BACKEND_BASE_URL" && \
	echo "" && \
	if CLIENT_ID=$$STR_CLIENT_ID CLIENT_SECRET=$$STR_CLIENT_SECRET ./tests/test_auth_client.sh; then \
		echo "✅ STR client authorized"; \
	else \
		echo "❌ STR client authorization failed"; \
		exit 1; \
	fi && \
	./tests/test_health_ping.sh 2>&1 | tee $$OUTPUT_FILE && \
	./tests/test_str_areas.sh 2>&1 | tee $$OUTPUT_FILE && \
	./tests/test_str_activities.sh 2>&1 | tee $$OUTPUT_FILE && \
	echo "✅ STR endpoints tested"

test-verbose: .is-up .get-client-credentials ## Test all (verbose)
	@set -a && source ./.env && source ./tmp/.credentials && set +a && set -o pipefail && \
	RESULTS_FILE=$$(mktemp) && \
	FAILED_TESTS_FILE=$$(mktemp) && \
	OUTPUT_FILE=$$(mktemp) && \
	SUITE_RESULTS_FILE=$$(mktemp) && \
	PRE_COUNTS_FILE=$$(mktemp) && \
	POST_COUNTS_FILE=$$(mktemp) && \
	trap "rm -f $$RESULTS_FILE $$FAILED_TESTS_FILE $$OUTPUT_FILE $$SUITE_RESULTS_FILE $$PRE_COUNTS_FILE $$POST_COUNTS_FILE" EXIT && \
	echo "🧪 Running all tests..." && \
	echo "" && \
	echo "📊 Capturing PRE-test row counts..." && \
	docker exec -i sdep-postgres psql -U $$POSTGRES_SUPER_USER -d $$POSTGRES_DB_NAME \
		-t -A -F'|' < postgres/count-app.sql > $$PRE_COUNTS_FILE && \
	while IFS='|' read -r tname tcount; do \
		printf "    %-25s %s\n" "$$tname:" "$$tcount"; \
	done < $$PRE_COUNTS_FILE && \
	echo "" && \
	if $(MAKE) --no-print-directory test-security 2>&1 | tee $$OUTPUT_FILE; then \
		grep -E "^\s*(Total|Passed|Failed):" $$OUTPUT_FILE >> $$RESULTS_FILE || true; \
	else \
		grep -E "^\s*(Total|Passed|Failed):" $$OUTPUT_FILE >> $$RESULTS_FILE || true; \
		echo "test-security" >> $$FAILED_TESTS_FILE; \
	fi && \
	S_TOTAL=$$(grep "Total:" $$OUTPUT_FILE 2>/dev/null | awk '{sum += $$2} END {print sum+0}') && \
	S_PASSED=$$(grep "Passed:" $$OUTPUT_FILE 2>/dev/null | awk '{sum += $$2} END {print sum+0}') && \
	S_FAILED=$$(grep "Failed:" $$OUTPUT_FILE 2>/dev/null | awk '{sum += $$2} END {print sum+0}') && \
	S_ICON=$$(if [ "$$S_FAILED" -gt 0 ] 2>/dev/null; then echo "❌"; else echo "✅"; fi) && \
	printf "📋 test-security:  %3d total, %3d passed, %d failed %s\n" "$$S_TOTAL" "$$S_PASSED" "$$S_FAILED" "$$S_ICON" && \
	printf "test-security|%d|%d|%d\n" "$$S_TOTAL" "$$S_PASSED" "$$S_FAILED" >> $$SUITE_RESULTS_FILE && \
	echo "" && \
	if $(MAKE) --no-print-directory test-str 2>&1 | tee $$OUTPUT_FILE; then \
		grep -E "^\s*(Total|Passed|Failed):" $$OUTPUT_FILE >> $$RESULTS_FILE || true; \
	else \
		grep -E "^\s*(Total|Passed|Failed):" $$OUTPUT_FILE >> $$RESULTS_FILE || true; \
		echo "test-str" >> $$FAILED_TESTS_FILE; \
	fi && \
	S_TOTAL=$$(grep "Total:" $$OUTPUT_FILE 2>/dev/null | awk '{sum += $$2} END {print sum+0}') && \
	S_PASSED=$$(grep "Passed:" $$OUTPUT_FILE 2>/dev/null | awk '{sum += $$2} END {print sum+0}') && \
	S_FAILED=$$(grep "Failed:" $$OUTPUT_FILE 2>/dev/null | awk '{sum += $$2} END {print sum+0}') && \
	S_ICON=$$(if [ "$$S_FAILED" -gt 0 ] 2>/dev/null; then echo "❌"; else echo "✅"; fi) && \
	printf "📋 test-str:       %3d total, %3d passed, %d failed %s\n" "$$S_TOTAL" "$$S_PASSED" "$$S_FAILED" "$$S_ICON" && \
	printf "test-str|%d|%d|%d\n" "$$S_TOTAL" "$$S_PASSED" "$$S_FAILED" >> $$SUITE_RESULTS_FILE && \
	echo "" && \
	if $(MAKE) --no-print-directory test-ca 2>&1 | tee $$OUTPUT_FILE; then \
		grep -E "^\s*(Total|Passed|Failed):" $$OUTPUT_FILE >> $$RESULTS_FILE || true; \
	else \
		grep -E "^\s*(Total|Passed|Failed):" $$OUTPUT_FILE >> $$RESULTS_FILE || true; \
		echo "test-ca" >> $$FAILED_TESTS_FILE; \
	fi && \
	S_TOTAL=$$(grep "Total:" $$OUTPUT_FILE 2>/dev/null | awk '{sum += $$2} END {print sum+0}') && \
	S_PASSED=$$(grep "Passed:" $$OUTPUT_FILE 2>/dev/null | awk '{sum += $$2} END {print sum+0}') && \
	S_FAILED=$$(grep "Failed:" $$OUTPUT_FILE 2>/dev/null | awk '{sum += $$2} END {print sum+0}') && \
	S_ICON=$$(if [ "$$S_FAILED" -gt 0 ] 2>/dev/null; then echo "❌"; else echo "✅"; fi) && \
	printf "📋 test-ca:        %3d total, %3d passed, %d failed %s\n" "$$S_TOTAL" "$$S_PASSED" "$$S_FAILED" "$$S_ICON" && \
	printf "test-ca|%d|%d|%d\n" "$$S_TOTAL" "$$S_PASSED" "$$S_FAILED" >> $$SUITE_RESULTS_FILE && \
	echo "" && \
	echo "🧹 Cleaning sdep-test-* data..." && \
	docker exec -i sdep-postgres psql -U $$POSTGRES_SUPER_USER -d $$POSTGRES_DB_NAME \
		-v ON_ERROR_STOP=1 < postgres/clean-testrun.sql && \
	echo "📊 Capturing POST-test row counts..." && \
	docker exec -i sdep-postgres psql -U $$POSTGRES_SUPER_USER -d $$POSTGRES_DB_NAME \
		-t -A -F'|' < postgres/count-app.sql > $$POST_COUNTS_FILE && \
	while IFS='|' read -r tname tcount; do \
		printf "    %-25s %s\n" "$$tname:" "$$tcount"; \
	done < $$POST_COUNTS_FILE && \
	echo "" && \
	SUITE_COUNT=$$(grep -c "Total:" $$RESULTS_FILE 2>/dev/null || echo 0) && \
	GRAND_TOTAL=$$(grep "Total:" $$RESULTS_FILE 2>/dev/null | awk '{sum += $$2} END {print sum+0}') && \
	GRAND_PASSED=$$(grep "Passed:" $$RESULTS_FILE 2>/dev/null | awk '{sum += $$2} END {print sum+0}') && \
	GRAND_FAILED=$$(grep "Failed:" $$RESULTS_FILE 2>/dev/null | awk '{sum += $$2} END {print sum+0}') && \
	SUITES_FAILED=$$(if [ -s $$FAILED_TESTS_FILE ]; then wc -l < $$FAILED_TESTS_FILE; else echo 0; fi) && \
	ISOLATION_OK=true && \
	echo "" && \
	echo "══ TEST RESULTS ══════════════════════════════" && \
	echo "" && \
	echo "  Suite Results:" && \
	while IFS='|' read -r SNAME STOT SPAS SFAI; do \
		SICO=$$(if [ "$$SFAI" -gt 0 ] 2>/dev/null; then echo "❌"; else echo "✅"; fi) && \
		printf "    %-18s %3d total, %3d passed, %d failed %s\n" "$$SNAME:" "$$STOT" "$$SPAS" "$$SFAI" "$$SICO"; \
	done < $$SUITE_RESULTS_FILE && \
	echo "" && \
	echo "  Grand Total:" && \
	echo "    Test suites:  $$SUITE_COUNT" && \
	echo "    Total tests:  $$GRAND_TOTAL" && \
	echo "    Tests passed: $$GRAND_PASSED ✅" && \
	echo "    Tests failed: $$GRAND_FAILED ❌" && \
	echo "" && \
	echo "  Test Isolation (PRE/POST row counts):" && \
	while IFS='|' read -r PRE_NAME PRE_COUNT; do \
		POST_COUNT=$$(grep "^$$PRE_NAME|" $$POST_COUNTS_FILE | cut -d'|' -f2) && \
		if [ "$$PRE_COUNT" = "$$POST_COUNT" ]; then \
			printf "    %-25s PRE=%-5s POST=%-5s ✅\n" "$$PRE_NAME:" "$$PRE_COUNT" "$$POST_COUNT"; \
		else \
			printf "    %-25s PRE=%-5s POST=%-5s ❌\n" "$$PRE_NAME:" "$$PRE_COUNT" "$$POST_COUNT"; \
			ISOLATION_OK=false; \
		fi; \
	done < $$PRE_COUNTS_FILE && \
	echo "" && \
	if [ "$$ISOLATION_OK" != "true" ]; then \
		echo "test-isolation" >> $$FAILED_TESTS_FILE; \
	fi && \
	if [ -s $$FAILED_TESTS_FILE ] || [ "$$GRAND_FAILED" -gt 0 ]; then \
		if [ -s $$FAILED_TESTS_FILE ]; then \
			echo "  Failed test suites:" && \
			while read -r test; do echo "    ❌ $$test"; done < $$FAILED_TESTS_FILE && \
			echo ""; \
		fi && \
		echo "  ❌ Some test (suites) failed!" && \
		exit 1; \
	else \
		echo "  ✅ All tests passed!"; \
	fi

test: .is-up ## Test all (quiet)
	@set -a && source ./.env && set +a && \
	set -o pipefail && \
	$(MAKE) --no-print-directory test-verbose 2>&1 | sed -n '/^══ TEST RESULTS/,$$p'

##@ Help

help: ## Show help
	@echo "🤖 Make"
	@echo ""
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-40s\033[0m  %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
