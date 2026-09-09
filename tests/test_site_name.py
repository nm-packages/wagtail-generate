"""Regression coverage for inserting readable names into Python settings."""

import ast
from pathlib import Path

import pytest

from wagtail_generate.wagtail import _set_wagtail_site_name


@pytest.mark.parametrize(
    "site_name",
    [
        "Example Website",
        "Café",
        "日本語のサイト",
        "Museum 🏛️",
        'The "Example" Website',
        r"C:\new\test",
        r"Group \1 and \g<name>",
        "First line\nSecond line\tTabbed",
    ],
)
def test_site_name_round_trips_through_generated_python(
    tmp_path: Path, site_name: str
) -> None:
    settings = tmp_path / "base.py"
    settings.write_text('WAGTAIL_SITE_NAME = "example"\nDEBUG = False\n')

    _set_wagtail_site_name(settings, site_name)

    content = settings.read_text()
    module = ast.parse(content)
    assignment = module.body[0]
    assert isinstance(assignment, ast.Assign)
    assert ast.literal_eval(assignment.value) == site_name
    assert content.endswith("\nDEBUG = False\n")
