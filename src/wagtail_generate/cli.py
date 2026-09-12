"""Command-line interface for wagtail-generate."""

import argparse
import keyword
import re
import sys
import unicodedata
from collections.abc import Callable, Sequence
from pathlib import Path

from wagtail_generate import __version__
from wagtail_generate.layouts import get_layout, layout_names
from wagtail_generate.safety import (
    destination_is_in_source_checkout,
    source_checkout_root,
    validate_source_package,
)
from wagtail_generate.wagtail import Database, run_wagtail_start


def normalize_package_name(value: str) -> str:
    """Convert a human-readable name into a conventional Python package name."""
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    )
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value).strip("_").lower()
    if not normalized:
        raise ValueError("the name must contain at least one letter or number")
    if normalized[0].isdigit():
        normalized = f"site_{normalized}"
    if keyword.iskeyword(normalized):
        normalized = f"{normalized}_site"
    return normalized


def display_site_name(value: str) -> str:
    """Return a readable site name without package-name separators."""
    readable_name = " ".join(re.sub(r"[_-]+", " ", value).split())
    return readable_name.title()


def prompt_for_site_name(
    default_name: str,
    input_fn: Callable[[str], str] | None = None,
) -> str:
    """Ask for the human-facing Wagtail site name."""
    read_input = input_fn or input
    while True:
        value = read_input(f"Site name [{default_name}]: ")
        try:
            return validate_site_name(default_name if value == "" else value)
        except ValueError as error:
            print(f"Invalid site name: {error}")


def validate_site_name(value: str) -> str:
    """Trim a display name while preserving its spelling and punctuation."""
    name = value.strip()
    if not name:
        raise ValueError("site name cannot be empty")
    if any(unicodedata.category(character) == "Cc" for character in name):
        raise ValueError("site name cannot contain control characters")
    return name


def normalize_subfolder(value: str) -> Path:
    """Normalize each component of a relative Python package path."""
    subfolder = Path(value)
    if subfolder == Path(".") or subfolder.is_absolute() or ".." in subfolder.parts:
        raise ValueError("the subfolder must stay inside the project root")
    normalized = Path(*(normalize_package_name(part) for part in subfolder.parts))
    validate_source_package(normalized.parts[0])
    return normalized


def prompt_for_site_subfolder(
    project_name: str,
    input_fn: Callable[[str], str] | None = None,
) -> Path | None:
    """Ask whether Wagtail's generated code should live in a subfolder."""
    read_input = input_fn or input

    while True:
        use_subfolder = read_input("Generate the site in a subfolder? [y/N]: ")
        match use_subfolder.strip().lower():
            case "" | "n" | "no":
                return None
            case "y" | "yes":
                while True:
                    value = read_input(f"Subfolder name [{project_name}]: ").strip()
                    requested_name = value or project_name
                    try:
                        subfolder = normalize_subfolder(requested_name)
                    except ValueError as error:
                        print(f"Invalid subfolder: {error}")
                        continue
                    if str(subfolder) != requested_name:
                        print(f"Using subfolder name: {subfolder}")
                    return subfolder
            case _:
                print("Please answer yes or no.")


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="wagtail-generate",
        description=(
            "Generate an opinionated Wagtail CMS project from a named layout."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")
    start_parser = subparsers.add_parser(
        "start",
        help="Create a UV project and start a Wagtail site.",
        description=(
            "Initialize a UV project, add the latest Wagtail, and generate the site."
        ),
    )
    start_parser.add_argument("project_name", help="Name for the Wagtail project.")
    start_parser.add_argument(
        "--site-name",
        help="Human-facing Wagtail site name; prompted for when omitted.",
    )
    start_parser.add_argument(
        "--database",
        choices=("sqlite3", "postgresql", "mysql"),
        default="sqlite3",
        help="Database backend; defaults to sqlite3.",
    )
    start_parser.add_argument(
        "--directory",
        type=Path,
        help=(
            "UV project root; defaults to a site-name folder in the current directory."
        ),
    )
    start_parser.add_argument(
        "--site-directory",
        type=Path,
        default=argparse.SUPPRESS,
        help=(
            "Non-interactive Wagtail code directory relative to the project root; "
            "use '.' for the root."
        ),
    )
    start_parser.add_argument(
        "--layout",
        choices=layout_names(),
        default="standard",
        help="Named codebase layout; defaults to standard.",
    )
    start_parser.add_argument(
        "--template",
        type=Path,
        help="Optional custom Wagtail project template path.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""
    parser = build_parser()
    arguments = parser.parse_args(argv)
    if arguments.command == "start":
        try:
            project_name = normalize_package_name(arguments.project_name)
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        if project_name != arguments.project_name:
            print(f"Using Python project name: {project_name}")

        default_site_name = display_site_name(project_name)
        if arguments.site_name is None:
            site_name = prompt_for_site_name(default_site_name)
        else:
            try:
                site_name = validate_site_name(arguments.site_name)
            except ValueError as error:
                print(f"error: --site-name: {error}", file=sys.stderr)
                return 2

        project_root = arguments.directory
        if project_root is None:
            try:
                directory_name = normalize_package_name(site_name)
            except ValueError:
                directory_name = project_name
            project_root = Path.cwd() / directory_name
        project_root = project_root.resolve()
        project_root_exists = project_root.exists()

        checkout_root = source_checkout_root()
        if checkout_root is not None and destination_is_in_source_checkout(
            project_root,
            checkout_root,
        ):
            print(
                "error: refusing to generate a site inside the wagtail-generate "
                f"source checkout ({checkout_root})",
                file=sys.stderr,
            )
            print(
                "Choose a directory outside this repository.",
                file=sys.stderr,
            )
            return 2

        if project_root.exists():
            if not project_root.is_dir():
                print(
                    f"error: project root is not a directory: {project_root}",
                    file=sys.stderr,
                )
                return 2
            existing_entries = sorted(path.name for path in project_root.iterdir())
            if existing_entries:
                preview = ", ".join(existing_entries[:5])
                if len(existing_entries) > 5:
                    preview += f", and {len(existing_entries) - 5} more"
                print(
                    f"error: project root must be empty: {project_root}",
                    file=sys.stderr,
                )
                print(f"Found: {preview}", file=sys.stderr)
                return 2

        database: Database = arguments.database

        if hasattr(arguments, "site_directory"):
            site_subfolder = arguments.site_directory
            if site_subfolder == Path("."):
                site_subfolder = None
            else:
                try:
                    site_subfolder = normalize_subfolder(str(site_subfolder))
                except ValueError as error:
                    print(
                        f"error: --site-directory: {error}",
                        file=sys.stderr,
                    )
                    return 2
        else:
            site_subfolder = prompt_for_site_subfolder(project_name)

        template = arguments.template
        if template is not None:
            template = template.resolve()
            if not template.exists():
                print(
                    f"error: Wagtail project template does not exist: {template}",
                    file=sys.stderr,
                )
                return 2

        result = run_wagtail_start(
            project_name=project_name,
            site_name=site_name,
            database=database,
            project_root=project_root,
            site_subfolder=site_subfolder,
            template=template,
            layout=get_layout(arguments.layout),
        )
        if result == 0 and arguments.directory is None:
            action = "Using" if project_root_exists else "Created"
            print(f"{action} project directory: {project_root}", flush=True)
        return result

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
