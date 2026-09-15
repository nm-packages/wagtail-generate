"""Optional models remain independent, safe, and consistent across layouts."""

from pathlib import Path
from unittest.mock import patch

import pytest

from wagtail_generate.cli import main, prompt_for_custom_model
from wagtail_generate.model_options import (
    build_model_files,
    configure_models,
)
from wagtail_generate.planning import ProjectOptions, build_generation_plan


@pytest.mark.parametrize(
    "answer,expected",
    [
        ("", False),
        ("n", False),
        (" NO ", False),
        ("Y", True),
        (" yes ", True),
    ],
)
def test_model_prompt(answer, expected, capsys):
    assert (
        prompt_for_custom_model("user", "auth.User", "Create?", lambda _: answer)
        is expected
    )
    assert "Current user model: auth.User" in capsys.readouterr().out


def test_prompt_retries_and_handles_eof(capsys):
    answers = iter(["maybe", "yes"])
    assert prompt_for_custom_model(
        "image", "wagtailimages.Image", "Create?", lambda _: next(answers)
    )
    assert "Please answer yes or no" in capsys.readouterr().out

    def eof(_):
        raise EOFError

    assert not prompt_for_custom_model("user", "auth.User", "Create?", eof)


@pytest.mark.parametrize("interactive", [False, True])
@pytest.mark.parametrize(
    "flags,expected",
    [
        ([], (False, False)),
        (["--custom-user"], (True, False)),
        (["--custom-images"], (False, True)),
        (["--custom-user", "--custom-images"], (True, True)),
        (["--no-custom-user", "--no-custom-images"], (False, False)),
    ],
)
def test_cli_model_choices(tmp_path, interactive, flags, expected):
    with (
        patch("wagtail_generate.cli.sys.stdin.isatty", return_value=interactive),
        patch("builtins.input", return_value="") as read_input,
        patch("wagtail_generate.cli.run_wagtail_start", return_value=0) as generate,
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
                    str(tmp_path / "site"),
                    *flags,
                ]
            )
            == 0
        )
    assert (
        generate.call_args.kwargs["custom_user"],
        generate.call_args.kwargs["custom_images"],
    ) == expected
    assert read_input.call_count == (3 - len(flags) if interactive else 0)


def test_interactive_choices_are_independent(tmp_path, capsys):
    with (
        patch("wagtail_generate.cli.sys.stdin.isatty", return_value=True),
        patch("builtins.input", side_effect=["yes", "no", "no"]),
        patch("wagtail_generate.cli.run_wagtail_start", return_value=0) as generate,
    ):
        main(
            [
                "start",
                "example",
                "--site-name",
                "Example",
                "--site-directory",
                ".",
                "--directory",
                str(tmp_path / "site"),
            ]
        )
    assert generate.call_args.kwargs["custom_user"] is True
    assert generate.call_args.kwargs["custom_images"] is False
    assert "Current image model: wagtailimages.Image" in capsys.readouterr().out


@pytest.mark.parametrize("source", [".", "src", "website.source"])
@pytest.mark.parametrize(
    "user,images", [(False, False), (True, False), (False, True), (True, True)]
)
def test_plan_and_configure_models(tmp_path, source, user, images):
    source = source.replace(".", "/") if source != "." else source
    options = ProjectOptions(
        "example",
        "Example",
        "sqlite3",
        tmp_path,
        None if source == "." else Path(source),
        user,
        images,
    )
    plan = build_generation_plan(options, "3.14")
    settings = tmp_path / source / "settings" / "base.py"
    settings.parent.mkdir(parents=True)
    original = 'INSTALLED_APPS = ["wagtail.images", "home"]\n'
    settings.write_text(original)
    configure_models(
        tmp_path, settings, plan.model_files, source, user, images, plan.model_settings
    )
    contents = settings.read_text()
    compile(contents, "settings", "exec")
    assert ('AUTH_USER_MODEL = "accounts.User"' in contents) == user
    assert ('WAGTAILIMAGES_IMAGE_MODEL = "images.CustomImage"' in contents) == images
    assert bool(plan.model_commands) == (user or images)
    if user or images:
        assert "--no-header" in plan.model_commands[0].arguments
    else:
        assert contents == original
    for app, enabled in (("accounts", user), ("images", images)):
        assert (tmp_path / source / app / "models.py").exists() == enabled
        if enabled:
            module = app if source == "." else source.replace("/", ".") + "." + app
            assert (
                f'name = "{module}"'
                in (tmp_path / source / app / "apps.py").read_text()
            )
    readme = next(
        f.content
        for f in plan.documentation_files
        if str(f.relative_path) == "README.md"
    )
    assert ("accounts.User" if user else "auth.User") in readme
    assert ("images.CustomImage" if images else "wagtailimages.Image") in readme


@pytest.mark.parametrize("source,project", [("accounts", "example"), ("src", "images")])
def test_app_name_collisions(source, project):
    with pytest.raises(ValueError, match="package conflicts"):
        build_model_files(source, project, True, True)


@pytest.mark.parametrize(
    "content,error",
    [
        ("INSTALLED_APPS = get_apps()\n", "literal INSTALLED_APPS"),
        ('INSTALLED_APPS = ["other.accounts"]\n', "INSTALLED_APPS"),
        ('INSTALLED_APPS = []\nAUTH_USER_MODEL = "people.User"\n', "AUTH_USER_MODEL"),
    ],
)
def test_staged_settings_conflicts_leave_files_untouched(tmp_path, content, error):
    settings = tmp_path / "base.py"
    settings.write_text(content)
    files = build_model_files(".", "example", True, False)
    with pytest.raises(ValueError, match=error):
        configure_models(
            tmp_path,
            settings,
            files,
            ".",
            True,
            False,
            "AUTH_USER_MODEL = 'accounts.User'\n",
        )
    assert settings.read_text() == content
    assert not (tmp_path / "accounts").exists()


@pytest.mark.parametrize("path", ["accounts", "accounts.py"])
def test_existing_app_path_is_not_overwritten(tmp_path, path):
    (tmp_path / path).write_text("preserve")
    settings = tmp_path / "base.py"
    settings.write_text("INSTALLED_APPS = []\n")
    files = build_model_files(".", "example", True, False)
    with pytest.raises(ValueError, match="refusing to overwrite"):
        configure_models(
            tmp_path,
            settings,
            files,
            ".",
            True,
            False,
            "AUTH_USER_MODEL = 'accounts.User'\n",
        )
    assert (tmp_path / path).read_text() == "preserve"


def test_tuple_installed_apps_and_unicode(tmp_path):
    settings = tmp_path / "base.py"
    settings.write_text('LABEL = "é"; INSTALLED_APPS = ()\n')
    files = build_model_files(".", "example", True, False)
    configure_models(
        tmp_path,
        settings,
        files,
        ".",
        True,
        False,
        "AUTH_USER_MODEL = 'accounts.User'\n",
    )
    namespace = {}
    exec(settings.read_text(), namespace)
    assert namespace["INSTALLED_APPS"] == ("accounts",)


def test_swappable_references_are_not_conflicts(tmp_path):
    (tmp_path / "models.py").write_text(
        "from django.conf import settings\n"
        "# AUTH_USER_MODEL is intentionally swappable\n"
        "owner = models.ForeignKey(\n"
        "    settings.AUTH_USER_MODEL, on_delete=models.CASCADE)\n"
    )
    assert build_model_files(".", "example", True, False)
