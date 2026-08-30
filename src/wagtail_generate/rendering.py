"""Load and render files shipped with the generator package."""

from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, StrictUndefined

_ENVIRONMENT = Environment(
    autoescape=False,
    keep_trailing_newline=True,
    undefined=StrictUndefined,
)


@dataclass(frozen=True)
class RenderedFile:
    """Content and metadata for one validated generated file."""

    relative_path: Path
    content: str
    mode: int | None = None
    overwrite: bool = True


def template_text(relative_path: str) -> str:
    """Read a UTF-8 template resource from the installed package."""
    resource = files("wagtail_generate").joinpath(
        "templates", *Path(relative_path).parts
    )
    return resource.read_text(encoding="utf-8")


def render_template(relative_path: str, context: Mapping[str, object]) -> str:
    """Render one packaged template with strict variable handling."""
    template = _ENVIRONMENT.from_string(template_text(relative_path))
    return template.render(**context)


def write_template(
    destination: Path,
    relative_path: str,
    context: Mapping[str, object] | None = None,
    mode: int | None = None,
) -> None:
    """Render or copy a packaged template to a generated project."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = (
        template_text(relative_path)
        if context is None
        else render_template(relative_path, context)
    )
    destination.write_text(content)
    if mode is not None:
        destination.chmod(mode)


def plan_template(
    relative_destination: str | Path,
    relative_template: str,
    context: Mapping[str, object] | None = None,
    mode: int | None = None,
    *,
    overwrite: bool = True,
) -> RenderedFile:
    """Render and validate a file before generation starts."""
    destination = Path(relative_destination)
    if destination.is_absolute() or ".." in destination.parts:
        raise ValueError("generated file paths must stay inside the project root")
    content = (
        template_text(relative_template)
        if context is None
        else render_template(relative_template, context)
    )
    return RenderedFile(destination, content, mode, overwrite)


def write_rendered_files(
    project_directory: Path, files: tuple[RenderedFile, ...]
) -> None:
    """Write a previously rendered and validated file plan."""
    for generated_file in files:
        destination = project_directory / generated_file.relative_path
        if destination.exists() and not generated_file.overwrite:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(generated_file.content)
        if generated_file.mode is not None:
            destination.chmod(generated_file.mode)
