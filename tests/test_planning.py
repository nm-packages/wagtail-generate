"""Tests for named layouts and typed generation plans."""

from pathlib import Path

import pytest

from wagtail_generate.layouts import STANDARD_LAYOUT, get_layout, layout_names
from wagtail_generate.wagtail import ProjectOptions, build_generation_plan


@pytest.mark.parametrize(
    ("project_name", "subfolder"),
    [("site", None), ("example", Path("site")), ("example", Path("email/cms"))],
)
def test_plan_rejects_standard_library_source_package(
    project_name: str, subfolder: Path | None, tmp_path: Path
) -> None:
    options = ProjectOptions(
        project_name, "Example", "sqlite3", tmp_path / "generated", subfolder, None
    )
    with pytest.raises(ValueError, match="conflicts with Python's standard library"):
        build_generation_plan(options, "3.14")
    assert not options.project_root.exists()


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
        Path("docs/agent-instructions/environment.md"),
        Path("docs/agent-instructions/backend.md"),
        Path("docs/agent-instructions/checks.md"),
    }


@pytest.mark.parametrize(
    ("project_name", "subfolder"),
    [("django", None), ("example", Path("django")), ("example", Path("wagtail/cms"))],
)
def test_plan_rejects_dependency_source_package(
    project_name: str, subfolder: Path | None, tmp_path: Path
) -> None:
    options = ProjectOptions(
        project_name, "Example", "sqlite3", tmp_path / "generated", subfolder, None
    )
    with pytest.raises(
        ValueError, match="conflicts with a generated-project dependency"
    ):
        build_generation_plan(options, "3.14")
    assert not options.project_root.exists()


def test_documentation_preserves_custom_agent_guidance(tmp_path: Path) -> None:
    from wagtail_generate.rendering import write_rendered_files

    options = ProjectOptions("example", "Example", "sqlite3", tmp_path, None, None)
    plan = build_generation_plan(options, "3.14")
    custom_paths = (
        Path("AGENTS.md"),
        Path("docs/agent-instructions/backend.md"),
    )
    for path in custom_paths:
        destination = tmp_path / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("Custom project guidance\n")

    write_rendered_files(tmp_path, plan.documentation_files)

    for path in custom_paths:
        assert (tmp_path / path).read_text() == "Custom project guidance\n"
    assert (tmp_path / "docs/agent-instructions/checks.md").is_file()
    assert (tmp_path / "docs/agent-instructions/environment.md").is_file()
