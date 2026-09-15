"""Create a UV environment and run Wagtail's project-generation command."""

import json
import re
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from wagtail_generate.commands import GenerationError, run_command
from wagtail_generate.developer_tools import (
    apply_developer_tooling_plan,
    configure_database,
)
from wagtail_generate.model_options import configure_models

# Retain the existing imports for callers while planning owns these definitions.
from wagtail_generate.planning import UV_COMMAND as UV_COMMAND
from wagtail_generate.planning import UV_VERSION as UV_VERSION
from wagtail_generate.planning import CommandPlan as CommandPlan
from wagtail_generate.planning import Database as Database
from wagtail_generate.planning import GenerationPlan as GenerationPlan
from wagtail_generate.planning import ProjectOptions as ProjectOptions
from wagtail_generate.planning import ResolvedDependencies as ResolvedDependencies
from wagtail_generate.planning import (
    build_generation_plan as build_generation_plan,
)
from wagtail_generate.planning import dependency_groups
from wagtail_generate.rendering import write_rendered_files
from wagtail_generate.safety import (
    destination_is_in_source_checkout,
    source_checkout_root,
    validate_source_package,
)
from wagtail_generate.transformations import (
    ProjectStructureError,
    flatten_project_package,
)

ROOT_FILES = (".dockerignore", "Dockerfile", "manage.py")
DependencyResolver = Callable[[Database, str], ResolvedDependencies]


def run_wagtail_start(
    project_name: str,
    site_name: str | None = None,
    database: Database = "sqlite3",
    project_root: Path | None = None,
    site_subfolder: Path | None = None,
    template: Path | None = None,
    allow_playground: bool = False,
    dependency_resolver: DependencyResolver | None = None,
    custom_user: bool = False,
    custom_images: bool = False,
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
        custom_user=custom_user,
        custom_images=custom_images,
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
        python_version = latest_stable_python_version(
            _nearest_existing_directory(project_directory)
        )
        resolver = dependency_resolver or resolve_dependencies
        plan = build_generation_plan(
            options,
            python_version,
            resolver(options.database, python_version),
        )
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


def resolve_dependencies(
    database: Database, python_version: str
) -> ResolvedDependencies:
    """Resolve direct dependencies before any generation side effects."""
    requirements = dependency_groups(database)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".in") as source:
        source.write("\n".join(requirements.all) + "\n")
        source.flush()
        result = run_command(
            [
                *UV_COMMAND,
                "pip",
                "compile",
                source.name,
                "--python-version",
                python_version,
                "--no-annotate",
                "--no-header",
            ],
            stage="resolution",
            description="Resolve project dependencies",
            capture_output=True,
        )
    resolved = tuple(
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and not line.startswith("#")
    )
    pinned: dict[str, str] = {}
    for name in requirements.all:
        prefix = name.lower() + "=="
        match = next(
            (line for line in resolved if line.lower().startswith(prefix)), None
        )
        if match is None:
            raise ValueError(f"UV did not resolve direct dependency: {name}")
        pinned[name] = match
    return ResolvedDependencies(
        runtime=tuple(pinned[name] for name in requirements.runtime),
        development=tuple(pinned[name] for name in requirements.development),
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
        print(f"error: {error}", file=sys.stderr)
        return error.returncode or 2
    except (OSError, ValueError) as error:
        print(f"error: generation: {error}", file=sys.stderr)
        return 2


def _execute_generation_plan_in_directory(
    plan: GenerationPlan,
    project_directory: Path,
) -> int:
    """Execute a validated plan inside an isolated directory."""
    _prepare_environment(plan, project_directory)
    _generate_wagtail_site(plan, project_directory)
    settings_file = _adapt_project_structure(plan.options, project_directory)
    if settings_file is None:
        return 2
    _configure_project(plan, project_directory, settings_file)
    for command in plan.model_commands:
        run_command(
            command.arguments,
            cwd=project_directory,
            stage="models",
            description=command.description,
        )
    _format_project(plan, project_directory)
    return 0


def _prepare_environment(plan: GenerationPlan, project_directory: Path) -> None:
    """Create the relocatable UV environment and install planned dependencies."""
    for command in plan.setup_commands:
        run_command(
            command.arguments,
            cwd=project_directory,
            stage="setup",
            description=command.description,
        )


def _generate_wagtail_site(plan: GenerationPlan, project_directory: Path) -> None:
    """Create the source directory and run Wagtail in the prepared environment."""
    options = plan.options
    if options.site_subfolder is not None:
        (project_directory / options.site_subfolder).mkdir(
            parents=True,
            exist_ok=True,
        )

    run_command(
        plan.wagtail_command.arguments,
        cwd=project_directory,
        stage="wagtail",
        description=plan.wagtail_command.description,
    )


def _adapt_project_structure(
    options: ProjectOptions, project_directory: Path
) -> Path | None:
    """Arrange Wagtail's files for the chosen layout and locate its settings.

    Return None when flattening reports a missing package or a file conflict.
    """
    if options.site_subfolder is not None:
        generated_directory = project_directory / options.site_subfolder
        if not _flatten_project_package(
            generated_directory,
            options.project_name,
            ".".join(options.site_subfolder.parts),
        ):
            return None

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
        (project_directory / "requirements.txt").unlink(missing_ok=True)

    return settings_file


def _configure_project(
    plan: GenerationPlan, project_directory: Path, settings_file: Path
) -> None:
    """Apply the site name, database, developer tooling, and planned documentation."""
    options = plan.options
    configure_models(
        project_directory,
        settings_file,
        plan.model_files,
        options.source_directory,
        options.custom_user,
        options.custom_images,
        plan.model_settings,
    )
    _set_wagtail_site_name(settings_file, options.site_name)
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


def _format_project(plan: GenerationPlan, project_directory: Path) -> None:
    """Run the planned formatters after configuration is complete."""
    for command in plan.formatting_commands:
        run_command(
            command.arguments,
            cwd=project_directory,
            stage="formatting",
            description=command.description,
        )


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
    result = run_command(
        [
            *UV_COMMAND,
            "python",
            "list",
            "--only-downloads",
            "--output-format",
            "json",
        ],
        cwd=project_directory,
        stage="resolution",
        description="Discover Python version",
        capture_output=True,
    )

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
    """Adapt the generated package while retaining the legacy bool boundary."""
    try:
        flatten_project_package(generated_directory, project_name, destination_module)
    except ProjectStructureError as error:
        print(f"error: {error}", file=sys.stderr)
        return False
    return True
