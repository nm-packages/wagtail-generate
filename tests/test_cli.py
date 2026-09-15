"""Tests for the command-line interface."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from wagtail_generate import __version__
from wagtail_generate.cli import (
    display_site_name,
    main,
    normalize_package_name,
    normalize_subfolder,
    prompt_for_site_name,
    prompt_for_site_subfolder,
)


def test_cli_without_arguments_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0

    output = capsys.readouterr().out
    assert "Generate an opinionated Wagtail CMS project" in output


def test_cli_reports_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["--version"])

    output = capsys.readouterr().out
    assert output.strip() == f"wagtail-generate {__version__}"


@pytest.mark.parametrize(
    ("value", "normalized"),
    [("123site", "site_123site"), ("class", "class_site")],
)
def test_normalize_package_name_avoids_invalid_python_names(
    value: str, normalized: str
) -> None:
    assert normalize_package_name(value) == normalized


def test_subfolder_prompt_retries_invalid_answer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    responses = iter(["maybe", "no"])

    assert prompt_for_site_subfolder("example", lambda _: next(responses)) is None
    assert "Please answer yes or no." in capsys.readouterr().out


@patch("wagtail_generate.cli.run_wagtail_start")
def test_start_rejects_removed_layout_option(
    run_start: Mock, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit, match="2"):
        main(["start", "example", "--layout", "standard"])

    assert "unrecognized arguments: --layout standard" in capsys.readouterr().err
    run_start.assert_not_called()


@pytest.mark.parametrize(
    ("database", "expected_result"), [("postgresql", 0), ("sqlite3", 1)]
)
@patch("wagtail_generate.cli.run_wagtail_start")
def test_start_forwards_options_and_exit_code(
    run_start: Mock,
    database: str,
    expected_result: int,
    tmp_path: Path,
) -> None:
    run_start.return_value = expected_result
    output = tmp_path / "output"

    assert (
        main(
            [
                "start",
                "example",
                "--site-name",
                "Example Website",
                "--database",
                database,
                "--directory",
                str(output),
                "--site-directory",
                ".",
            ]
        )
        == expected_result
    )

    run_start.assert_called_once_with(
        project_name="example",
        site_name="Example Website",
        database=database,
        project_root=output,
        site_subfolder=None,
        template=None,
        custom_user=False,
        custom_images=False,
        starter_homepage=False,
    )
    assert not output.exists()


@pytest.mark.parametrize("state", ["absent", "empty", "nonempty"])
@patch("wagtail_generate.cli.run_wagtail_start", return_value=0)
@patch("wagtail_generate.cli.source_checkout_root", return_value=None)
def test_start_validates_site_name_directory_by_default(
    find_checkout: Mock,
    run_start: Mock,
    state: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    destination = tmp_path / "example_site"
    if state != "absent":
        destination.mkdir()
    if state == "nonempty":
        (destination / ".hidden-file").write_text("existing")
    monkeypatch.chdir(tmp_path)

    result = main(
        [
            "start",
            "example",
            "--site-name",
            "Example Site",
            "--database",
            "postgresql",
            "--site-directory",
            ".",
        ]
    )

    if state == "nonempty":
        assert result == 2
        error = capsys.readouterr().err
        assert f"project root must be empty: {destination}" in error
        assert ".hidden-file" in error
        run_start.assert_not_called()
    else:
        action = "Using" if state == "empty" else "Created"
        assert result == 0
        assert f"{action} project directory: {destination}" in capsys.readouterr().out
        run_start.assert_called_once_with(
            project_name="example",
            site_name="Example Site",
            database="postgresql",
            project_root=destination,
            site_subfolder=None,
            template=None,
            custom_user=False,
            custom_images=False,
            starter_homepage=False,
        )
    find_checkout.assert_called_once_with()


@pytest.mark.parametrize("site_name", ["日本語のサイト", "🏛️"])
@pytest.mark.parametrize("prompted", [False, True])
@patch("wagtail_generate.cli.run_wagtail_start", return_value=0)
def test_non_ascii_site_name_uses_project_name_as_directory_fallback(
    run_start: Mock,
    site_name: str,
    prompted: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    arguments = ["start", "CMS Package", "--site-directory", "."]
    if prompted:
        monkeypatch.setattr("builtins.input", lambda _: site_name)
    else:
        arguments.extend(["--site-name", site_name])
    destination = tmp_path / "cms_package"

    assert main(arguments) == 0

    run_start.assert_called_once_with(
        project_name="cms_package",
        site_name=site_name,
        database="sqlite3",
        project_root=destination,
        site_subfolder=None,
        template=None,
        custom_user=False,
        custom_images=False,
        starter_homepage=False,
    )
    assert not destination.exists()


@patch("wagtail_generate.cli.run_wagtail_start")
def test_start_rejects_invalid_project_name(
    run_start: Mock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(["start", "!!!", "--site-name", "Example"])

    assert result == 2
    assert "name must contain at least one letter or number" in capsys.readouterr().err
    run_start.assert_not_called()


@patch("wagtail_generate.cli.run_wagtail_start")
def test_start_reports_eof_while_prompting_for_site_name(
    run_start: Mock,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def raise_eof(_: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    assert main(["start", "example"]) == 2
    assert "site name is required" in capsys.readouterr().err
    run_start.assert_not_called()


@patch("wagtail_generate.cli.run_wagtail_start")
def test_start_rejects_project_root_that_is_not_a_directory(
    run_start: Mock,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    destination = tmp_path / "project"
    destination.write_text("not a directory")

    result = main(
        [
            "start",
            "example",
            "--site-name",
            "Example",
            "--directory",
            str(destination),
            "--site-directory",
            ".",
        ]
    )

    assert result == 2
    assert "project root is not a directory" in capsys.readouterr().err
    run_start.assert_not_called()


@patch("wagtail_generate.cli.run_wagtail_start")
def test_start_reports_eof_while_prompting_for_source_location(
    run_start: Mock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def raise_eof(_: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    assert (
        main(
            [
                "start",
                "example",
                "--site-name",
                "Example",
                "--directory",
                str(tmp_path),
            ]
        )
        == 2
    )
    assert "source location is required" in capsys.readouterr().err
    run_start.assert_not_called()


@pytest.mark.parametrize("subfolder", ["Site", "site/example"])
@patch("wagtail_generate.cli.run_wagtail_start")
def test_start_rejects_standard_library_subfolder_before_generation(
    run_start: Mock,
    subfolder: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    destination = tmp_path / "generated"
    assert (
        main(
            [
                "start",
                "example",
                "--site-name",
                "Example",
                "--directory",
                str(destination),
                "--site-directory",
                subfolder,
            ]
        )
        == 2
    )
    assert "conflicts with Python's standard library" in capsys.readouterr().err
    assert not destination.exists()
    run_start.assert_not_called()


@pytest.mark.parametrize("subfolder", ["django", "wagtail/cms"])
@patch("wagtail_generate.cli.run_wagtail_start")
def test_start_rejects_dependency_subfolder_before_generation(
    run_start: Mock,
    subfolder: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    destination = tmp_path / "generated"
    assert (
        main(
            [
                "start",
                "example",
                "--site-name",
                "Example",
                "--directory",
                str(destination),
                "--site-directory",
                subfolder,
            ]
        )
        == 2
    )
    assert "conflicts with a generated-project dependency" in capsys.readouterr().err
    assert not destination.exists()
    run_start.assert_not_called()


@pytest.mark.parametrize(
    ("invalid", "message"),
    [
        ("django", "conflicts with a generated-project dependency"),
        ("site", "conflicts with Python's standard library"),
    ],
)
def test_subfolder_prompt_retries_conflicting_name(
    invalid: str,
    message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    responses = iter(["yes", invalid, "src"])
    assert prompt_for_site_subfolder("example", lambda _: next(responses)) == Path(
        "src"
    )
    assert message in capsys.readouterr().out


@pytest.mark.parametrize("value", ["src/django", "src/site"])
def test_nested_package_can_use_conflicting_name(value: str) -> None:
    assert normalize_subfolder(value) == Path(value)


@patch("wagtail_generate.cli.run_wagtail_start", return_value=0)
@patch("wagtail_generate.cli.source_checkout_root", return_value=None)
def test_start_resolves_relative_template_from_invocation_directory(
    find_checkout: Mock,
    run_start: Mock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template = tmp_path / "templates" / "custom"
    template.mkdir(parents=True)
    destination = tmp_path / "generated" / "example"
    monkeypatch.chdir(tmp_path)

    result = main(
        [
            "start",
            "example",
            "--site-name",
            "Example",
            "--directory",
            str(destination),
            "--site-directory",
            ".",
            "--template",
            "templates/custom",
        ]
    )

    assert result == 0
    assert run_start.call_args.kwargs["template"] == template
    find_checkout.assert_called_once_with()


@patch("wagtail_generate.cli.run_wagtail_start")
@patch("wagtail_generate.cli.source_checkout_root", return_value=None)
def test_start_refuses_missing_template_before_creating_project(
    find_checkout: Mock,
    run_start: Mock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    destination = tmp_path / "generated" / "example"
    monkeypatch.chdir(tmp_path)

    result = main(
        [
            "start",
            "example",
            "--site-name",
            "Example",
            "--directory",
            str(destination),
            "--site-directory",
            ".",
            "--template",
            "missing-template",
        ]
    )

    assert result == 2
    assert "Wagtail project template does not exist" in capsys.readouterr().err
    assert not destination.exists()
    run_start.assert_not_called()
    find_checkout.assert_called_once_with()


@pytest.mark.parametrize(
    ("responses", "expected", "message"),
    [
        (("",), None, None),
        (("yes", ""), Path("example"), None),
        (("y", "sites/example"), Path("sites/example"), None),
        (("y", "website source"), Path("website_source"), "Using subfolder name:"),
    ],
)
def test_subfolder_prompt_selects_and_normalizes_layout(
    responses: tuple[str, ...],
    expected: Path | None,
    message: str | None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    response_iterator = iter(responses)

    subfolder = prompt_for_site_subfolder(
        "example",
        input_fn=lambda _: next(response_iterator),
    )

    assert subfolder == expected
    if message is not None:
        assert message in capsys.readouterr().out


def test_human_readable_name_is_normalized() -> None:
    assert normalize_package_name("This is my site") == "this_is_my_site"


def test_display_site_name_removes_package_separators() -> None:
    assert display_site_name("this_is-my site") == "This Is My Site"


@pytest.mark.parametrize(
    ("default_name", "response", "expected"),
    [
        ("Src", "Example heritage centre", "Example heritage centre"),
        ("Example Site", "", "Example Site"),
    ],
)
def test_site_name_prompt_accepts_custom_and_default_values(
    default_name: str,
    response: str,
    expected: str,
) -> None:
    assert prompt_for_site_name(default_name, input_fn=lambda _: response) == expected


@patch("wagtail_generate.cli.run_wagtail_start", return_value=0)
def test_start_uses_normalized_project_name(
    run_start: Mock,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "start",
                "this is my site",
                "--site-name",
                "Editorial website",
                "--database",
                "mysql",
                "--directory",
                str(tmp_path),
                "--site-directory",
                ".",
            ]
        )
        == 0
    )

    assert "Using Python project name: this_is_my_site" in capsys.readouterr().out
    run_start.assert_called_once_with(
        project_name="this_is_my_site",
        site_name="Editorial website",
        database="mysql",
        project_root=tmp_path,
        site_subfolder=None,
        template=None,
        custom_user=False,
        custom_images=False,
        starter_homepage=False,
    )


@patch("wagtail_generate.cli.run_wagtail_start")
@patch("wagtail_generate.cli.source_checkout_root")
def test_start_refuses_destination_inside_tool_checkout(
    find_checkout: Mock,
    run_start: Mock,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    checkout = tmp_path / "wagtail-generate"
    destination = checkout / "src"
    find_checkout.return_value = checkout

    result = main(
        [
            "start",
            "example",
            "--site-name",
            "Example",
            "--database",
            "postgresql",
            "--directory",
            str(destination),
            "--site-directory",
            ".",
        ]
    )

    assert result == 2
    assert "refusing to generate" in capsys.readouterr().err
    assert not destination.exists()
    run_start.assert_not_called()


@pytest.mark.parametrize("prompted", [False, True])
@pytest.mark.parametrize("name", ["EXAMPLE's iWidget eShop", "Café  🏛️"])
@patch("wagtail_generate.cli.run_wagtail_start", return_value=0)
def test_explicit_site_names_are_preserved(
    run_start: Mock,
    prompted: bool,
    name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments = [
        "start",
        "example",
        "--directory",
        str(tmp_path),
        "--site-directory",
        ".",
    ]
    value = f"  {name}  "
    if prompted:
        monkeypatch.setattr("builtins.input", lambda _: value)
    else:
        arguments.extend(["--site-name", value])

    assert main(arguments) == 0
    assert run_start.call_args.kwargs["site_name"] == name


@pytest.mark.parametrize("prompted", [False, True])
@pytest.mark.parametrize("invalid", ["   ", "A\x00B"])
@patch("wagtail_generate.cli.run_wagtail_start", return_value=0)
def test_invalid_site_names_are_rejected_consistently(
    run_start: Mock,
    prompted: bool,
    invalid: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    destination = tmp_path / "site"
    arguments = [
        "start",
        "example",
        "--directory",
        str(destination),
        "--site-directory",
        ".",
    ]
    if prompted:
        responses = iter([invalid, "EXAMPLE's Site"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        assert main(arguments) == 0
        assert run_start.call_args.kwargs["site_name"] == "EXAMPLE's Site"
        assert "Invalid site name:" in capsys.readouterr().out
    else:
        arguments.extend(["--site-name", invalid])
        assert main(arguments) == 2
        run_start.assert_not_called()
        assert "error: --site-name:" in capsys.readouterr().err
    assert not destination.exists()


@patch("wagtail_generate.cli.run_wagtail_start", return_value=0)
def test_default_site_name_is_derived_from_package(
    run_start: Mock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts: list[str] = []

    def accept_default(prompt: str) -> str:
        prompts.append(prompt)
        return ""

    monkeypatch.setattr("builtins.input", accept_default)
    assert (
        main(
            [
                "start",
                "my-example_site",
                "--directory",
                str(tmp_path),
                "--site-directory",
                ".",
            ]
        )
        == 0
    )
    assert prompts == ["Site name [My Example Site]: "]
    assert run_start.call_args.kwargs["site_name"] == "My Example Site"
