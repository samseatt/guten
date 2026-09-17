-include local.mk
export DATALAKE_PYTHON GUTEN_ROOT SERVICE ARCHIVE_ROOT ARCHIVE TARGET DATABASE ALLOW_MASTER TEST_DATABASE
.DEFAULT_GOAL := help
.PHONY: help status up run check build backup restore migrate test seed-publications acceptance test-db
help status up run check build backup restore migrate test seed-publications acceptance test-db:
	@python3 -B scripts/dev.py $@

DOCKER_TASKS := docker-setup docker-db-up docker-db-stop docker-build docker-init-test docker-up docker-stop docker-down docker-status docker-logs docker-config docker-test docker-test-lifecycle
.PHONY: $(DOCKER_TASKS)
$(DOCKER_TASKS):
	@python3 -B scripts/compose.py $@
