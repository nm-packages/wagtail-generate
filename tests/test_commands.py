"""Exercise the process boundary independently of project generation."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from wagtail_generate.commands import GenerationError, run_command


@pytest.mark.parametrize("capture_output", [False, True])
def test_output_mode_and_literal_arguments(
    capture_output: bool, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    literal = "a path with spaces; $(not-a-command)"
    result = run_command(
        [sys.executable, "-c", "import sys; print(sys.argv[1])", literal],
        stage="test",
        description="Echo literal argument",
        cwd=tmp_path,
        capture_output=capture_output,
    )
    assert result.returncode == 0
    terminal = capfd.readouterr()
    if capture_output:
        assert result.stdout == literal + "\n"
        assert terminal.out == ""
    else:
        assert result.stdout is None
        assert terminal.out == literal + "\n"


@pytest.mark.parametrize("capture_output", [False, True])
def test_failed_command_reports_context_and_preserves_exit_code(
    capture_output: bool, capfd: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(GenerationError) as raised:
        run_command(
            [
                sys.executable,
                "-c",
                "import sys; sys.stderr.write('detail'); sys.exit(7)",
            ],
            stage="setup",
            description="Install dependencies",
            capture_output=capture_output,
        )
    error = raised.value
    assert error.stage == "setup"
    assert error.returncode == 7
    assert "Install dependencies" in str(error)
    assert sys.executable in str(error)
    assert "exited with code 7" in str(error)
    terminal = capfd.readouterr()
    if capture_output:
        assert str(error).endswith("\ndetail")
        assert terminal.err == ""
    else:
        assert terminal.err == "detail"


@pytest.mark.parametrize("capture_output", [False, True])
@patch("wagtail_generate.commands.subprocess.run")
def test_launch_error_has_context_and_cause(run: Mock, capture_output: bool) -> None:
    cause = FileNotFoundError("uvx unavailable")
    run.side_effect = cause
    with pytest.raises(GenerationError, match="resolution: Discover Python") as raised:
        run_command(
            ["uvx", "uv", "python", "list"],
            stage="resolution",
            description="Discover Python",
            capture_output=capture_output,
        )
    assert raised.value.__cause__ is cause
    assert raised.value.returncode is None


@patch("wagtail_generate.commands.subprocess.run")
def test_captured_failure_without_stderr_remains_actionable(run: Mock) -> None:
    run.return_value = subprocess.CompletedProcess([], 9, stdout="", stderr="")
    with pytest.raises(GenerationError, match="exited with code 9"):
        run_command(
            ["uvx", "uv", "pip", "compile"],
            stage="resolution",
            description="Resolve dependencies",
            capture_output=True,
        )
