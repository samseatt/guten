-include local.mk
export DATALAKE_PYTHON GUTEN_ROOT SERVICE ARCHIVE_ROOT ARCHIVE TARGET DATABASE ALLOW_MASTER TEST_DATABASE
.DEFAULT_GOAL := help
.PHONY: help status up run check build backup restore migrate test seed-publications
help status up run check build backup restore migrate test seed-publications:
	@python3 -B scripts/dev.py $@
