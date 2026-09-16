-include local.mk
export DATALAKE_PYTHON GUTEN_ROOT SERVICE ARCHIVE_ROOT ARCHIVE TARGET
.DEFAULT_GOAL := help
.PHONY: help status up run check build backup restore
help status up run check build backup restore:
	@python3 -B scripts/dev.py $@
