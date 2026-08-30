"""Load and render files shipped with the generator package."""

from collections.abc import Mapping
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, StrictUndefined

_ENVIRONMENT = Environment(
    autoescape=False,
    keep_trailing_newline=True,
    undefined=StrictUndefined,
)


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
