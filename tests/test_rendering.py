"""Tests for packaged template loading and strict rendering."""

from pathlib import Path

import pytest
from jinja2 import UndefinedError

from wagtail_generate.rendering import render_template, template_text, write_template


def test_packaged_static_template_can_be_read() -> None:
    content = template_text("static/pre-commit-config.yaml")

    assert "Validate UV lockfile" in content
    assert "Format Django templates" in content


def test_generated_ignore_rules_only_exclude_root_output_directories() -> None:
    content = template_text("static/gitignore")

    assert "/media/" in content
    assert "/static/" in content
    assert "\nmedia/" not in content
    assert "\nstatic/" not in content


def test_rendering_requires_every_template_value() -> None:
    with pytest.raises(UndefinedError):
        render_template("env/postgresql.example.jinja", {})


def test_sqlite_readme_quick_start_does_not_require_env_file() -> None:
    content = render_template(
        "README.md.jinja",
        {
            "site_name": "Example",
            "project_name": "example",
            "layout": "standard",
            "source_directory": ".",
            "settings_module": "example.settings",
            "database": "sqlite3",
            "database_name": "SQLite",
            "python_version": "3.14",
        },
    )

    quick_start = content.split("## Quick start", 1)[1].split("## Docker setup", 1)[0]
    assert "make dev" in quick_start
    assert "cp .env.example .env" not in quick_start


def test_write_template_renders_content_and_applies_mode(tmp_path: Path) -> None:
    destination = tmp_path / "Dockerfile"

    write_template(
        destination,
        "Dockerfile.jinja",
        {
            "python_version": "3.14",
            "settings_module": "src.settings",
            "build_database_packages": "libpq-dev",
        },
        mode=0o700,
    )

    assert "DJANGO_SETTINGS_MODULE=src.settings.dev" in destination.read_text()
    assert destination.stat().st_mode & 0o777 == 0o700
