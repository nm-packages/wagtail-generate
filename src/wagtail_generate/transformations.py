"""Transform Wagtail's generated source package for a selected layout."""

import re
from pathlib import Path


class ProjectStructureError(ValueError):
    """The generated project does not have the structure required to adapt it."""


def move_project_package(generated_directory: Path, project_name: str) -> None:
    """Move the nested Wagtail package contents into the source directory."""
    package_directory = generated_directory / project_name
    if not package_directory.is_dir():
        raise ProjectStructureError(
            f"Wagtail did not generate the expected {project_name}/ package"
        )

    conflicts = sorted(
        child.name
        for child in package_directory.iterdir()
        if (generated_directory / child.name).exists()
    )
    if conflicts:
        raise ProjectStructureError(
            "refusing to overwrite generated code path(s): " + ", ".join(conflicts)
        )

    for child in package_directory.iterdir():
        child.replace(generated_directory / child.name)
    package_directory.rmdir()


def validate_generated_structure(generated_directory: Path, project_name: str) -> None:
    """Validate the generated files required by the source-subfolder transform."""
    package_directory = generated_directory / project_name
    if not package_directory.is_dir():
        raise ProjectStructureError(
            f"Wagtail did not generate the expected {project_name}/ package"
        )
    for relative_path in ("settings/base.py",):
        if not (package_directory / relative_path).is_file():
            raise ProjectStructureError(
                "Wagtail did not generate the expected "
                f"{project_name}/{relative_path} file"
            )
    if not (generated_directory / "home" / "apps.py").is_file():
        raise ProjectStructureError(
            "Wagtail did not generate the expected home/apps.py file"
        )


def ensure_package_markers(generated_directory: Path, destination_module: str) -> None:
    """Create ``__init__.py`` files for each parent source package."""
    parent_directory = generated_directory.parent
    for _ in range(len(destination_module.split(".")) - 1):
        package_marker = parent_directory / "__init__.py"
        if not package_marker.exists():
            package_marker.write_text("")
        parent_directory = parent_directory.parent


def rewrite_imports(content: str, project_name: str, destination_module: str) -> str:
    """Rewrite generated project and app imports to the selected module path."""
    new_prefix = f"{destination_module}."
    updated = re.sub(
        rf"(?P<prefix>\b(?:from|import)\s+){re.escape(project_name)}\.",
        rf"\g<prefix>{new_prefix}",
        content,
    )
    updated = re.sub(
        rf"(?P<quote>['\"]){re.escape(project_name)}\.(?=(?:settings|urls|wsgi|asgi)(?:\.|['\"]))",
        rf"\g<quote>{new_prefix}",
        updated,
    )
    for app_name in ("home", "search"):
        updated = re.sub(
            rf"(?P<prefix>\b(?:from|import)\s+){app_name}(?=\s|\.)",
            rf"\g<prefix>{destination_module}.{app_name}",
            updated,
        )
    return updated


def adjust_settings(content: str, destination_module: str) -> str:
    """Adjust the generated settings paths and installed applications."""
    if "BASE_DIR = PROJECT_DIR.parent" not in content:
        raise ProjectStructureError(
            "Wagtail's generated settings are missing BASE_DIR = PROJECT_DIR.parent"
        )
    source_depth = len(destination_module.split("."))
    project_root_expression = "PROJECT_DIR" + ".parent" * source_depth
    updated = content.replace(
        "BASE_DIR = PROJECT_DIR.parent",
        f"BASE_DIR = {project_root_expression}",
    )
    for app_name in ("home", "search"):
        updated = updated.replace(
            f'"{app_name}"',
            f'"{destination_module}.{app_name}"',
        )
    return updated


def adjust_app_config(content: str, destination_module: str) -> str:
    """Set the generated home app's full Python module name."""
    if '    name = "home"' not in content:
        raise ProjectStructureError(
            'Wagtail\'s generated home app is missing name = "home"'
        )
    return content.replace(
        '    name = "home"',
        f'    name = "{destination_module}.home"',
    )


def rewrite_python_files(
    generated_directory: Path,
    project_name: str,
    destination_module: str,
) -> None:
    """Apply import rewriting to every generated Python source file."""
    for python_file in generated_directory.rglob("*.py"):
        content = python_file.read_text()
        updated = rewrite_imports(content, project_name, destination_module)
        if updated != content:
            python_file.write_text(updated)


def adjust_generated_settings(
    generated_directory: Path, destination_module: str
) -> None:
    """Validate and update the generated settings module."""
    settings_file = generated_directory / "settings" / "base.py"
    if not settings_file.is_file():
        raise ProjectStructureError(
            "Wagtail did not generate the expected settings/base.py file"
        )
    settings_file.write_text(
        adjust_settings(settings_file.read_text(), destination_module)
    )


def adjust_generated_app_config(
    generated_directory: Path, destination_module: str
) -> None:
    """Validate and update the generated home app configuration."""
    app_file = generated_directory / "home" / "apps.py"
    if not app_file.is_file():
        raise ProjectStructureError(
            "Wagtail did not generate the expected home/apps.py file"
        )
    app_file.write_text(adjust_app_config(app_file.read_text(), destination_module))


def flatten_project_package(
    generated_directory: Path,
    project_name: str,
    destination_module: str,
) -> None:
    """Adapt a nested Wagtail project to a source-subfolder package layout."""
    validate_generated_structure(generated_directory, project_name)
    move_project_package(generated_directory, project_name)
    ensure_package_markers(generated_directory, destination_module)
    rewrite_python_files(generated_directory, project_name, destination_module)
    adjust_generated_settings(generated_directory, destination_module)
    adjust_generated_app_config(generated_directory, destination_module)
