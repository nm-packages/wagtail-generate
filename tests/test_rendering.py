"""Tests for packaged template loading and strict rendering."""

from pathlib import Path

import pytest
from jinja2 import UndefinedError

from wagtail_generate.rendering import render_template, template_text, write_template


def test_packaged_static_template_can_be_read() -> None:
    content = template_text("static/pre-commit-config.yaml")

    assert "Validate UV lockfile" in content
    assert "Format Django templates" in content


def test_rendering_requires_every_template_value() -> None:
    with pytest.raises(UndefinedError):
        render_template("env/postgresql.example.jinja", {})


def test_write_template_renders_content_and_applies_mode(tmp_path: Path) -> None:
    destination = tmp_path / "Dockerfile"

    write_template(
        destination,
        "Dockerfile.jinja",
        {
            "python_version": "3.12",
            "settings_module": "src.settings",
            "wsgi_module": "src",
            "build_database_packages": "libpq-dev",
            "runtime_database_packages": "libpq5",
        },
        mode=0o700,
    )

    assert "DJANGO_SETTINGS_MODULE=src.settings.dev" in destination.read_text()
    assert destination.stat().st_mode & 0o777 == 0o700
