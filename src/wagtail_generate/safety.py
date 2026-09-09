"""Safety checks for project generation destinations."""

import sys
import tomllib
from pathlib import Path


def validate_source_package(name: str) -> None:
    """Reject top-level source packages that collide with the standard library."""
    if name in sys.stdlib_module_names:
        raise ValueError(
            f"source package '{name}' conflicts with Python's standard library; "
            "choose a name such as 'src'"
        )


def source_checkout_root() -> Path | None:
    """Return this tool's repository root when running from its source checkout."""
    candidate = Path(__file__).resolve().parents[2]
    pyproject = candidate / "pyproject.toml"
    if not pyproject.is_file():
        return None

    with pyproject.open("rb") as configuration:
        project = tomllib.load(configuration).get("project", {})

    if project.get("name") != "wagtail-generate":
        return None
    return candidate


def destination_is_in_source_checkout(
    destination: Path,
    checkout_root: Path,
) -> bool:
    """Check whether a destination is the tool checkout or one of its children."""
    resolved_destination = destination.resolve()
    resolved_checkout = checkout_root.resolve()
    return resolved_destination.is_relative_to(resolved_checkout)
