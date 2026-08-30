"""Discoverable codebase layouts supported by wagtail-generate."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Layout:
    """A stable named collection of generated-project templates."""

    name: str
    description: str
    agents_template: str
    readme_template: str


STANDARD_LAYOUT = Layout(
    name="standard",
    description="UV-native Wagtail development with optional Docker databases",
    agents_template="AGENTS.md.jinja",
    readme_template="README.md.jinja",
)

LAYOUTS = {STANDARD_LAYOUT.name: STANDARD_LAYOUT}


def layout_names() -> tuple[str, ...]:
    """Return stable layout names in display order."""
    return tuple(LAYOUTS)


def get_layout(name: str) -> Layout:
    """Return a layout by its stable CLI name."""
    return LAYOUTS[name]
