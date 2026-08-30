"""Tests for the command-line interface."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from wagtail_generate import __version__
from wagtail_generate.cli import main, prompt_for_destination


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

    assert main(["start", "example", "--directory", str(output)]) == 0

    run_start.assert_called_once_with(
        project_name="example",
        destination=output,
        template=None,
    )
    assert output.is_dir()


@patch("wagtail_generate.cli.run_wagtail_start", return_value=1)
def test_start_returns_wagtail_exit_code(run_start: Mock, tmp_path: Path) -> None:
    assert main(["start", "example", "--directory", str(tmp_path)]) == 1


def test_destination_defaults_to_current_directory() -> None:
    destination = prompt_for_destination(
        "example",
        base_directory=Path("workspace"),
        input_fn=lambda _: "",
    )

    assert destination == Path("workspace")


def test_subfolder_name_defaults_to_project_name() -> None:
    responses = iter(["yes", ""])

    destination = prompt_for_destination(
        "example",
        base_directory=Path("workspace"),
        input_fn=lambda _: next(responses),
    )

    assert destination == Path("workspace/example")


def test_custom_subfolder_can_be_selected() -> None:
    responses = iter(["y", "sites/example"])

    destination = prompt_for_destination(
        "example",
        base_directory=Path("workspace"),
        input_fn=lambda _: next(responses),
    )

    assert destination == Path("workspace/sites/example")


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

    result = main(["start", "example", "--directory", str(destination)])

    assert result == 2
    assert "refusing to generate" in capsys.readouterr().err
    assert not destination.exists()
    run_start.assert_not_called()
