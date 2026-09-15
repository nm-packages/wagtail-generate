"""Plan optional model apps and safely integrate their settings."""

import ast
import re
from pathlib import Path

from wagtail_generate.rendering import RenderedFile, plan_template, write_rendered_files

MODEL_SETTINGS = ("AUTH_USER_MODEL", "WAGTAILIMAGES_IMAGE_MODEL")


def _source_files(directory: Path) -> list[Path]:
    """Find template/site Python sources without examining environments."""
    return sorted(
        path
        for path in directory.rglob("*.py")
        if not any(part.startswith(".") for part in path.relative_to(directory).parts)
    )


def _validate_conflicts(directory: Path, apps: tuple[str, ...]) -> None:
    """Reject existing model settings and app labels before installing any files."""
    for path in _source_files(directory):
        content = path.read_text()
        for app in apps:
            setting = MODEL_SETTINGS[0 if app == "accounts" else 1]
            if re.search(
                rf"(?m)^\s*{setting}\s*(?::[^=\n]+)?(?:=|\+=)", content
            ) or re.search(rf"(?m)^\s*from .+ import .*\b{setting}\b", content):
                raise ValueError(
                    f"custom {app} conflicts with {setting} in {path}; "
                    "keep the template model by choosing no"
                )
            if path.name == "apps.py" and re.search(
                rf"\b(?:name|label)\s*=\s*['\"](?:[\w.]+\.)?{app}['\"]", content
            ):
                raise ValueError(
                    f"custom {app} conflicts with app configuration: {path}"
                )


def build_model_files(
    source_directory: str,
    project_name: str,
    custom_user: bool,
    custom_images: bool,
) -> tuple[RenderedFile, ...]:
    """Render optional applications and validate known conflicts before execution."""
    apps = tuple(
        name
        for name, enabled in (("accounts", custom_user), ("images", custom_images))
        if enabled
    )
    if not apps:
        return ()
    source = Path(source_directory)
    if project_name in apps or (source != Path(".") and source.parts[0] in apps):
        raise ValueError("project or source package conflicts with a custom model app")
    planned = []
    for app in apps:
        module = app if source == Path(".") else f"{'.'.join(source.parts)}.{app}"
        context = {"app": app, "module": module}
        for name in ("__init__.py", "migrations/__init__.py"):
            planned.append(plan_template(source / app / name, "models/empty.py.jinja"))
        planned.append(
            plan_template(
                source / app / "apps.py",
                "models/apps.py.jinja",
                context,
            )
        )
        for name in (
            "models.py",
            "tests.py",
            *(["admin.py"] if app == "accounts" else []),
        ):
            planned.append(
                plan_template(
                    source / app / name,
                    f"models/{app}/{name}.jinja",
                    context,
                )
            )
    return tuple(planned)


def configure_models(
    directory: Path,
    settings_file: Path,
    files: tuple[RenderedFile, ...],
    source_directory: str,
    custom_user: bool,
    custom_images: bool,
    settings_fragment: str,
) -> None:
    """Validate all conflicts, then write apps and settings inside staging."""
    if not files:
        return
    apps = tuple(
        name
        for name, enabled in (("accounts", custom_user), ("images", custom_images))
        if enabled
    )
    source = directory / source_directory
    _validate_conflicts(directory, apps)
    for app in apps:
        if (source / app).exists() or (source / f"{app}.py").exists():
            raise ValueError(
                f"refusing to overwrite custom model app path: {source / app}"
            )
    content = settings_file.read_text()
    tree = ast.parse(content)
    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "INSTALLED_APPS"
            for target in node.targets
        )
    ]
    if len(assignments) != 1 or not isinstance(
        assignments[0].value, (ast.List, ast.Tuple)
    ):
        raise ValueError("custom models require a literal INSTALLED_APPS list or tuple")
    installed = assignments[0].value
    # Check dotted app registrations, including apps without an AppConfig file.
    for item in installed.elts:
        if (
            isinstance(item, ast.Constant)
            and isinstance(item.value, str)
            and not item.value.startswith("wagtail.")
            and any(app in item.value.split(".") for app in apps)
        ):
            raise ValueError(
                f"custom model app conflicts with INSTALLED_APPS: {item.value}"
            )
    # AST columns count UTF-8 bytes; splice the original source without reformatting it.
    lines = content.encode().splitlines(keepends=True)
    offset = sum(map(len, lines[: installed.lineno - 1])) + installed.col_offset + 1
    prefix = (
        "" if source_directory == "." else ".".join(Path(source_directory).parts) + "."
    )
    additions = "".join(f'\n    "{prefix}{app}",' for app in apps).encode()
    updated = (
        content.encode()[:offset] + additions + content.encode()[offset:]
    ).decode()
    write_rendered_files(directory, files)
    settings_file.write_text(updated + "\n" + settings_fragment)
