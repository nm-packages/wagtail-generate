"""Test source-layout transformations independently from command execution."""

from pathlib import Path

import pytest

from wagtail_generate.transformations import (
    ProjectStructureError,
    adjust_app_config,
    adjust_settings,
    flatten_project_package,
    rewrite_imports,
)


def test_rewrite_imports_only_changes_module_references() -> None:
    content = (
        "from example.home.models import HomePage\n"
        "import home.models\n"
        "import example.settings\n"
        "from django.db import models\n"
        "value = models.Model\n"
        'label = "example.Model"\n'
    )

    assert rewrite_imports(content, "example", "sites.example") == (
        "from sites.example.home.models import HomePage\n"
        "import sites.example.home.models\n"
        "import sites.example.settings\n"
        "from django.db import models\n"
        "value = models.Model\n"
        'label = "example.Model"\n'
    )


def test_settings_and_app_config_transformations_are_string_operations() -> None:
    settings = 'BASE_DIR = PROJECT_DIR.parent\nINSTALLED_APPS = ["home", "search"]\n'
    app_config = 'class HomeConfig:\n    name = "home"\n'

    assert adjust_settings(settings, "sites.example") == (
        "BASE_DIR = PROJECT_DIR.parent.parent\n"
        'INSTALLED_APPS = ["sites.example.home", "sites.example.search"]\n'
    )
    assert adjust_app_config(app_config, "sites.example") == (
        'class HomeConfig:\n    name = "sites.example.home"\n'
    )


def test_flatten_validates_required_template_structure_before_moving(
    tmp_path: Path,
) -> None:
    package = tmp_path / "src" / "example"
    (package / "settings").mkdir(parents=True)
    (package / "settings" / "base.py").write_text("BASE_DIR = PROJECT_DIR.parent\n")

    with pytest.raises(ProjectStructureError, match="home/apps.py"):
        flatten_project_package(tmp_path / "src", "example", "src")

    assert package.is_dir()
    assert not (tmp_path / "src" / "settings").exists()
