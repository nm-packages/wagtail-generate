"""Starter homepage selection, rendering, and custom-template boundaries."""

from pathlib import Path
from unittest.mock import patch

import pytest

from wagtail_generate.cli import main
from wagtail_generate.homepage import (
    HOME_TEMPLATE,
    WELCOME_FILES,
    build_homepage_files,
    configure_homepage,
    plan_homepage_removals,
)
from wagtail_generate.planning import ProjectOptions, build_generation_plan


def make_home(source, model="class HomePage(Page):\n    pass\n"):
    path = source / HOME_TEMPLATE
    path.parent.mkdir(parents=True)
    path.write_text("Custom homepage")
    (source / "home/models.py").write_text(model)


@pytest.mark.parametrize("enabled", [False, True])
def test_cli_choice(tmp_path, enabled):
    with patch("wagtail_generate.cli.run_wagtail_start", return_value=0) as run:
        assert (
            main(
                [
                    "start",
                    "example",
                    "--site-name",
                    "Example",
                    "--site-directory",
                    ".",
                    "--directory",
                    str(tmp_path),
                    "--no-custom-user",
                    "--no-custom-images",
                    *(["--starter-homepage"] if enabled else []),
                ]
            )
            == 0
        )
    assert run.call_args.kwargs["starter_homepage"] is enabled


@pytest.mark.parametrize("source", [".", "src", "website/source"])
@pytest.mark.parametrize("enabled", [False, True])
def test_plan_and_custom_homepage_replacement(tmp_path, source, enabled):
    template = tmp_path / "template"
    make_home(template)
    destination = tmp_path / "output"
    make_home(destination / source)
    for relative_path in (*WELCOME_FILES, Path("home/static/css/custom.css")):
        path = destination / source / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original")
    options = ProjectOptions(
        "example",
        "Example",
        "sqlite3",
        destination,
        None if source == "." else Path(source),
        template,
        starter_homepage=enabled,
    )
    plan = build_generation_plan(options, "3.14")
    configure_homepage(
        destination,
        source,
        plan.homepage_files,
        plan.homepage_removals,
    )
    for relative_path in WELCOME_FILES:
        assert (destination / source / relative_path).exists() is not enabled
    assert (
        destination / source / "home/static/css/custom.css"
    ).read_text() == "original"
    html = (destination / source / HOME_TEMPLATE).read_text()
    assert (template / HOME_TEMPLATE).read_text() == "Custom homepage"
    if enabled:
        assert "<main" in html
        assert "welcome_page" not in html
        assert "base.html" not in html
        assert "{% static 'home/css/starter-homepage.css' %}" in html
        css = destination / source / "home/static/home/css/starter-homepage.css"
        assert "clamp(" in css.read_text()
    else:
        assert html == "Custom homepage"
        assert not plan.homepage_files


@pytest.mark.parametrize(
    "model",
    [
        "class OtherPage(Page): pass",
        "class HomePage(CustomPage): pass",
        "class HomePage(Page):\n    template = 'other.html'",
        "class HomePage(Page):\n    def serve(self, request): pass",
        "class HomePage(Page):\n    def get_template(self, request): pass",
        "not valid python!",
    ],
)
def test_unsupported_custom_models_fail_without_writes(tmp_path, model):
    make_home(tmp_path, model)
    assert build_homepage_files(".", False, tmp_path) == ()
    with pytest.raises(ValueError, match="--starter-homepage requires"):
        build_homepage_files(".", True, tmp_path)
    files = build_homepage_files(".", True, None)
    with pytest.raises(ValueError, match="--starter-homepage requires"):
        configure_homepage(tmp_path, ".", files)
    assert (tmp_path / HOME_TEMPLATE).read_text() == "Custom homepage"


def test_missing_or_archive_template(tmp_path):
    for template in (tmp_path, tmp_path / "template.zip"):
        assert build_homepage_files(".", False, template) == ()
        with pytest.raises(ValueError, match="--starter-homepage requires"):
            build_homepage_files(".", True, template)


@pytest.mark.parametrize(
    "interactive,flags,answers,expected,prompt_count",
    [
        (True, [], ["yes"], True, 1),
        (True, [], [""], False, 1),
        (True, [], ["no"], False, 1),
        (True, [], ["maybe", "y"], True, 2),
        (True, [], [EOFError()], False, 1),
        (True, ["--starter-homepage"], [], True, 0),
        (True, ["--no-starter-homepage"], [], False, 0),
        (False, [], [], False, 0),
        (False, ["--starter-homepage"], [], True, 0),
        (False, ["--no-starter-homepage"], [], False, 0),
    ],
)
@pytest.mark.parametrize("custom_template", [False, True])
def test_runtime_homepage_choice(
    tmp_path,
    interactive,
    flags,
    answers,
    expected,
    prompt_count,
    custom_template,
):
    template_flags = []
    if custom_template:
        template = tmp_path / "template"
        make_home(template)
        template_flags = ["--template", str(template)]
    with (
        patch("wagtail_generate.cli.sys.stdin.isatty", return_value=interactive),
        patch("builtins.input", side_effect=answers) as read_input,
        patch("wagtail_generate.cli.run_wagtail_start", return_value=0) as run,
    ):
        assert (
            main(
                [
                    "start",
                    "example",
                    "--site-name",
                    "Example",
                    "--site-directory",
                    ".",
                    "--directory",
                    str(tmp_path / "output"),
                    "--no-custom-user",
                    "--no-custom-images",
                    *template_flags,
                    *flags,
                ]
            )
            == 0
        )
    assert run.call_args.kwargs["starter_homepage"] is expected
    assert read_input.call_count == prompt_count
    if prompt_count:
        assert read_input.call_args.args == (
            "Replace the template homepage with a simple styled starter? [y/N]: ",
        )


@pytest.mark.parametrize("kind", ["file_symlink", "parent_symlink", "directory"])
def test_cleanup_rejects_unsafe_paths_before_changes(tmp_path, kind):
    source = tmp_path / "project"
    make_home(source)
    external = tmp_path / "external"
    external.mkdir()
    (external / "welcome_page.css").write_text("preserve")
    css = source / "home/static/css/welcome_page.css"
    css.parent.parent.mkdir(parents=True)
    if kind == "parent_symlink":
        css.parent.symlink_to(external, target_is_directory=True)
    else:
        css.parent.mkdir()
        if kind == "file_symlink":
            css.symlink_to(external / "welcome_page.css")
        else:
            css.mkdir()
    with pytest.raises(ValueError, match="unsupported welcome-page cleanup path"):
        configure_homepage(
            source,
            ".",
            build_homepage_files(".", True, None),
            plan_homepage_removals(".", True),
        )
    assert (external / "welcome_page.css").read_text() == "preserve"
    assert (source / HOME_TEMPLATE).read_text() == "Custom homepage"


def test_cleanup_tolerates_missing_welcome_files(tmp_path):
    make_home(tmp_path)
    configure_homepage(
        tmp_path,
        ".",
        build_homepage_files(".", True, None),
        plan_homepage_removals(".", True),
    )
    assert "<main" in (tmp_path / HOME_TEMPLATE).read_text()
