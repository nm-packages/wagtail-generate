"""Transform Wagtail's generated source package for a selected layout."""

import ast
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
    updated = re.sub(
        rf"(?P<quote>['\"]){re.escape(project_name)}\.(?=(?:settings|urls|wsgi|asgi)(?:\.|['\"]))",
        rf"\g<quote>{destination_module}.",
        content,
    )
    # AST positions use UTF-8 byte offsets. Apply edits backwards to retain all
    # source outside the changed import statements, including settings layout.
    source = updated.encode()
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    edits = []
    reserved_names = set(re.findall(r"\b\w+\b", updated))
    inline_loader_lines: set[int] = set()
    for node in ast.walk(ast.parse(updated)):
        if isinstance(node, ast.Import):
            if not any(
                _relocated_module(alias.name, project_name, destination_module)
                != alias.name
                for alias in node.names
            ):
                continue
            indentation = lines[node.lineno - 1][: node.col_offset].decode()
            inline = bool(indentation.strip())
            statements = []
            for alias in node.names:
                imports = _rewrite_plain_import(
                    alias, project_name, destination_module, reserved_names
                )
                if len(imports) == 2:
                    if inline:
                        assert node.end_lineno is not None
                        inline_loader_lines.add(node.end_lineno)
                    else:
                        imports[0] += "  # noqa: F401"
                statements.extend(imports)
            separator = "; " if inline else "\n" + indentation
            replacement = separator.join(statements)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            module = _relocated_module(node.module, project_name, destination_module)
            if module == node.module:
                continue
            statement = ast.get_source_segment(updated, node)
            assert statement is not None
            replacement = re.sub(
                r"\Afrom\b.*?\bimport\b",
                f"from {module} import",
                statement,
                count=1,
                flags=re.DOTALL,
            )
        else:
            continue
        assert node.end_lineno is not None and node.end_col_offset is not None
        start = offsets[node.lineno - 1] + node.col_offset
        end = offsets[node.end_lineno - 1] + node.end_col_offset
        edits.append((start, end, replacement.encode()))
    for line_number in inline_loader_lines:
        end = offsets[line_number - 1] + len(lines[line_number - 1].rstrip(b"\r\n"))
        edits.append((end, end, b"  # noqa: F401"))
    for start, end, replacement_bytes in sorted(edits, reverse=True):
        source = source[:start] + replacement_bytes + source[end:]
    return source.decode()


def _relocated_module(name: str, project_name: str, destination_module: str) -> str:
    root, separator, suffix = name.partition(".")
    if root == project_name:
        return destination_module + separator + suffix
    if root in ("home", "search"):
        return f"{destination_module}.{name}"
    return name


def _rewrite_plain_import(
    alias: ast.alias,
    project_name: str,
    destination_module: str,
    reserved_names: set[str],
) -> list[str]:
    module = _relocated_module(alias.name, project_name, destination_module)
    if module == alias.name:
        return [ast.unparse(ast.Import(names=[alias]))]
    root, separator, _ = alias.name.partition(".")
    if alias.asname or not separator:
        return [f"import {module} as {alias.asname or root}"]
    # An unaliased dotted import loads the leaf but binds the original root.
    # Keep the loader under a private, unused name and import the relocated root
    # under the original binding. The loader needs F401 suppression so Ruff does
    # not remove its side effect; either import order leaves the binding intact.
    relocated_root = _relocated_module(root, project_name, destination_module)
    loader_name = "_wagtail_import_" + alias.name.replace(".", "_")
    while loader_name in reserved_names:
        loader_name += "_"
    reserved_names.add(loader_name)
    return [
        f"import {module} as {loader_name}",
        f"import {relocated_root} as {root}",
    ]


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
        try:
            updated = rewrite_imports(content, project_name, destination_module)
        except SyntaxError as error:
            raise ProjectStructureError(
                f"cannot rewrite imports in {python_file}: {error.msg}"
            ) from error
        if updated != content:
            python_file.write_text(updated)


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
    settings_file = generated_directory / "settings" / "base.py"
    settings_file.write_text(
        adjust_settings(settings_file.read_text(), destination_module)
    )
    app_file = generated_directory / "home" / "apps.py"
    app_file.write_text(adjust_app_config(app_file.read_text(), destination_module))
