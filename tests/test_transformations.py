"""Test source-layout transformations independently from command execution."""

import subprocess
import sys
from pathlib import Path

import pytest

from wagtail_generate.transformations import (
    ProjectStructureError,
    adjust_app_config,
    adjust_settings,
    flatten_project_package,
    rewrite_imports,
    rewrite_python_files,
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
        "import sites.example.home.models as _wagtail_import_home_models"
        "  # noqa: F401\n"
        "import sites.example.home as home\n"
        "import sites.example.settings as _wagtail_import_example_settings"
        "  # noqa: F401\n"
        "import sites.example as example\n"
        "from django.db import models\n"
        "value = models.Model\n"
        'label = "example.Model"\n'
    )


@pytest.mark.parametrize("destination_module", ["src", "sites.example"])
@pytest.mark.parametrize(
    "code",
    [
        "import home.models\nassert home.models.VALUE == 42\n",
        "import search.views\nassert search.views.VALUE == 42\n",
        "import example.settings\nassert example.settings.VALUE == 42\n",
        "import home.models as models\nassert models.VALUE == 42\n",
        "import example.settings as settings\nassert settings.VALUE == 42\n",
        "import home\nassert home.NAME == 'home'\n",
        "import example\nassert example.NAME == 'project'\n",
        "from home import models\nassert models.VALUE == 42\n",
        "from example import settings\nassert settings.VALUE == 42\n",
        "import json, home.models, example.settings as settings\n"
        "assert json.loads('42') == home.models.VALUE == settings.VALUE\n",
        "def check():\n    import home.models\n    return home.models.VALUE\n"
        "assert check() == 42\n",
        "label = 'café'; import home.models\nassert home.models.VALUE == 42\n",
        "src = 'existing binding'\nimport home.models\n"
        "assert src == 'existing binding'\nassert home.models.VALUE == 42\n",
        "_wagtail_import_home_models = 'existing binding'\nimport home.models\n"
        "assert _wagtail_import_home_models == 'existing binding'\n"
        "assert home.models.VALUE == 42\n",
    ],
)
def test_rewritten_imports_preserve_runtime_bindings(
    tmp_path: Path, destination_module: str, code: str
) -> None:
    source = tmp_path.joinpath(*destination_module.split("."))
    for app in ("home", "search"):
        directory = source / app
        directory.mkdir(parents=True)
        (directory / "__init__.py").write_text(f"NAME = {app!r}\n")
    (source / "__init__.py").write_text("NAME = 'project'\n")
    for path in ("home/models.py", "search/views.py", "settings.py"):
        (source / path).write_text("VALUE = 42\n")
    transformed = rewrite_imports(code, "example", destination_module)
    subprocess.run([sys.executable, "-c", transformed], cwd=tmp_path, check=True)


def test_rewriting_preserves_relative_imports_comments_and_unrelated_strings() -> None:
    content = (
        "# import home.models\n"
        'description = "from home import models"\n'
        "from .home import models\n"
        "from . import home\n"
        "import example_other\n"
    )
    assert rewrite_imports(content, "example", "src") == content


def test_from_import_preserves_comments_and_aliases() -> None:
    content = (
        "from home.models import (\n"
        "    HomePage as Page,  # Keep the public alias.\n"
        ")\n"
    )
    assert rewrite_imports(content, "example", "src") == content.replace(
        "from home.models", "from src.home.models"
    )


def test_rewritten_imports_still_work_after_ruff_fixes(tmp_path: Path) -> None:
    source = tmp_path / "src" / "home"
    source.mkdir(parents=True)
    (source / "models.py").write_text("VALUE = 42\n")
    script = tmp_path / "probe.py"
    script.write_text(
        rewrite_imports(
            "import home.models\nfrom json import loads\n"
            "assert home.models.VALUE == loads('42')\n",
            "example",
            "src",
        )
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--isolated",
            "--fix",
            "--select",
            "E,F,I,UP,B,SIM",
            str(script),
        ],
        check=True,
    )
    subprocess.run([sys.executable, str(script)], cwd=tmp_path, check=True)


def test_invalid_python_reports_a_structure_error(tmp_path: Path) -> None:
    (tmp_path / "invalid.py").write_text("import (\n")
    with pytest.raises(ProjectStructureError, match="invalid.py"):
        rewrite_python_files(tmp_path, "example", "src")


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


def test_settings_transformation_requires_the_generated_base_directory() -> None:
    with pytest.raises(ProjectStructureError, match="BASE_DIR"):
        adjust_settings("INSTALLED_APPS = []\n", "sites.example")


def test_app_config_transformation_requires_the_generated_app_name() -> None:
    with pytest.raises(ProjectStructureError, match="name ="):
        adjust_app_config("class HomeConfig:\n", "sites.example")


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
