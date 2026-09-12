"""Run a disposable developer site in the source checkout."""

import argparse
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from wagtail_generate.safety import source_checkout_root
from wagtail_generate.wagtail import UV_COMMAND, run_wagtail_start

MARKER = ".wagtail-generate-playground"


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


def main(argv: Sequence[str] | None = None) -> int:
    """Rebuild, validate, and serve the playground, or explicitly reset it."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset", action="store_true", help="Remove the playground only"
    )
    parser.add_argument(
        "--site-directory",
        choices=(".", "src"),
        default=".",
        help="Generate Wagtail code at the project root (default) or in src/",
    )
    arguments = parser.parse_args(argv)
    try:
        destination = playground_directory()
        reset_playground(destination)
        if arguments.reset:
            print("Playground reset.")
            return 0
        result = run_wagtail_start(
            project_name="playground",
            site_name="Developer Playground",
            project_root=destination,
            database="sqlite3",
            site_subfolder=(Path("src") if arguments.site_directory == "src" else None),
            allow_playground=True,
        )
        if result:
            return result
        (destination / MARKER).touch()
        # Do not let the generator's active UV environment select its own venv.
        environment = os.environ.copy()
        environment.pop("VIRTUAL_ENV", None)
        for command in (
            ("sync", "--locked"),
            ("run", "python", "manage.py", "migrate", "--noinput"),
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
            ("run", "python", "manage.py", "check"),
            ("run", "python", "manage.py", "runserver", "127.0.0.1:8000"),
        ):
            command_environment = environment.copy()
            if "createsuperuser" in command:
                command_environment["DJANGO_SUPERUSER_PASSWORD"] = "playground"
            if "runserver" in command:
                print(
                    "Playground admin: http://127.0.0.1:8000/admin/ "
                    "(username: admin, password: playground)",
                    flush=True,
                )
            result = subprocess.run(
                [*UV_COMMAND, *command],
                cwd=destination,
                env=command_environment,
                check=False,
            ).returncode
            if result:
                return result
        return 0
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
