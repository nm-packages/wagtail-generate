"""Command-line interface for wagtail-generate."""

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from wagtail_generate import __version__
from wagtail_generate.safety import (
    destination_is_in_source_checkout,
    source_checkout_root,
)
from wagtail_generate.wagtail import run_wagtail_start


def prompt_for_destination(
    project_name: str,
    base_directory: Path | None = None,
    input_fn: Callable[[str], str] | None = None,
) -> Path:
    """Ask whether the generated project should live in a subfolder."""
    base_directory = base_directory or Path.cwd()
    read_input = input_fn or input

    while True:
        use_subfolder = read_input("Generate the site in a subfolder? [y/N]: ")
        match use_subfolder.strip().lower():
            case "" | "n" | "no":
                return base_directory
            case "y" | "yes":
                subfolder = read_input(f"Subfolder name [{project_name}]: ").strip()
                return base_directory / (subfolder or project_name)
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
        "--directory",
        type=Path,
        help="Directory to initialize; defaults to the current directory.",
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
        destination = arguments.directory
        if destination is None:
            destination = prompt_for_destination(arguments.project_name)

        checkout_root = source_checkout_root()
        if checkout_root is not None and destination_is_in_source_checkout(
            destination,
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

        destination.mkdir(parents=True, exist_ok=True)

        return run_wagtail_start(
            project_name=arguments.project_name,
            destination=destination,
            template=arguments.template,
        )

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
