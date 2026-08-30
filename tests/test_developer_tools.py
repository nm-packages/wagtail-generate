"""Tests for generated development tooling."""

from pathlib import Path

from wagtail_generate.developer_tools import (
    configure_database,
    database_driver,
    write_developer_tooling,
)


def generated_settings() -> str:
    return """from pathlib import Path

INSTALLED_APPS = [
    "home",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "db.sqlite3",
    }
}
"""


def test_mysql_settings_and_tooling_are_consistent(tmp_path: Path) -> None:
    settings = tmp_path / "base.py"
    settings.write_text(generated_settings())
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "example"\nversion = "0.1.0"\n'
    )

    configure_database(settings, "mysql", "example")
    write_developer_tooling(
        project_directory=tmp_path,
        project_name="example",
        settings_module="src.settings",
        database="mysql",
    )

    content = settings.read_text()
    assert '"ENGINE": "django.db.backends.mysql"' in content
    assert '"OPTIONS": {"charset": "utf8mb4"}' in content
    assert "django.contrib.postgres" not in content
    assert database_driver("mysql") == "mysqlclient"
    assert "mysql:8.4" in (tmp_path / "compose.yaml").read_text()
    dockerfile = (tmp_path / "Dockerfile").read_text()
    assert "default-libmysqlclient-dev" in dockerfile
    assert "RUN chown wagtail:wagtail /app" in dockerfile
    assert "MYSQL_ROOT_PASSWORD" in (tmp_path / ".env.example").read_text()
    compose = (tmp_path / "compose.yaml").read_text()
    assert "docker/mysql-init.sh" in compose
    mysql_init = tmp_path / "docker" / "mysql-init.sh"
    assert mysql_init.stat().st_mode & 0o111
    assert "test_${escaped_database}" in mysql_init.read_text()


def test_postgresql_adds_required_django_app(tmp_path: Path) -> None:
    settings = tmp_path / "base.py"
    settings.write_text(generated_settings())

    configure_database(settings, "postgresql", "example")

    content = settings.read_text()
    assert '"ENGINE": "django.db.backends.postgresql"' in content
    assert '"django.contrib.postgres"' in content
    assert database_driver("postgresql") == "psycopg[binary]"
    assert not (tmp_path / "docker" / "mysql-init.sh").exists()
