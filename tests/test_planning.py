"""Tests for named layouts and typed generation plans."""

from pathlib import Path

from wagtail_generate.layouts import STANDARD_LAYOUT, get_layout, layout_names
from wagtail_generate.wagtail import ProjectOptions, build_generation_plan


def test_standard_layout_is_discoverable_by_stable_name() -> None:
    assert layout_names() == ("standard",)
    assert get_layout("standard") is STANDARD_LAYOUT


def test_complete_plan_is_rendered_without_writing_destination(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "generated"
    options = ProjectOptions(
        project_name="example",
        site_name="Example Site",
        database="postgresql",
        project_root=project_root,
        site_subfolder=Path("sites/example"),
        template=None,
    )

    plan = build_generation_plan(options, "3.14")

    assert not project_root.exists()
    assert plan.options is options
    assert plan.python_version == "3.14"
    assert plan.wagtail_command.arguments[-2:] == ("example", "sites/example")
    assert plan.setup_commands[3].arguments[-2:] == (
        "wagtail",
        "psycopg[binary]",
    )
    tooling_paths = {
        generated_file.relative_path for generated_file in plan.developer_tooling.files
    }
    assert Path("Dockerfile") in tooling_paths
    assert Path("compose.yaml") in tooling_paths
    assert {file.relative_path for file in plan.documentation_files} == {
        Path("AGENTS.md"),
        Path("README.md"),
    }
