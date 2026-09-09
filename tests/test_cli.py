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
from wagtail_generate.layouts import STANDARD_LAYOUT


def test_cli_without_arguments_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0

    output = capsys.readouterr().out
    assert "Generate an opinionated Wagtail CMS project" in output


def test_cli_reports_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["--version"])

    output = capsys.readouterr().out
    assert output.strip() == f"wagtail-generate {__version__}"


@patch("wagtail_generate.cli.run_wagtail_start", return_value=0)
def test_start_runs_wagtail_command(run_start: Mock, tmp_path: Path) -> None:
    output = tmp_path / "output"

    assert (
        main(
            [
                "start",
                "example",
                "--site-name",
                "Example Website",
                "--database",
                "postgresql",
                "--directory",
                str(output),
                "--site-directory",
                ".",
            ]
        )
        == 0
    )

    run_start.assert_called_once_with(
        project_name="example",
        site_name="Example Website",
        database="postgresql",
        project_root=output,
        site_subfolder=None,
        template=None,
        layout=STANDARD_LAYOUT,
    )
    assert not output.exists()


@patch("wagtail_generate.cli.run_wagtail_start", return_value=0)
@patch("wagtail_generate.cli.source_checkout_root", return_value=None)
def test_start_creates_site_name_directory_by_default(
    find_checkout: Mock,
    run_start: Mock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    result = main(
        [
            "start",
            "cms_package",
            "--site-name",
            "Editorial Website",
            "--database",
            "postgresql",
            "--site-directory",
            ".",
        ]
    )

    destination = tmp_path / "editorial_website"
    assert result == 0
    assert not destination.exists()
    assert f"Created project directory: {destination}" in capsys.readouterr().out
    run_start.assert_called_once_with(
        project_name="cms_package",
        site_name="Editorial Website",
        database="postgresql",
        project_root=destination,
        site_subfolder=None,
        template=None,
        layout=STANDARD_LAYOUT,
    )
    find_checkout.assert_called_once_with()


@patch("wagtail_generate.cli.run_wagtail_start", return_value=0)
@patch("wagtail_generate.cli.source_checkout_root", return_value=None)
def test_start_accepts_existing_empty_site_name_directory(
    find_checkout: Mock,
    run_start: Mock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    destination = tmp_path / "example_site"
    destination.mkdir()
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

    assert result == 0
    assert run_start.call_args.kwargs["project_root"] == destination
    assert f"Using project directory: {destination}" in capsys.readouterr().out
    find_checkout.assert_called_once_with()


@patch("wagtail_generate.cli.run_wagtail_start")
@patch("wagtail_generate.cli.source_checkout_root", return_value=None)
def test_start_refuses_nonempty_site_name_directory(
    find_checkout: Mock,
    run_start: Mock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    destination = tmp_path / "example_site"
    destination.mkdir()
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

    assert result == 2
    error = capsys.readouterr().err
    assert f"project root must be empty: {destination}" in error
    assert ".hidden-file" in error
    run_start.assert_not_called()
    find_checkout.assert_called_once_with()


@pytest.mark.parametrize("subfolder", ["site", "Site", "site/example", "json"])
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


def test_subfolder_prompt_retries_standard_library_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    responses = iter(["yes", "site", "src"])
    assert prompt_for_site_subfolder("example", lambda _: next(responses)) == Path(
        "src"
    )
    assert "conflicts with Python's standard library" in capsys.readouterr().out


def test_nested_package_can_use_standard_library_name() -> None:
    assert normalize_subfolder("src/site") == Path("src/site")


@patch("wagtail_generate.cli.run_wagtail_start", return_value=1)
def test_start_returns_wagtail_exit_code(run_start: Mock, tmp_path: Path) -> None:
    assert (
        main(
            [
                "start",
                "example",
                "--site-name",
                "Example",
                "--directory",
                str(tmp_path),
                "--site-directory",
                ".",
            ]
        )
        == 1
    )
    assert run_start.call_args.kwargs["database"] == "sqlite3"


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


def test_site_code_defaults_to_project_root() -> None:
    subfolder = prompt_for_site_subfolder(
        "example",
        input_fn=lambda _: "",
    )

    assert subfolder is None


def test_subfolder_name_defaults_to_project_name() -> None:
    responses = iter(["yes", ""])

    subfolder = prompt_for_site_subfolder(
        "example",
        input_fn=lambda _: next(responses),
    )

    assert subfolder == Path("example")


def test_custom_subfolder_can_be_selected() -> None:
    responses = iter(["y", "sites/example"])

    subfolder = prompt_for_site_subfolder(
        "example",
        input_fn=lambda _: next(responses),
    )

    assert subfolder == Path("sites/example")


def test_human_readable_name_is_normalized() -> None:
    assert normalize_package_name("This is my site") == "this_is_my_site"


def test_display_site_name_removes_package_separators() -> None:
    assert display_site_name("this_is-my site") == "This Is My Site"


def test_site_name_is_prompted_separately() -> None:
    site_name = prompt_for_site_name(
        "Src",
        input_fn=lambda _: "Droitwich heritage centre",
    )

    assert site_name == "Droitwich Heritage Centre"


def test_site_name_prompt_accepts_default() -> None:
    assert prompt_for_site_name("Example Site", input_fn=lambda _: "") == (
        "Example Site"
    )


def test_subfolder_with_spaces_is_normalized(
    capsys: pytest.CaptureFixture[str],
) -> None:
    responses = iter(["y", "website source"])

    subfolder = prompt_for_site_subfolder(
        "this_is_my_site",
        input_fn=lambda _: next(responses),
    )

    assert subfolder == Path("website_source")
    assert "Using subfolder name: website_source" in capsys.readouterr().out


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
        site_name="Editorial Website",
        database="mysql",
        project_root=tmp_path,
        site_subfolder=None,
        template=None,
        layout=STANDARD_LAYOUT,
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


@patch("wagtail_generate.cli.run_wagtail_start")
@patch("wagtail_generate.cli.source_checkout_root", return_value=None)
def test_start_refuses_nonempty_project_root(
    find_checkout: Mock,
    run_start: Mock,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / ".hidden-file").write_text("existing")

    result = main(
        [
            "start",
            "example",
            "--site-name",
            "Example",
            "--database",
            "postgresql",
            "--directory",
            str(tmp_path),
            "--site-directory",
            ".",
        ]
    )

    assert result == 2
    error = capsys.readouterr().err
    assert "project root must be empty" in error
    assert ".hidden-file" in error
    find_checkout.assert_called_once_with()
    run_start.assert_not_called()
