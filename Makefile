.DEFAULT_GOAL := help
SITE_DIRECTORY ?= .
export SITE_DIRECTORY

.PHONY: help playground playground-reset

help:
	@echo "make playground        Rebuild .playground, migrate, check, and serve on port 8000"
	@echo "make playground SITE_DIRECTORY=src  Exercise the source-subfolder layout"
	@echo "make playground-reset  Delete the generated playground"

playground:
	uv run python -m wagtail_generate.playground --site-directory "$$SITE_DIRECTORY"

playground-reset:
	uv run python -m wagtail_generate.playground --reset
