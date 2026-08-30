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
    site_directory = project_root / "site"
    site_directory.mkdir()
    moved_root_files = (".dockerignore", "Dockerfile", "manage.py")
    generated_root_files = (*moved_root_files, "requirements.txt")
    for filename in generated_root_files:
        content = (
            'os.environ.setdefault("DJANGO_SETTINGS_MODULE", '
            '"example.settings.dev")'
        )
        (site_directory / filename).write_text(
            content if filename == "manage.py" else filename
        )
    package_directory = site_directory / "example"
    (package_directory / "settings").mkdir(parents=True)
    (package_directory / "__init__.py").write_text("")
    (package_directory / "settings" / "base.py").write_text(
        'INSTALLED_APPS = ["home", "search"]\n'
        'ROOT_URLCONF = "example.urls"\n'
        'WAGTAIL_SITE_NAME = "example"'
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
    agents = (project_root / "AGENTS.md").read_text()
    assert "Example website" in agents
    assert "Python project package: `example`" in agents
    assert "Site source directory: `site`" in agents
    assert "Django settings package: `site.settings`" in agents
    assert "custom template `custom-template`" in agents
    assert not package_directory.exists()
    assert (site_directory / "settings" / "base.py").is_file()
    assert "site.settings.dev" in (project_root / "manage.py").read_text()
    settings = (site_directory / "settings" / "base.py").read_text()
    assert '"site.home"' in settings
    assert '"site.search"' in settings
    assert '"site.urls"' in settings
    assert 'WAGTAIL_SITE_NAME = "Example website"' in settings
    assert (home_directory / "apps.py").read_text() == '    name = "site.home"'
    assert (home_directory / "tests.py").read_text() == (
        "from site.home.models import HomePage"
    )
    assert migration.read_text() == 'HomePage = apps.get_model("home.HomePage")'
    assert run.call_args_list == [
        (
            (["uv", "init", "--bare", "--no-workspace"],),
            {"cwd": project_root, "check": False},
        ),
        ((["uv", "add", "wagtail"],), {"cwd": project_root, "check": False}),
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
    ]


@patch("wagtail_generate.wagtail.subprocess.run")
def test_run_wagtail_start_stops_after_failed_uv_command(run: Mock) -> None:
    run.return_value = subprocess.CompletedProcess([], returncode=2)

    assert run_wagtail_start("example", project_root=Path("generated")) == 2
    run.assert_called_once_with(
        ["uv", "init", "--bare", "--no-workspace"],
        cwd=Path("generated"),
        check=False,
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
