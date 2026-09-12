"""Create a UV environment and run Wagtail's project-generation command."""

import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from wagtail_generate.developer_tools import (
    DeveloperToolingPlan,
    apply_developer_tooling_plan,
    build_developer_tooling_plan,
    configure_database,
    database_driver,
)
from wagtail_generate.layouts import STANDARD_LAYOUT, Layout
from wagtail_generate.rendering import RenderedFile, plan_template, write_rendered_files
from wagtail_generate.safety import (
    destination_is_in_source_checkout,
    source_checkout_root,
    validate_source_package,
)

ROOT_FILES = (".dockerignore", "Dockerfile", "manage.py")
UV_VERSION = "0.12.7"
UV_COMMAND = ("uvx", f"uv@{UV_VERSION}")
Database = Literal["sqlite3", "postgresql", "mysql"]


class GenerationError(RuntimeError):
    """An expected operational failure while generating a project."""

    def __init__(self, stage: str, message: str, returncode: int | None = None) -> None:
        super().__init__(message)
        self.stage = stage
        self.returncode = returncode


@dataclass(frozen=True)
class ProjectOptions:
    """Validated user choices that determine a generated project."""

    project_name: str
    site_name: str
    database: Database
    project_root: Path
    site_subfolder: Path | None
    template: Path | None
    layout: Layout = STANDARD_LAYOUT

    @property
    def source_directory(self) -> str:
        """Return the source directory relative to the project root."""
        return "." if self.site_subfolder is None else str(self.site_subfolder)

    @property
    def settings_module(self) -> str:
        """Return the generated Django settings package."""
        if self.site_subfolder is None:
            return f"{self.project_name}.settings"
        return f"{'.'.join(self.site_subfolder.parts)}.settings"


@dataclass(frozen=True)
class CommandPlan:
    """One external command in a generation plan."""

    arguments: tuple[str, ...]


@dataclass(frozen=True)
class GenerationPlan:
    """A complete, rendered generation plan ready for side-effect execution."""

    options: ProjectOptions
    python_version: str
    setup_commands: tuple[CommandPlan, ...]
    wagtail_command: CommandPlan
    formatting_commands: tuple[CommandPlan, ...]
    developer_tooling: DeveloperToolingPlan
    documentation_files: tuple[RenderedFile, ...]


def run_wagtail_start(
    project_name: str,
    site_name: str | None = None,
    database: Database = "sqlite3",
    project_root: Path | None = None,
    site_subfolder: Path | None = None,
    template: Path | None = None,
    layout: Layout = STANDARD_LAYOUT,
    allow_playground: bool = False,
) -> int:
    """Initialize a UV project, install Wagtail, and generate into that project."""
    project_directory = (project_root or Path.cwd()).resolve()
    options = ProjectOptions(
        project_name=project_name,
        site_name=site_name or project_name.replace("_", " ").title(),
        database=database,
        project_root=project_directory,
        site_subfolder=site_subfolder,
        template=template,
        layout=layout,
    )

    try:
        _validate_generation_boundary(options, allow_playground=allow_playground)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if site_subfolder is not None:
        conflicts = [
            filename
            for filename in ROOT_FILES
            if (project_directory / filename).exists()
        ]
        if conflicts:
            print(
                "error: refusing to overwrite project-root file(s): "
                + ", ".join(conflicts),
                file=sys.stderr,
            )
            return 2

    try:
        validate_source_package(options.settings_module.partition(".")[0])
        python_version = latest_stable_python_version(
            _nearest_existing_directory(project_directory)
        )
        plan = build_generation_plan(options, python_version)
    except (RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    return execute_generation_plan(plan)


def _validate_generation_boundary(
    options: ProjectOptions,
    *,
    allow_playground: bool = False,
) -> None:
    """Validate paths and option invariants before any side effects."""
    if options.site_subfolder is not None:
        if options.site_subfolder.is_absolute() or ".." in options.site_subfolder.parts:
            raise ValueError(
                "site subfolder must be relative and stay inside the project root"
            )
        if options.site_subfolder == Path("."):
            raise ValueError("site subfolder must name a directory or be omitted")
    checkout = source_checkout_root()
    if (
        checkout is not None
        and destination_is_in_source_checkout(options.project_root, checkout)
        and not (
            allow_playground
            and options.project_root == (checkout / ".playground").resolve()
        )
    ):
        raise ValueError(
            "refusing to generate inside the wagtail-generate source checkout"
        )
    validate_source_package(options.settings_module.partition(".")[0])


def build_generation_plan(
    options: ProjectOptions,
    python_version: str,
) -> GenerationPlan:
    """Render and validate every generator-owned action before writing files."""
    validate_source_package(options.settings_module.partition(".")[0])
    runtime_dependencies = ["wagtail"]
    driver = database_driver(options.database)
    if driver is not None:
        runtime_dependencies.append(driver)

    setup_commands = (
        CommandPlan(
            (
                *UV_COMMAND,
                "init",
                "--bare",
                "--no-workspace",
                "--python",
                python_version,
                "--name",
                options.project_name,
            )
        ),
        CommandPlan((*UV_COMMAND, "python", "pin", python_version)),
        # Console scripts must keep working after the staged project is moved.
        CommandPlan((*UV_COMMAND, "venv", "--relocatable", "--python", python_version)),
        CommandPlan((*UV_COMMAND, "add", *runtime_dependencies)),
        CommandPlan((*UV_COMMAND, "add", "--dev", "ruff", "djangofmt", "pre-commit")),
    )

    wagtail_arguments = [
        *UV_COMMAND,
        "run",
        "wagtail",
        "start",
        options.project_name,
        options.source_directory,
    ]
    if options.template is not None:
        wagtail_arguments.append(f"--template={options.template}")

    tooling = build_developer_tooling_plan(
        project_name=options.project_name,
        settings_module=options.settings_module,
        database=options.database,
        python_version=python_version,
    )
    template_description = (
        f"custom template `{options.template}`"
        if options.template is not None
        else "the default Wagtail template"
    )
    documentation_context = {
        "site_name": options.site_name,
        "project_name": options.project_name,
        "source_directory": options.source_directory,
        "settings_module": options.settings_module,
        "database": options.database,
        "layout": options.layout.name,
    }
    documentation_files = (
        plan_template(
            "AGENTS.md",
            options.layout.agents_template,
            documentation_context | {"template_description": template_description},
            overwrite=False,
        ),
        *(
            plan_template(
                f"docs/agent-instructions/{name}.md",
                f"docs/agent-instructions/{name}.md.jinja",
                documentation_context,
                overwrite=False,
            )
            for name in ("environment", "backend", "checks")
        ),
        plan_template(
            "README.md",
            options.layout.readme_template,
            documentation_context
            | {
                "database_name": {
                    "sqlite3": "SQLite",
                    "postgresql": "PostgreSQL",
                    "mysql": "MySQL",
                }[options.database],
                "python_version": python_version,
            },
        ),
    )
    formatting_commands = (
        CommandPlan((*UV_COMMAND, "run", "djangofmt", options.source_directory)),
        CommandPlan(
            (
                *UV_COMMAND,
                "run",
                "ruff",
                "check",
                "--fix",
                options.source_directory,
            )
        ),
        CommandPlan(
            (
                *UV_COMMAND,
                "run",
                "ruff",
                "format",
                options.source_directory,
                "manage.py",
            )
        ),
    )
    return GenerationPlan(
        options=options,
        python_version=python_version,
        setup_commands=setup_commands,
        wagtail_command=CommandPlan(tuple(wagtail_arguments)),
        formatting_commands=formatting_commands,
        developer_tooling=tooling,
        documentation_files=documentation_files,
    )


def execute_generation_plan(plan: GenerationPlan) -> int:
    """Execute a plan in staging and publish it only after complete success."""
    try:
        project_directory = plan.options.project_root
        staging_parent = _nearest_existing_directory(project_directory.parent)
        with tempfile.TemporaryDirectory(
            dir=staging_parent,
            prefix=f".{project_directory.name}-",
        ) as temporary_directory:
            staging_directory = Path(temporary_directory)
            result = _execute_generation_plan_in_directory(plan, staging_directory)
            if result != 0:
                return result
            if not _publish_generated_project(staging_directory, project_directory):
                return 2
        return 0
    except GenerationError as error:
        print(f"error: {error.stage}: {error}", file=sys.stderr)
        return error.returncode or 2
    except (OSError, ValueError) as error:
        print(f"error: generation: {error}", file=sys.stderr)
        return 2


def _execute_generation_plan_in_directory(
    plan: GenerationPlan,
    project_directory: Path,
) -> int:
    """Execute a validated plan inside an isolated directory."""
    options = plan.options

    for command in plan.setup_commands:
        result = _run_generation_command(command, project_directory, "setup")
        if result.returncode != 0:
            return result.returncode

    if options.site_subfolder is not None:
        (project_directory / options.site_subfolder).mkdir(
            parents=True,
            exist_ok=True,
        )

    result = _run_generation_command(plan.wagtail_command, project_directory, "wagtail")
    if result.returncode != 0:
        return result.returncode

    if options.site_subfolder is not None:
        generated_directory = project_directory / options.site_subfolder
        if not _flatten_project_package(
            generated_directory,
            options.project_name,
            ".".join(options.site_subfolder.parts),
        ):
            return 2

        _set_wagtail_site_name(
            generated_directory / "settings" / "base.py",
            options.site_name,
        )
        (generated_directory / "requirements.txt").unlink(missing_ok=True)
        (generated_directory / "README.md").unlink(missing_ok=True)
        for filename in ROOT_FILES:
            source = generated_directory / filename
            if source.exists():
                source.replace(project_directory / filename)
        settings_file = generated_directory / "settings" / "base.py"
    else:
        settings_file = (
            project_directory / options.project_name / "settings" / "base.py"
        )
        _set_wagtail_site_name(settings_file, options.site_name)
        (project_directory / "requirements.txt").unlink(missing_ok=True)

    configure_database(
        settings_file,
        options.database,
        options.project_name,
    )
    apply_developer_tooling_plan(
        project_directory,
        plan.developer_tooling,
    )
    write_rendered_files(project_directory, plan.documentation_files)

    for command in plan.formatting_commands:
        result = _run_generation_command(command, project_directory, "formatting")
        if result.returncode != 0:
            return result.returncode

    return 0


def _run_generation_command(
    command: CommandPlan, project_directory: Path, stage: str
) -> subprocess.CompletedProcess[bytes]:
    """Run one command and translate missing executables into a stage error."""
    try:
        return subprocess.run(
            list(command.arguments), cwd=project_directory, check=False
        )
    except OSError as error:
        raise GenerationError(stage, str(error)) from error


def _publish_generated_project(staging_directory: Path, destination: Path) -> bool:
    """Move a completed staged project into an absent or empty destination."""
    if destination.exists():
        existing_entries = list(destination.iterdir())
        if existing_entries:
            print(
                f"error: project root became nonempty during generation: {destination}",
                file=sys.stderr,
            )
            return False
        for child in staging_directory.iterdir():
            child.replace(destination / child.name)
        return True

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging_directory.replace(destination)
    return True


def _set_wagtail_site_name(settings_file: Path, site_name: str) -> None:
    """Replace Wagtail's package-style site name with a human-readable name."""
    content = settings_file.read_text()
    updated = re.sub(
        r"^WAGTAIL_SITE_NAME\s*=.*$",
        lambda _: f"WAGTAIL_SITE_NAME = {json.dumps(site_name, ensure_ascii=False)}",
        content,
        flags=re.MULTILINE,
    )
    if updated != content:
        settings_file.write_text(updated)


def _nearest_existing_directory(path: Path) -> Path:
    """Return an existing directory suitable for read-only UV resolution."""
    candidate = path
    while not candidate.exists():
        candidate = candidate.parent
    return candidate if candidate.is_dir() else candidate.parent


def latest_stable_python_version(project_directory: Path) -> str:
    """Return the major/minor line of the newest stable CPython known to UV."""
    result = subprocess.run(
        [
            *UV_COMMAND,
            "python",
            "list",
            "--only-downloads",
            "--output-format",
            "json",
        ],
        cwd=project_directory,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "UV could not list Python downloads"
        raise RuntimeError(detail)

    downloads = json.loads(result.stdout)
    if not isinstance(downloads, list):
        raise ValueError("UV returned an invalid Python download list")

    versions: list[str] = []
    for download in downloads:
        if not isinstance(download, dict):
            continue
        version = download.get("version")
        if (
            download.get("implementation") == "cpython"
            and download.get("variant") == "default"
            and isinstance(version, str)
            and re.fullmatch(r"\d+\.\d+\.\d+", version)
        ):
            versions.append(version)

    if not versions:
        raise ValueError("UV did not report a stable CPython download")
    latest = max(versions, key=lambda version: tuple(map(int, version.split("."))))
    major, minor, _ = latest.split(".")
    return f"{major}.{minor}"


def _flatten_project_package(
    generated_directory: Path,
    project_name: str,
    destination_module: str,
) -> bool:
    """Move the nested Django project package into the selected source folder."""
    package_directory = generated_directory / project_name
    if not package_directory.is_dir():
        print(
            f"error: Wagtail did not generate the expected {project_name}/ package",
            file=sys.stderr,
        )
        return False

    conflicts = [
        child.name
        for child in package_directory.iterdir()
        if (generated_directory / child.name).exists()
    ]
    if conflicts:
        print(
            "error: refusing to overwrite generated code path(s): "
            + ", ".join(sorted(conflicts)),
            file=sys.stderr,
        )
        return False

    for child in package_directory.iterdir():
        child.replace(generated_directory / child.name)
    package_directory.rmdir()

    parent_directory = generated_directory.parent
    for _ in range(len(destination_module.split(".")) - 1):
        package_marker = parent_directory / "__init__.py"
        if not package_marker.exists():
            package_marker.write_text("")
        parent_directory = parent_directory.parent

    new_prefix = f"{destination_module}."
    for python_file in generated_directory.rglob("*.py"):
        content = python_file.read_text()
        # Rewrite only import paths and quoted settings-module references. A
        # global replacement would corrupt identifiers such as ``models.Model``
        # when the project itself is named ``models``.
        updated = re.sub(
            rf'(?P<prefix>\b(?:from|import)\s+|["\']){re.escape(project_name)}\.',
            rf"\g<prefix>{new_prefix}",
            content,
        )
        for app_name in ("home", "search"):
            for suffix in (" ", "."):
                updated = updated.replace(
                    f"from {app_name}{suffix}",
                    f"from {destination_module}.{app_name}{suffix}",
                )
        if updated != content:
            python_file.write_text(updated)

    settings_file = generated_directory / "settings" / "base.py"
    settings = settings_file.read_text()
    source_depth = len(destination_module.split("."))
    project_root_expression = "PROJECT_DIR" + ".parent" * source_depth
    settings = settings.replace(
        "BASE_DIR = PROJECT_DIR.parent",
        f"BASE_DIR = {project_root_expression}",
    )
    for app_name in ("home", "search"):
        settings = settings.replace(
            f'"{app_name}"',
            f'"{destination_module}.{app_name}"',
        )
    settings_file.write_text(settings)

    home_app = generated_directory / "home" / "apps.py"
    app_config = home_app.read_text().replace(
        '    name = "home"',
        f'    name = "{destination_module}.home"',
    )
    home_app.write_text(app_config)

    return True
