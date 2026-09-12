"""Exercise generated Make commands with real UV and Compose dotenv parsing."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from wagtail_generate.rendering import render_template


@pytest.fixture(params=["postgresql", "mysql"])
def project(request: pytest.FixtureRequest, tmp_path: Path) -> tuple[Path, str]:
    database = str(request.param)
    context = {"database": database, "project_name": "example"}
    for destination, template in (
        ("Makefile", "Makefile.jinja"),
        ("compose.yaml", f"compose/{database}.yaml.jinja"),
        ("settings.py", f"database/{database}.py.jinja"),
    ):
        content = render_template(template, context)
        if destination == "settings.py":
            content = "import os\n" + content
        (tmp_path / destination).write_text(content)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "example"\nversion = "0.1.0"\n'
    )
    (tmp_path / "manage.py").write_text(
        "import json, sys\nfrom settings import DATABASES\n"
        "print(json.dumps({'command': sys.argv[1], **DATABASES['default']}))\n"
    )
    return tmp_path, database


def clean_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("DATABASE_", "UV_", "COMPOSE_", "MYSQL_"))
        and key not in {"VIRTUAL_ENV", "MAKEFLAGS", "MFLAGS", "WEB_PORT"}
    }
    return environment | {"UV_PYTHON": sys.executable, "UV_OFFLINE": "1"}


@pytest.mark.parametrize("source", ["defaults", "file", "shell"])
@pytest.mark.parametrize(
    ("literal", "password"),
    [
        ("'cost$5#demo with spaces'", "cost$5#demo with spaces"),
        ('"quoted password # value"', "quoted password # value"),
        ("plain#hash", "plain#hash"),
    ],
)
def test_local_make_commands_preserve_database_settings(
    project: tuple[Path, str],
    source: str,
    literal: str,
    password: str,
) -> None:
    root, database = project
    environment = clean_environment()
    if source != "defaults":
        (root / ".env").write_text(
            f"DATABASE_PASSWORD={literal}\nDATABASE_HOST=db.example.test\n"
            "DATABASE_PORT=15432\n"
        )
    if source == "shell":
        environment.update(
            DATABASE_HOST="override.example.test",
            DATABASE_PORT="25432",
            DATABASE_PASSWORD="shell$secret# with spaces",
        )
    result = subprocess.run(
        ["make", "--no-print-directory", "migrate", "superuser", "test"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    records = [
        json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")
    ]
    assert [record["command"] for record in records] == [
        "migrate",
        "createsuperuser",
        "test",
    ]
    for record in records:
        assert (
            record["HOST"]
            == {
                "defaults": "127.0.0.1",
                "file": "db.example.test",
                "shell": "override.example.test",
            }[source]
        )
        assert (
            record["PORT"]
            == {
                "defaults": "5432" if database == "postgresql" else "3306",
                "file": "15432",
                "shell": "25432",
            }[source]
        )
        assert (
            record["PASSWORD"]
            == {
                "defaults": "development",
                "file": password,
                "shell": "shell$secret# with spaces",
            }[source]
        )


@pytest.mark.parametrize("override", [False, True])
def test_compose_through_make_preserves_credentials_and_internal_host(
    project: tuple[Path, str],
    override: bool,
) -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker Compose is required for the configuration check")
    root, database = project
    environment = clean_environment()
    version = subprocess.run(
        ["docker", "compose", "version"],
        env=environment,
        capture_output=True,
        check=False,
    )
    if version.returncode:
        pytest.skip("Docker Compose is unavailable")
    password = "cost$5#demo with spaces"
    (root / ".env").write_text(
        f"DATABASE_PASSWORD='{password}'\nDATABASE_HOST=external.example.test\n"
        "DATABASE_PORT=15432\n"
    )
    if override:
        password = "shell$secret# with spaces"
        environment["DATABASE_PASSWORD"] = password
    with (root / "Makefile").open("a") as makefile:
        makefile.write("\ninspect-compose:\n\t@docker compose config --format json\n")
        makefile.write(
            "\ninspect-environment:\n\t@docker compose config --environment\n"
        )
    interpolation = subprocess.run(
        ["make", "--no-print-directory", "inspect-environment"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    assert f"DATABASE_PASSWORD={password}" in interpolation.stdout.splitlines()
    result = subprocess.run(
        ["make", "--no-print-directory", "inspect-compose"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    services = json.loads(result.stdout)["services"]
    web = services["web"]["environment"]
    # Compose escapes dollars when serializing reusable configuration.
    assert web["DATABASE_PASSWORD"] == password.replace("$", "$$")
    assert web["DATABASE_HOST"] == "db"
    port = "5432" if database == "postgresql" else "3306"
    assert str(web["DATABASE_PORT"]) == port
    key = "POSTGRES_PASSWORD" if database == "postgresql" else "MYSQL_PASSWORD"
    assert services["db"]["environment"][key] == password.replace("$", "$$")
    assert services["db"]["ports"][0]["published"] == "15432"


def test_dev_loads_environment_for_migrations_and_server(
    project: tuple[Path, str],
) -> None:
    root, _ = project
    (root / ".env").write_text(
        "DATABASE_HOST=db.example.test\nDATABASE_PASSWORD='cost$5#demo'\n"
    )
    binary_directory = root / "bin"
    binary_directory.mkdir()
    docker = binary_directory / "docker"
    docker.write_text('#!/bin/sh\nprintf "%s\\n" "$*" > docker-call.txt\n')
    docker.chmod(0o755)
    environment = clean_environment()
    environment["PATH"] = f"{binary_directory}{os.pathsep}{environment['PATH']}"
    result = subprocess.run(
        ["make", "--no-print-directory", "dev"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    records = [
        json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")
    ]
    assert [record["command"] for record in records] == ["migrate", "runserver"]
    assert all(record["HOST"] == "db.example.test" for record in records)
    assert all(record["PASSWORD"] == "cost$5#demo" for record in records)
    assert (root / "docker-call.txt").read_text() == "compose up -d --wait db\n"
