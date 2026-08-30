"""Tests for the Wagtail command integration."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from wagtail_generate.wagtail import run_wagtail_start


@patch("wagtail_generate.wagtail.subprocess.run")
def test_run_wagtail_start_streams_native_command(
    run: Mock,
    tmp_path: Path,
) -> None:
    run.return_value = subprocess.CompletedProcess([], returncode=0)
    project_root = tmp_path / "generated"
    project_root.mkdir()
    (project_root / "pyproject.toml").write_text(
        '[project]\nname = "example"\nversion = "0.1.0"\n'
    )
    site_directory = project_root / "site"
    site_directory.mkdir()
    moved_root_files = (".dockerignore", "Dockerfile", "manage.py")
    generated_root_files = (*moved_root_files, "requirements.txt")
    for filename in generated_root_files:
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
    migration = migrations / "0002_create_homepage.py"
    migration.write_text('HomePage = apps.get_model("home.HomePage")')

    result = run_wagtail_start(
        "example",
        site_name="Example website",
        database="postgresql",
        project_root=project_root,
        site_subfolder=Path("site"),
        template=Path("custom-template"),
    )

    assert result == 0
    assert (project_root / "site").is_dir()
    for filename in moved_root_files:
        assert (project_root / filename).is_file()
        assert not (site_directory / filename).exists()
    assert not (project_root / "requirements.txt").exists()
    assert not (site_directory / "requirements.txt").exists()
    assert not (site_directory / "README.md").exists()
    readme = (project_root / "README.md").read_text()
    assert readme.startswith("# Example website")
    assert "Site source: `site`" in readme
    assert "Django settings: `site.settings`" in readme
    assert "Database: PostgreSQL" in readme
    assert "make dev" in readme
    assert "make docker" in readme
    assert "make check" in readme
    assert "git init" in readme
    assert "git add --all" in readme
    assert "uv run pre-commit install" in readme
    agents = (project_root / "AGENTS.md").read_text()
    assert "Example website" in agents
    assert "Python project package: `example`" in agents
    assert "Site source directory: `site`" in agents
    assert "Django settings package: `site.settings`" in agents
    assert "Database: `postgresql`" in agents
    assert "custom template `custom-template`" in agents
    assert "postgres:17-bookworm" in (project_root / "compose.yaml").read_text()
    assert (project_root / "Makefile").is_file()
    assert "uv sync --locked" in (project_root / "Dockerfile").read_text()
    assert (project_root / ".pre-commit-config.yaml").is_file()
    assert "[tool.djangofmt]" in (project_root / "pyproject.toml").read_text()
    assert (project_root / ".env.example").is_file()
    assert not package_directory.exists()
    assert (site_directory / "settings" / "base.py").is_file()
    assert "site.settings.dev" in (project_root / "manage.py").read_text()
    settings = (site_directory / "settings" / "base.py").read_text()
    assert '"site.home"' in settings
    assert '"site.search"' in settings
    assert '"site.urls"' in settings
    assert 'WAGTAIL_SITE_NAME = "Example website"' in settings
    assert '"ENGINE": "django.db.backends.postgresql"' in settings
    assert '"django.contrib.postgres"' in settings
    assert 'os.environ.get("DATABASE_HOST", "127.0.0.1")' in settings
    assert (home_directory / "apps.py").read_text() == '    name = "site.home"'
    assert (home_directory / "tests.py").read_text() == (
        "from site.home.models import HomePage"
    )
    assert migration.read_text() == 'HomePage = apps.get_model("home.HomePage")'
    assert run.call_args_list == [
        (
            (
                [
                    "uv",
                    "init",
                    "--bare",
                    "--no-workspace",
                    "--python",
                    "3.12",
                    "--name",
                    "example",
                ],
            ),
            {"cwd": project_root, "check": False},
        ),
        (
            (["uv", "python", "pin", "3.12"],),
            {"cwd": project_root, "check": False},
        ),
        (
            (["uv", "add", "wagtail", "gunicorn", "psycopg[binary]"],),
            {"cwd": project_root, "check": False},
        ),
        (
            (["uv", "add", "--dev", "ruff", "djangofmt", "pre-commit"],),
            {"cwd": project_root, "check": False},
        ),
        (
            (
                [
                    "uv",
                    "run",
                    "wagtail",
                    "start",
                    "example",
                    "site",
                    "--template=custom-template",
                ],
            ),
            {"cwd": project_root, "check": False},
        ),
        (
            (["uv", "run", "djangofmt", "site"],),
            {"cwd": project_root, "check": False},
        ),
        (
            (["uv", "run", "ruff", "check", "--fix", "site"],),
            {"cwd": project_root, "check": False},
        ),
        (
            (["uv", "run", "ruff", "format", "site", "manage.py"],),
            {"cwd": project_root, "check": False},
        ),
    ]


@patch("wagtail_generate.wagtail.subprocess.run")
def test_run_wagtail_start_stops_after_failed_uv_command(run: Mock) -> None:
    run.return_value = subprocess.CompletedProcess([], returncode=2)

    assert run_wagtail_start("example", project_root=Path("generated")) == 2
    run.assert_called_once_with(
        [
            "uv",
            "init",
            "--bare",
            "--no-workspace",
            "--python",
            "3.12",
            "--name",
            "example",
        ],
        cwd=Path("generated"),
        check=False,
    )


@patch("wagtail_generate.wagtail.subprocess.run")
def test_run_wagtail_start_defaults_to_sqlite_without_driver(run: Mock) -> None:
    run.side_effect = [
        subprocess.CompletedProcess([], returncode=0),
        subprocess.CompletedProcess([], returncode=0),
        subprocess.CompletedProcess([], returncode=1),
    ]

    assert run_wagtail_start("example", project_root=Path("generated")) == 1
    assert run.call_args_list[2] == (
        (["uv", "add", "wagtail", "gunicorn"],),
        {"cwd": Path("generated"), "check": False},
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
        site_subfolder=Path("site"),
    )

    assert result == 2
    assert "manage.py" in capsys.readouterr().err
    assert (tmp_path / "manage.py").read_text() == "existing"
    run.assert_not_called()
