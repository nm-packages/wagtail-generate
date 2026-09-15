.DEFAULT_GOAL := help

.PHONY: help playground playground-reset

help:
	@echo "make playground        Rebuild and serve SQLite with src layout, starter homepage, custom users, and custom images"
	@echo "make playground-reset  Delete the generated playground"

playground:
	uv run python -m wagtail_generate.playground \
		--database sqlite3 --site-directory src \
		--starter-homepage --custom-user --custom-images

playground-reset:
	uv run python -m wagtail_generate.playground --reset
