"""Structural checks for the generated frontend skill and its recipe."""

import json
import re
from pathlib import Path

import pytest

from wagtail_generate.planning import ProjectOptions, build_generation_plan
from wagtail_generate.rendering import write_rendered_files

SKILL_PATH = Path(".agents/skills/wagtail-frontend-setup")


@pytest.mark.parametrize("subfolder", [None, Path("src"), Path("sites/cms")])
def test_skill_is_deterministic_linked_and_has_no_generation_side_effects(
    tmp_path: Path, subfolder: Path | None
) -> None:
    options = ProjectOptions("example", "Example", "sqlite3", tmp_path, subfolder)
    plan = build_generation_plan(options, "3.14")
    assert plan == build_generation_plan(options, "3.14")
    assert list(tmp_path.iterdir()) == []

    write_rendered_files(tmp_path, plan.documentation_files)
    skill = (tmp_path / SKILL_PATH / "SKILL.md").read_text()
    _, frontmatter, body = skill.split("---", 2)
    metadata = dict(line.split(": ", 1) for line in frontmatter.strip().splitlines())
    assert metadata["name"] == SKILL_PATH.name
    assert metadata["description"]
    assert body.strip()

    for file in plan.documentation_files:
        for target in re.findall(r"\]\(([^)]+)\)", file.content):
            if "://" not in target and not target.startswith("#"):
                path = tmp_path / file.relative_path.parent / target.split("#")[0]
                assert path.is_file(), (file.relative_path, target)

    recipe = (tmp_path / SKILL_PATH / "references/sass-esbuild.md").read_text()
    package = json.loads(recipe.split("```json\n", 1)[1].split("```", 1)[0])
    source = subfolder or Path(".")
    for name, suffix in (("css", "css"), ("js", "js")):
        destination = source / f"home/static/home/build/{name}/site.{suffix}"
        assert str(destination) in package["scripts"][f"build:{name}"]
    assert not (tmp_path / "package.json").exists()
    assert not (tmp_path / "node_modules").exists()
    assert all(command.arguments[0] == "uvx" for command in plan.setup_commands)
    assert set(plan.resolved_dependencies.all) == {
        "wagtail",
        "ruff",
        "djangofmt",
        "pre-commit",
    }
