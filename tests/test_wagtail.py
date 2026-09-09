"""Tests for the Wagtail command integration."""

import subprocess
from pathlib import Path
from typing import cast
from unittest.mock import Mock, patch

import pytest

from wagtail_generate.wagtail import (
    _flatten_project_package,
    latest_stable_python_version,
    run_wagtail_start,
)


@pytest.mark.parametrize(
    ("project_name", "subfolder"),
    [("site", None), ("example", Path("site")), ("example", Path("json/cms"))],
)
@patch("wagtail_generate.wagtail.subprocess.run")
def test_source_package_conflict_is_rejected_before_external_commands(
    run: Mock,
    project_name: str,
    subfolder: Path | None,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    destination = tmp_path / "generated"
    assert (
        run_wagtail_start(
            project_name, project_root=destination, site_subfolder=subfolder
        )
        == 2
    )
    assert "conflicts with Python's standard library" in capsys.readouterr().err
    assert not destination.exists()
    run.assert_not_called()


def write_mock_wagtail_project(project_root: Path) -> None:
    """Create the relevant subset of Wagtail's default generated tree."""
    (project_root / "pyproject.toml").write_text(
        '[project]\nname = "example"\nversion = "0.1.0"\n'
    )
    site_directory = project_root / "src"
    moved_root_files = (".dockerignore", "Dockerfile", "manage.py")
    for filename in (*moved_root_files, "requirements.txt"):
        content = (
            'os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example.settings.dev")'
        )
        (site_directory / filename).write_text(
            content if filename == "manage.py" else filename
        )
    (site_directory / "README.md").write_text("Wagtail's generated README")
    package_directory = site_directory / "example"
    (package_directory / "settings").mkdir(parents=True)
    (package_directory / "__init__.py").write_text("")
    (package_directory / "settings" / "base.py").write_text(
        "from pathlib import Path\n\n"
        "INSTALLED_APPS = [\n"
        '    "home",\n'
        '    "search",\n'
        "]\n"
        'ROOT_URLCONF = "example.urls"\n'
        'WAGTAIL_SITE_NAME = "example"\n'
        "DATABASES = {\n"
        '    "default": {\n'
        '        "ENGINE": "django.db.backends.sqlite3",\n'
        '        "NAME": "db.sqlite3",\n'
        "    }\n"
        "}\n"
    )
    (package_directory / "urls.py").write_text("")
    home_directory = site_directory / "home"
    home_directory.mkdir()
    (home_directory / "apps.py").write_text('    name = "home"')
    (home_directory / "tests.py").write_text("from home.models import HomePage")
    migrations = home_directory / "migrations"
    migrations.mkdir()
    (migrations / "0002_create_homepage.py").write_text(
        'HomePage = apps.get_model("home.HomePage")'
    )


@patch(
    "wagtail_generate.wagtail.latest_stable_python_version",
    return_value="3.14",
)
@patch("wagtail_generate.wagtail.subprocess.run")
def test_run_wagtail_start_streams_native_command(
    run: Mock,
    resolve_python: Mock,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "generated"

    def run_command(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess:
        if "wagtail" in command and "start" in command:
            write_mock_wagtail_project(cast(Path, kwargs["cwd"]))
        return subprocess.CompletedProcess(command, returncode=0)

    run.side_effect = run_command

    result = run_wagtail_start(
        "example",
        site_name="Example website",
        database="postgresql",
        project_root=project_root,
        site_subfolder=Path("src"),
        template=Path("custom-template"),
    )

    assert result == 0
    site_directory = project_root / "src"
    moved_root_files = (".dockerignore", "Dockerfile", "manage.py")
    package_directory = site_directory / "example"
    home_directory = site_directory / "home"
    migration = home_directory / "migrations" / "0002_create_homepage.py"
    assert (project_root / "src").is_dir()
    for filename in moved_root_files:
        assert (project_root / filename).is_file()
        assert not (site_directory / filename).exists()
    assert not (project_root / "requirements.txt").exists()
    assert not (site_directory / "requirements.txt").exists()
    assert not (site_directory / "README.md").exists()
    readme = (project_root / "README.md").read_text()
    assert readme.startswith("# Example website")
    assert "Site source: `src`" in readme
    assert "Django settings: `src.settings`" in readme
    assert "Codebase layout: `standard`" in readme
    assert "Database: PostgreSQL" in readme
    assert "Python: 3.14" in readme
    assert "cp .env.example .env\nmake dev" in readme
    assert "make dev" in readme
    assert "make docker" in readme
    assert "make check" in readme
    assert "git init" in readme
    assert "git add --all" in readme
    assert "uv run pre-commit install" in readme
    agents = (project_root / "AGENTS.md").read_text()
    assert "Example website" in agents
    assert "Python project package: `example`" in agents
    assert "Codebase layout: `standard`" in agents
    assert "Site source directory: `src`" in agents
    assert "Django settings package: `src.settings`" in agents
    assert "Database: `postgresql`" in agents
    assert "custom template `custom-template`" in agents
    assert "postgres:17-bookworm" in (project_root / "compose.yaml").read_text()
    assert (project_root / "Makefile").is_file()
    assert "uv sync --locked" in (project_root / "Dockerfile").read_text()
    assert (
        "FROM python:3.14-slim AS development"
        in (project_root / "Dockerfile").read_text()
    )
    assert (project_root / ".pre-commit-config.yaml").is_file()
    assert (project_root / "scripts" / "check_django_templates.py").is_file()
    assert "[tool.djangofmt]" in (project_root / "pyproject.toml").read_text()
    assert 'target-version = "py314"' in (project_root / "pyproject.toml").read_text()
    assert (project_root / ".env.example").is_file()
    assert not package_directory.exists()
    assert (site_directory / "settings" / "base.py").is_file()
    assert "src.settings.dev" in (project_root / "manage.py").read_text()
    settings = (site_directory / "settings" / "base.py").read_text()
    assert '"src.home"' in settings
    assert '"src.search"' in settings
    assert '"src.urls"' in settings
    assert 'WAGTAIL_SITE_NAME = "Example website"' in settings
    assert '"ENGINE": "django.db.backends.postgresql"' in settings
    assert '"django.contrib.postgres"' in settings
    assert 'os.environ.get("DATABASE_HOST", "127.0.0.1")' in settings
    assert (home_directory / "apps.py").read_text() == '    name = "src.home"'
    assert (home_directory / "tests.py").read_text() == (
        "from src.home.models import HomePage"
    )
    assert migration.read_text() == 'HomePage = apps.get_model("home.HomePage")'
    generation_directory = run.call_args_list[0].kwargs["cwd"]
    assert generation_directory.parent == tmp_path
    assert run.call_args_list == [
        (
            (
                [
                    "uvx",
                    "uv@0.12.7",
                    "init",
                    "--bare",
                    "--no-workspace",
                    "--python",
                    "3.14",
                    "--name",
                    "example",
                ],
            ),
            {"cwd": generation_directory, "check": False},
        ),
        (
            (["uvx", "uv@0.12.7", "python", "pin", "3.14"],),
            {"cwd": generation_directory, "check": False},
        ),
        (
            (["uvx", "uv@0.12.7", "add", "wagtail", "psycopg[binary]"],),
            {"cwd": generation_directory, "check": False},
        ),
        (
            (
                [
                    "uvx",
                    "uv@0.12.7",
                    "add",
                    "--dev",
                    "ruff",
                    "djangofmt",
                    "pre-commit",
                ],
            ),
            {"cwd": generation_directory, "check": False},
        ),
        (
            (
                [
                    "uvx",
                    "uv@0.12.7",
                    "run",
                    "wagtail",
                    "start",
                    "example",
                    "src",
                    "--template=custom-template",
                ],
            ),
            {"cwd": generation_directory, "check": False},
        ),
        (
            (["uvx", "uv@0.12.7", "run", "djangofmt", "src"],),
            {"cwd": generation_directory, "check": False},
        ),
        (
            (["uvx", "uv@0.12.7", "run", "ruff", "check", "--fix", "src"],),
            {"cwd": generation_directory, "check": False},
        ),
        (
            (
                [
                    "uvx",
                    "uv@0.12.7",
                    "run",
                    "ruff",
                    "format",
                    "src",
                    "manage.py",
                ],
            ),
            {"cwd": generation_directory, "check": False},
        ),
    ]
    resolve_python.assert_called_once_with(tmp_path)


@patch(
    "wagtail_generate.wagtail.latest_stable_python_version",
    return_value="3.14",
)
@patch("wagtail_generate.wagtail.subprocess.run")
def test_run_wagtail_start_stops_after_failed_uv_command(
    run: Mock,
    resolve_python: Mock,
    tmp_path: Path,
) -> None:
    run.return_value = subprocess.CompletedProcess([], returncode=2)
    project_root = tmp_path / "generated"

    assert run_wagtail_start("example", project_root=project_root) == 2
    generation_directory = run.call_args.kwargs["cwd"]
    run.assert_called_once_with(
        [
            "uvx",
            "uv@0.12.7",
            "init",
            "--bare",
            "--no-workspace",
            "--python",
            "3.14",
            "--name",
            "example",
        ],
        cwd=generation_directory,
        check=False,
    )
    assert generation_directory.parent == tmp_path
    assert not project_root.exists()
    resolve_python.assert_called_once_with(tmp_path)


@patch(
    "wagtail_generate.wagtail.latest_stable_python_version",
    return_value="3.14",
)
@patch("wagtail_generate.wagtail.subprocess.run")
def test_run_wagtail_start_defaults_to_sqlite_without_driver(
    run: Mock,
    resolve_python: Mock,
    tmp_path: Path,
) -> None:
    run.side_effect = [
        subprocess.CompletedProcess([], returncode=0),
        subprocess.CompletedProcess([], returncode=0),
        subprocess.CompletedProcess([], returncode=1),
    ]

    project_root = tmp_path / "generated"

    assert run_wagtail_start("example", project_root=project_root) == 1
    generation_directory = run.call_args_list[0].kwargs["cwd"]
    assert run.call_args_list[2] == (
        (["uvx", "uv@0.12.7", "add", "wagtail"],),
        {"cwd": generation_directory, "check": False},
    )
    assert generation_directory.parent == tmp_path
    assert not project_root.exists()
    resolve_python.assert_called_once_with(tmp_path)


@patch(
    "wagtail_generate.wagtail.latest_stable_python_version",
    return_value="3.14",
)
@patch("wagtail_generate.wagtail.subprocess.run")
def test_late_command_failure_does_not_publish_partial_project(
    run: Mock,
    resolve_python: Mock,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "generated"

    def run_command(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess:
        if "wagtail" in command and "start" in command:
            write_mock_wagtail_project(cast(Path, kwargs["cwd"]))
        return_code = 7 if "djangofmt" in command else 0
        return subprocess.CompletedProcess(command, returncode=return_code)

    run.side_effect = run_command

    result = run_wagtail_start(
        "example",
        project_root=project_root,
        site_subfolder=Path("src"),
    )

    assert result == 7
    assert not project_root.exists()
    resolve_python.assert_called_once_with(tmp_path)


@patch("wagtail_generate.wagtail.subprocess.run")
def test_latest_stable_python_version_uses_uv_download_catalog(run: Mock) -> None:
    run.return_value = subprocess.CompletedProcess(
        [],
        returncode=0,
        stdout=(
            '[{"implementation":"cpython","variant":"default",'
            '"version":"3.14.7"},'
            '{"implementation":"cpython","variant":"default",'
            '"version":"3.15.0b1"},'
            '{"implementation":"pypy","variant":"default",'
            '"version":"3.14.8"}]'
        ),
        stderr="",
    )

    assert latest_stable_python_version(Path("generated")) == "3.14"
    run.assert_called_once_with(
        [
            "uvx",
            "uv@0.12.7",
            "python",
            "list",
            "--only-downloads",
            "--output-format",
            "json",
        ],
        cwd=Path("generated"),
        check=False,
        capture_output=True,
        text=True,
    )


@patch("wagtail_generate.wagtail.subprocess.run")
def test_subfolder_generation_refuses_root_file_conflict(
    run: Mock,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "manage.py").write_text("existing")

    result = run_wagtail_start(
        "example",
        project_root=tmp_path,
        site_subfolder=Path("src"),
    )

    assert result == 2
    assert "manage.py" in capsys.readouterr().err
    assert (tmp_path / "manage.py").read_text() == "existing"
    run.assert_not_called()


def test_nested_subfolder_keeps_base_directory_at_project_root(
    tmp_path: Path,
) -> None:
    generated_directory = tmp_path / "sites" / "example"
    package_directory = generated_directory / "example"
    settings_directory = package_directory / "settings"
    settings_directory.mkdir(parents=True)
    (settings_directory / "base.py").write_text(
        "from pathlib import Path\n\n"
        "PROJECT_DIR = Path(__file__).resolve().parent.parent\n"
        "BASE_DIR = PROJECT_DIR.parent\n\n"
        'INSTALLED_APPS = ["home", "search"]\n'
    )
    (package_directory / "__init__.py").write_text("")

    home_directory = generated_directory / "home"
    home_directory.mkdir()
    (home_directory / "apps.py").write_text('    name = "home"\n')

    result = _flatten_project_package(
        generated_directory,
        "example",
        "sites.example",
    )

    assert result
    assert (tmp_path / "sites" / "__init__.py").is_file()
    settings = (generated_directory / "settings" / "base.py").read_text()
    assert "PROJECT_DIR = Path(__file__).resolve().parent.parent" in settings
    assert "BASE_DIR = PROJECT_DIR.parent.parent" in settings
    assert 'INSTALLED_APPS = ["sites.example.home", "sites.example.search"]' in (
        settings
    )
