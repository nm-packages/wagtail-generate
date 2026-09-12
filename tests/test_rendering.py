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


@pytest.mark.parametrize("database", ["sqlite3", "postgresql", "mysql"])
@pytest.mark.parametrize("source_directory", [".", "src"])
def test_readme_documents_administrator_creation_for_each_workflow(
    database: str, source_directory: str
) -> None:
    content = render_template(
        "README.md.jinja",
        {
            "site_name": "Example",
            "project_name": "example",
            "layout": "standard",
            "source_directory": source_directory,
            "settings_module": (
                "example.settings" if source_directory == "." else "src.settings"
            ),
            "database": database,
            "database_name": database,
            "python_version": "3.14",
        },
    )

    quick_start = content.split("## Quick start", 1)[1].split("## Docker setup", 1)[0]
    local_setup = content.split("## Local UV setup", 1)[1].split(
        "## Quality checks", 1
    )[0]
    for section in (quick_start, local_setup):
        assert "make superuser" in section
        assert "http://localhost:8000/admin/" in section
        assert "another terminal" in section
        assert "project root" in section
        assert "docker compose" not in section
        assert section.index("make dev") < section.index("make superuser")

    docker_setup = content.split("## Docker setup", 1)[1].split("## Local UV setup", 1)[
        0
    ]
    assert "docker compose exec web python manage.py createsuperuser" in docker_setup
    assert "make superuser" not in docker_setup


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


@pytest.mark.parametrize("database", ["sqlite3", "postgresql", "mysql"])
@pytest.mark.parametrize("source_directory", [".", "src"])
def test_agent_guidance_matches_generated_environment(
    database: str, source_directory: str
) -> None:
    settings_module = "example.settings" if source_directory == "." else "src.settings"
    context = {
        "site_name": "Example",
        "template_description": "the standard layout",
        "project_name": "example",
        "layout": "standard",
        "source_directory": source_directory,
        "settings_module": settings_module,
        "database": database,
    }
    content = render_template("AGENTS.md.jinja", context)
    assert len(content.splitlines()) <= 60
    assert "docker compose run --rm web uv run ruff" not in content
    for name in ("environment", "backend", "checks"):
        path = f"docs/agent-instructions/{name}.md"
        assert f"]({path})" in content
        content += render_template(f"{path}.jinja", context)

    assert f"Site source directory: `{source_directory}`" in content
    assert f"Django settings package: `{settings_module}`" in content
    assert "project root, where `manage.py` and `compose.yaml` live" in content
    assert "Django's built-in test runner" in content
    for command in (
        "uv lock --check",
        "uv run ruff check .",
        "uv run ruff format --check .",
        "uv run python scripts/check_django_templates.py",
        "uv run python manage.py check",
        "uv run python manage.py makemigrations --check --dry-run",
        "uv run python manage.py test",
    ):
        assert f"docker compose run --rm web {command}" in content
    if database == "sqlite3":
        assert "`db.sqlite3`" in content
        assert "make database" not in content
        assert "DATABASE_HOST" not in content
    else:
        assert "`db.sqlite3`" not in content
        assert "make database" in content
        assert "uv run --env-file .env" in content
        assert "exported shell variables taking precedence" in content
        assert f"project uses `{database}`" in content


@pytest.mark.parametrize("database", ["sqlite3", "postgresql", "mysql"])
@pytest.mark.parametrize("source_directory", [".", "src"])
def test_readme_preserves_markdown_spacing_without_extra_blank_lines(
    database: str, source_directory: str
) -> None:
    content = render_template(
        "README.md.jinja",
        {
            "site_name": "Example",
            "project_name": "example",
            "layout": "standard",
            "source_directory": source_directory,
            "settings_module": "example.settings",
            "database": database,
            "database_name": database,
            "python_version": "3.14",
        },
    )

    assert "\n\n\n" not in content
    assert content.endswith(".\n")
    lines = content.splitlines()
    in_code_block = False
    for index, line in enumerate(lines):
        if line.startswith("## "):
            assert lines[index - 1] == lines[index + 1] == ""
        if line.startswith("```"):
            if in_code_block:
                assert lines[index + 1] == ""
            else:
                assert lines[index - 1] == ""
            in_code_block = not in_code_block
    assert not in_code_block
    if database == "mysql":
        assert "\n\n> [!NOTE]\n> Django warns" in content
        assert "setup error.\n\n## Local UV setup" in content
    else:
        assert "> [!NOTE]" not in content
