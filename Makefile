-include .env
export

export PROJECT_ROOT=$(shell pwd)

.PHONY: up down cleanup migrate-up migrate-down migrate-action migrate-create run parse ingest

run:
	@uv run python ${PROJECT_ROOT}/src/mling/__init__.py

parse:
	@uv run mling-bookparse-test $(book)

ingest:
	@if [ -z "$(book)" ]; then \
		echo "book is not specified. Example: make ingest book=books/the-great-gatsby.pdf"; \
		exit 1; \
	fi
	@uv run mling-ingest $(book) $(args)

up:
	@docker compose up -d

down:
	@docker compose down --remove-orphans

cleanup:
	@read -p "Remove Compose containers, networks and volumes? [y/N] " ans; \
	if [ "$$ans" = "y" ]; then \
		docker compose down -v; \
	else \
		echo "Aborted."; \
	fi

migrate-up:
	@$(MAKE) migrate-action action=up

migrate-down:
	@$(MAKE) migrate-action action=down

migrate-action:
	@if [ -z "$(action)" ]; then \
		echo "action is not specified. Example: make migrate-action action=up"; \
		exit 1; \
	fi
	@docker compose run --rm migrate \
		-path /migrations \
		-database "postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}?sslmode=disable" \
		-lock-timeout $(MIGRATE_LOCK_TIMEOUT) \
		"$(action)"

migrate-create:
	@if [ -z "$(seq)" ]; then \
		echo "seq parameter is not specified. Example: make migrate-create seq=init"; \
		exit 1; \
	fi
	@docker compose run --rm migrate \
		create \
		-ext sql \
		-dir /migrations \
		-seq "$(seq)"