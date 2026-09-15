"""Run a disposable developer site in the source checkout."""

import argparse
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from wagtail_generate.cli import (
    add_generation_arguments,
    normalize_package_name,
    normalize_subfolder,
    validate_site_name,
)
from wagtail_generate.generation import UV_COMMAND, Database, run_wagtail_start
from wagtail_generate.safety import source_checkout_root, validate_source_package

MARKER = ".wagtail-generate-playground"


@dataclass(frozen=True)
class PlaygroundOptions:
    """Validated command-line choices for the disposable playground."""

    reset: bool
    site_subfolder: Path | None
    project_name: str = "playground"
    site_name: str = "Developer Playground"
    database: Database = "sqlite3"
    starter_homepage: bool = False
    custom_user: bool = False
    custom_images: bool = False
    generate_only: bool = False


def playground_directory() -> Path:
    """Locate the single permitted in-checkout developer destination."""
    checkout = source_checkout_root()
    if checkout is None:
        raise ValueError("the playground requires the wagtail-generate source checkout")
    destination = checkout / ".playground"
    if destination.is_symlink():
        raise ValueError("refusing to use a symlink as the playground")
    return destination


def reset_playground(destination: Path) -> None:
    """Delete only an identified playground at the fixed checkout location."""
    if destination != playground_directory():
        raise ValueError("refusing to reset a directory outside the playground")
    if not destination.exists():
        return
    marker = destination / MARKER
    if not destination.is_dir() or marker.is_symlink() or not marker.is_file():
        raise ValueError("refusing to reset an unrecognized playground directory")
    shutil.rmtree(destination)


def parse_arguments(argv: Sequence[str] | None = None) -> PlaygroundOptions:
    """Validate playground choices before any reset."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset", action="store_true", help="Remove the playground only"
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Generate without application setup or serving",
    )
    parser.add_argument(
        "--project-name",
        default="playground",
        help="Python project name; defaults to playground",
    )
    add_generation_arguments(parser, interactive=False)
    parser.set_defaults(
        site_directory=Path("."),
        site_name="Developer Playground",
        starter_homepage=False,
        custom_user=False,
        custom_images=False,
    )
    arguments = parser.parse_args(argv)
    try:
        project_name = normalize_package_name(arguments.project_name)
        validate_source_package(project_name)
        site_name = validate_site_name(arguments.site_name)
        site_subfolder = (
            None
            if arguments.site_directory == Path(".")
            else normalize_subfolder(str(arguments.site_directory))
        )
    except ValueError as error:
        parser.error(str(error))
    return PlaygroundOptions(
        reset=arguments.reset,
        site_subfolder=site_subfolder,
        project_name=project_name,
        site_name=site_name,
        database=arguments.database,
        starter_homepage=arguments.starter_homepage,
        custom_user=arguments.custom_user,
        custom_images=arguments.custom_images,
        generate_only=arguments.generate_only,
    )


def playground_environment() -> dict[str, str]:
    """Return an environment that uses the playground's own UV environment."""
    environment = os.environ.copy()
    environment.pop("VIRTUAL_ENV", None)
    return environment


def run_playground_command(
    destination: Path,
    arguments: Sequence[str],
    environment: dict[str, str],
) -> int:
    """Run one explicit UV command in the generated playground."""
    return subprocess.run(
        [*UV_COMMAND, *arguments],
        cwd=destination,
        env=environment,
        check=False,
    ).returncode


def generate_playground(destination: Path, options: PlaygroundOptions) -> int:
    """Generate the disposable Wagtail project and mark it as recognized."""
    result = run_wagtail_start(
        project_name=options.project_name,
        site_name=options.site_name,
        project_root=destination,
        database=options.database,
        site_subfolder=options.site_subfolder,
        starter_homepage=options.starter_homepage,
        custom_user=options.custom_user,
        custom_images=options.custom_images,
        allow_playground=True,
    )
    if result == 0:
        (destination / MARKER).touch()
    return result


def prepare_playground(destination: Path, environment: dict[str, str]) -> int:
    """Install the lockfile and apply migrations before application setup."""
    for command in (
        ("sync", "--locked"),
        ("run", "python", "manage.py", "migrate", "--noinput"),
    ):
        result = run_playground_command(destination, command, environment)
        if result:
            return result
    return 0


def create_playground_administrator(
    destination: Path, environment: dict[str, str]
) -> int:
    """Create the known disposable administrator with an isolated password env."""
    administrator_environment = environment.copy()
    administrator_environment["DJANGO_SUPERUSER_PASSWORD"] = "playground"
    return run_playground_command(
        destination,
        (
            "run",
            "python",
            "manage.py",
            "createsuperuser",
            "--noinput",
            "--username",
            "admin",
            "--email",
            "admin@example.test",
        ),
        administrator_environment,
    )


def check_playground(destination: Path, environment: dict[str, str]) -> int:
    """Run Django's system checks before starting the development server."""
    return run_playground_command(
        destination,
        ("run", "python", "manage.py", "check"),
        environment,
    )


def serve_playground(destination: Path, environment: dict[str, str]) -> int:
    """Show playground credentials and serve the site on the documented address."""
    print(
        "Playground admin: http://127.0.0.1:8000/admin/ "
        "(username: admin, password: playground)",
        flush=True,
    )
    return run_playground_command(
        destination,
        ("run", "python", "manage.py", "runserver", "127.0.0.1:8000"),
        environment,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Rebuild, validate, and serve the playground, or explicitly reset it."""
    options = parse_arguments(argv)
    try:
        destination = playground_directory()
        reset_playground(destination)
        if options.reset:
            print("Playground reset.")
            return 0
        result = generate_playground(destination, options)
        if result or options.generate_only:
            return result
        environment = playground_environment()
        for step in (
            prepare_playground,
            create_playground_administrator,
            check_playground,
            serve_playground,
        ):
            result = step(destination, environment)
            if result:
                return result
        return result
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
