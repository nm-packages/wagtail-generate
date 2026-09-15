"""Build typed command and rendered-file plans without executing them."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from wagtail_generate.developer_tools import (
    DeveloperToolingPlan,
    build_developer_tooling_plan,
    database_driver,
)
from wagtail_generate.homepage import build_homepage_files, plan_homepage_removals
from wagtail_generate.model_options import build_model_files
from wagtail_generate.rendering import RenderedFile, plan_template, render_template
from wagtail_generate.safety import validate_source_package

UV_VERSION = "0.12.7"
UV_COMMAND = ("uvx", f"uv@{UV_VERSION}")
Database = Literal["sqlite3", "postgresql", "mysql"]


@dataclass(frozen=True)
class ProjectOptions:
    """Validated user choices that determine a generated project."""

    project_name: str
    site_name: str
    database: Database
    project_root: Path
    site_subfolder: Path | None
    custom_user: bool = False
    custom_images: bool = False
    starter_homepage: bool = False

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
    description: str


@dataclass(frozen=True)
class ResolvedDependencies:
    """Pinned runtime and development dependencies for a generated project."""

    runtime: tuple[str, ...]
    development: tuple[str, ...]

    @property
    def all(self) -> tuple[str, ...]:
        """Return dependencies in the order used for generated lock files."""
        return self.runtime + self.development


def dependency_groups(database: Database) -> ResolvedDependencies:
    """Return the direct runtime and development requirements for a database."""
    runtime = ["wagtail"]
    driver = database_driver(database)
    if driver is not None:
        runtime.append(driver)
    return ResolvedDependencies(
        runtime=tuple(runtime),
        development=("ruff", "djangofmt", "pre-commit"),
    )


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
    resolved_dependencies: ResolvedDependencies
    homepage_files: tuple[RenderedFile, ...] = ()
    homepage_removals: tuple[Path, ...] = ()
    model_settings: str = ""
    model_files: tuple[RenderedFile, ...] = ()
    model_commands: tuple[CommandPlan, ...] = ()


def build_generation_plan(
    options: ProjectOptions,
    python_version: str,
    resolved_dependencies: ResolvedDependencies | None = None,
) -> GenerationPlan:
    """Render and validate every generator-owned action before writing files."""
    validate_source_package(options.settings_module.partition(".")[0])
    if resolved_dependencies is None:
        resolved_dependencies = dependency_groups(options.database)

    model_files = build_model_files(
        options.source_directory,
        options.project_name,
        options.custom_user,
        options.custom_images,
    )
    model_apps = tuple(
        name
        for name, enabled in (
            ("accounts", options.custom_user),
            ("images", options.custom_images),
        )
        if enabled
    )
    return GenerationPlan(
        options=options,
        homepage_files=build_homepage_files(
            options.source_directory,
            options.starter_homepage,
        ),
        homepage_removals=plan_homepage_removals(
            options.source_directory,
            options.starter_homepage,
        ),
        model_files=model_files,
        model_settings=render_template(
            "models/settings.py.jinja",
            {
                "custom_user": options.custom_user,
                "custom_images": options.custom_images,
            },
        )
        if model_apps
        else "",
        model_commands=(
            CommandPlan(
                (
                    *UV_COMMAND,
                    "run",
                    "python",
                    "manage.py",
                    "makemigrations",
                    *model_apps,
                    "--noinput",
                    "--no-header",
                ),
                "Create initial custom model migrations",
            ),
        )
        if model_apps
        else (),
        python_version=python_version,
        setup_commands=_plan_setup_commands(
            options,
            python_version,
            resolved_dependencies.runtime,
            resolved_dependencies.development,
        ),
        wagtail_command=_plan_wagtail_command(options),
        formatting_commands=_plan_formatting_commands(options),
        developer_tooling=build_developer_tooling_plan(
            project_name=options.project_name,
            settings_module=options.settings_module,
            database=options.database,
            python_version=python_version,
        ),
        documentation_files=_plan_documentation_files(options, python_version),
        resolved_dependencies=resolved_dependencies,
    )


def _plan_setup_commands(
    options: ProjectOptions,
    python_version: str,
    runtime_dependencies: Sequence[str],
    development_dependencies: Sequence[str],
) -> tuple[CommandPlan, ...]:
    """Plan environment creation and dependency installation in execution order."""
    return (
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
            ),
            "Initialize project",
        ),
        CommandPlan(
            (*UV_COMMAND, "python", "pin", python_version), "Pin Python version"
        ),
        # Console scripts must keep working after the staged project is moved.
        CommandPlan(
            (*UV_COMMAND, "venv", "--relocatable", "--python", python_version),
            "Create relocatable environment",
        ),
        CommandPlan(
            (*UV_COMMAND, "add", *runtime_dependencies), "Install runtime dependencies"
        ),
        CommandPlan(
            (*UV_COMMAND, "add", "--dev", *development_dependencies),
            "Install development dependencies",
        ),
    )


def _plan_wagtail_command(options: ProjectOptions) -> CommandPlan:
    """Plan Wagtail start for the selected source location and template."""
    wagtail_arguments = [
        *UV_COMMAND,
        "run",
        "wagtail",
        "start",
        options.project_name,
        options.source_directory,
    ]
    return CommandPlan(tuple(wagtail_arguments), "Generate Wagtail site")


def _plan_documentation_files(
    options: ProjectOptions, python_version: str
) -> tuple[RenderedFile, ...]:
    """Render project documentation, retaining custom agent guidance on write."""
    template_description = "the default Wagtail template"
    documentation_context = {
        "starter_homepage": options.starter_homepage,
        "user_model": "accounts.User" if options.custom_user else "auth.User",
        "image_model": "images.CustomImage"
        if options.custom_images
        else "wagtailimages.Image",
        "site_name": options.site_name,
        "project_name": options.project_name,
        "source_directory": options.source_directory,
        "settings_module": options.settings_module,
        "database": options.database,
    }
    return (
        plan_template(
            "AGENTS.md",
            "AGENTS.md.jinja",
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
            "README.md.jinja",
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


def _plan_formatting_commands(options: ProjectOptions) -> tuple[CommandPlan, ...]:
    """Plan template formatting followed by Python lint fixes and formatting."""
    return (
        CommandPlan(
            (*UV_COMMAND, "run", "djangofmt", options.source_directory),
            "Format Django templates",
        ),
        CommandPlan(
            (
                *UV_COMMAND,
                "run",
                "ruff",
                "check",
                "--fix",
                options.source_directory,
            ),
            "Fix Python lint errors",
        ),
        CommandPlan(
            (
                *UV_COMMAND,
                "run",
                "ruff",
                "format",
                options.source_directory,
                "manage.py",
            ),
            "Format Python source",
        ),
    )
