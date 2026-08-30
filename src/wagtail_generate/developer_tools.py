"""Generate local development, formatting, and database tooling."""

import re
from pathlib import Path

TARGET_PYTHON_VERSION = "3.12"


def configure_database(settings_file: Path, database: str, project_name: str) -> None:
    """Replace Wagtail's SQLite settings with an environment-driven database."""
    if database == "postgresql":
        engine = "django.db.backends.postgresql"
        port = "5432"
        options = ""
    else:
        engine = "django.db.backends.mysql"
        port = "3306"
        options = '\n        "OPTIONS": {"charset": "utf8mb4"},'

    content = settings_file.read_text()
    if "import os\n" not in content:
        content = content.replace(
            "from pathlib import Path\n",
            "import os\n\nfrom pathlib import Path\n",
        )

    if database == "postgresql" and '"django.contrib.postgres"' not in content:
        content = content.replace(
            "INSTALLED_APPS = [\n",
            'INSTALLED_APPS = [\n    "django.contrib.postgres",\n',
            1,
        )

    database_settings = f'''DATABASES = {{
    "default": {{
        "ENGINE": "{engine}",
        "NAME": os.environ.get("DATABASE_NAME", "{project_name}"),
        "USER": os.environ.get("DATABASE_USER", "{project_name}"),
        "PASSWORD": os.environ.get("DATABASE_PASSWORD", "development"),
        "HOST": os.environ.get("DATABASE_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DATABASE_PORT", "{port}"),{options}
    }}
}}
'''
    content, replacements = re.subn(
        r"^DATABASES = \{.*?^\}\n",
        database_settings,
        content,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )
    if replacements != 1:
        raise ValueError("could not locate Wagtail's generated DATABASES setting")
    settings_file.write_text(content)


def write_developer_tooling(
    project_directory: Path,
    project_name: str,
    settings_module: str,
    database: str,
) -> None:
    """Write Docker, Compose, formatter, pre-commit, and environment files."""
    _write_dockerfile(project_directory, settings_module, database)
    _write_compose(project_directory, project_name, database)
    _write_environment_example(project_directory, project_name, database)
    _write_ignore_files(project_directory)
    if database == "mysql":
        _write_mysql_initialization(project_directory)
    _append_tool_configuration(project_directory / "pyproject.toml")
    _write_pre_commit(project_directory)


def database_driver(database: str) -> str:
    """Return the Python driver dependency for a selected database."""
    return "psycopg[binary]" if database == "postgresql" else "mysqlclient"


def _write_dockerfile(
    project_directory: Path,
    settings_module: str,
    database: str,
) -> None:
    build_database_packages = (
        "libpq-dev"
        if database == "postgresql"
        else "default-libmysqlclient-dev pkg-config"
    )
    runtime_database_packages = "libpq5" if database == "postgresql" else "libmariadb3"
    wsgi_module = settings_module.removesuffix(".settings")
    (project_directory / "Dockerfile").write_text(
        f'''FROM python:{TARGET_PYTHON_VERSION}-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.7 /uv /uvx /bin/

ENV UV_LINK_MODE=copy \\
    UV_PROJECT_ENVIRONMENT=/app/.venv \\
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update --yes --quiet \\
    && apt-get install --yes --quiet --no-install-recommends \\
        build-essential {build_database_packages} \\
        libjpeg62-turbo-dev zlib1g-dev libwebp-dev \\
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \\
    uv sync --locked --no-dev --no-install-project


FROM builder AS development

RUN --mount=type=cache,target=/root/.cache/uv \\
    uv sync --locked --no-install-project

COPY . .

ENV DJANGO_SETTINGS_MODULE={settings_module}.dev

CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:8000"]


FROM python:{TARGET_PYTHON_VERSION}-slim-bookworm AS runtime

RUN apt-get update --yes --quiet \\
    && apt-get install --yes --quiet --no-install-recommends \\
        {runtime_database_packages} libjpeg62-turbo libwebp7 \\
    && rm -rf /var/lib/apt/lists/* \\
    && useradd --create-home wagtail

ENV PATH="/app/.venv/bin:$PATH" \\
    PYTHONUNBUFFERED=1 \\
    DJANGO_SETTINGS_MODULE={settings_module}.production

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --chown=wagtail:wagtail . .

RUN chown wagtail:wagtail /app

USER wagtail

RUN python manage.py collectstatic --noinput --clear

EXPOSE 8000

CMD ["gunicorn", "{wsgi_module}.wsgi:application", "--bind", "0.0.0.0:8000"]
'''
    )


def _write_compose(project_directory: Path, project_name: str, database: str) -> None:
    if database == "postgresql":
        database_service = f"""    image: postgres:17-bookworm
    environment:
      POSTGRES_DB: ${{DATABASE_NAME:-{project_name}}}
      POSTGRES_USER: ${{DATABASE_USER:-{project_name}}}
      POSTGRES_PASSWORD: ${{DATABASE_PASSWORD:-development}}
    ports:
      - "${{DATABASE_FORWARD_PORT:-5432}}:5432"
    volumes:
      - database-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${{POSTGRES_USER}} -d $${{POSTGRES_DB}}"]
      interval: 2s
      timeout: 5s
      retries: 20
"""
        port = "5432"
    else:
        database_service = f"""    image: mysql:8.4
    environment:
      MYSQL_DATABASE: ${{DATABASE_NAME:-{project_name}}}
      MYSQL_USER: ${{DATABASE_USER:-{project_name}}}
      MYSQL_PASSWORD: ${{DATABASE_PASSWORD:-development}}
      MYSQL_ROOT_PASSWORD: ${{MYSQL_ROOT_PASSWORD:-development-root}}
    ports:
      - "${{DATABASE_FORWARD_PORT:-3306}}:3306"
    volumes:
      - database-data:/var/lib/mysql
      - ./docker/mysql-init.sh:/docker-entrypoint-initdb.d/10-django-test-database.sh:ro
    healthcheck:
      test:
        - CMD-SHELL
        - >-
          mysqladmin ping -h localhost -uroot
          -p$${{MYSQL_ROOT_PASSWORD}} --silent
      interval: 2s
      timeout: 5s
      retries: 30
"""
        port = "3306"

    (project_directory / "compose.yaml").write_text(
        f"""services:
  web:
    build:
      context: .
      target: development
    init: true
    command: >-
      sh -c "uv run python manage.py migrate &&
      uv run python manage.py runserver 0.0.0.0:8000"
    environment:
      DATABASE_NAME: ${{DATABASE_NAME:-{project_name}}}
      DATABASE_USER: ${{DATABASE_USER:-{project_name}}}
      DATABASE_PASSWORD: ${{DATABASE_PASSWORD:-development}}
      DATABASE_HOST: db
      DATABASE_PORT: {port}
    ports:
      - "${{WEB_PORT:-8000}}:8000"
    volumes:
      - .:/app
      - web-venv:/app/.venv
    depends_on:
      db:
        condition: service_healthy

  db:
{database_service}
volumes:
  database-data:
  web-venv:
"""
    )


def _write_environment_example(
    project_directory: Path,
    project_name: str,
    database: str,
) -> None:
    port = "5432" if database == "postgresql" else "3306"
    extra = "" if database == "postgresql" else "MYSQL_ROOT_PASSWORD=development-root\n"
    (project_directory / ".env.example").write_text(
        f"""DATABASE_NAME={project_name}
DATABASE_USER={project_name}
DATABASE_PASSWORD=development
DATABASE_HOST=db
DATABASE_PORT={port}
DATABASE_FORWARD_PORT={port}
WEB_PORT=8000
{extra}"""
    )


def _write_mysql_initialization(project_directory: Path) -> None:
    """Grant the application user access to Django's generated test database."""
    docker_directory = project_directory / "docker"
    docker_directory.mkdir(exist_ok=True)
    initialization_script = docker_directory / "mysql-init.sh"
    initialization_script.write_text(
        r"""#!/bin/sh
set -eu

escaped_database=$(printf '%s' "$MYSQL_DATABASE" | sed 's/`/``/g')
escaped_user=$(printf '%s' "$MYSQL_USER" | sed "s/'/''/g")

mysql --protocol=socket -uroot -p"$MYSQL_ROOT_PASSWORD" <<EOSQL
GRANT ALL PRIVILEGES ON \`test_${escaped_database}\`.* TO '${escaped_user}'@'%';
FLUSH PRIVILEGES;
EOSQL
"""
    )
    initialization_script.chmod(0o755)


def _write_ignore_files(project_directory: Path) -> None:
    (project_directory / ".gitignore").write_text(
        """.DS_Store
.env
.venv/
__pycache__/
*.py[cod]
*.sqlite3
.pytest_cache/
.ruff_cache/
htmlcov/
media/
static/
"""
    )
    (project_directory / ".dockerignore").write_text(
        """.git
.gitignore
.env
.venv
__pycache__
*.py[cod]
*.sqlite3
.pytest_cache
.ruff_cache
htmlcov
media
static
"""
    )


def _append_tool_configuration(pyproject: Path) -> None:
    configuration = """

[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
ignore = ["E501"]

[tool.ruff.lint.per-file-ignores]
"**/settings/*.py" = ["F403", "F405", "SIM105"]

[tool.djangofmt]
profile = "django"
line-length = 88
indent-width = 4
"""
    content = pyproject.read_text()
    if "[tool.ruff]" not in content:
        pyproject.write_text(content.rstrip() + configuration)


def _write_pre_commit(project_directory: Path) -> None:
    (project_directory / ".pre-commit-config.yaml").write_text(
        r"""repos:
  - repo: local
    hooks:
      - id: uv-lock
        name: Validate UV lockfile
        entry: uv lock --check
        language: system
        files: ^(pyproject\.toml|uv\.lock)$
        pass_filenames: false

      - id: ruff-check
        name: Ruff lint
        entry: uv run ruff check --fix
        language: system
        types: [python]

      - id: ruff-format
        name: Ruff format
        entry: uv run ruff format
        language: system
        types: [python]

      - id: djangofmt
        name: Format Django templates
        entry: uv run djangofmt
        language: system
        files: (^|/)templates/.*\.html$

"""
    )
