"""Execute external commands with consistent operational errors."""

import shlex
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, overload


class GenerationError(RuntimeError):
    """A command could not start or exited unsuccessfully."""

    def __init__(self, stage: str, message: str, returncode: int | None = None) -> None:
        super().__init__(f"{stage}: {message}")
        self.stage = stage
        self.returncode = returncode


@overload
def run_command(
    arguments: Sequence[str],
    *,
    stage: str,
    description: str,
    cwd: Path | None = None,
    capture_output: Literal[False] = False,
) -> subprocess.CompletedProcess[bytes]: ...


@overload
def run_command(
    arguments: Sequence[str],
    *,
    stage: str,
    description: str,
    cwd: Path | None = None,
    capture_output: Literal[True],
) -> subprocess.CompletedProcess[str]: ...


def run_command(
    arguments: Sequence[str],
    *,
    stage: str,
    description: str,
    cwd: Path | None = None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[bytes] | subprocess.CompletedProcess[str]:
    """Stream native output by default; capture text only for response parsing.

    Commands use argument lists, never a shell. Failures include command context;
    captured stderr is included because it was not displayed by the child.
    """
    command = list(arguments)
    context = f"{description} ({shlex.join(command)})"
    result: subprocess.CompletedProcess[bytes] | subprocess.CompletedProcess[str]
    captured_stderr = ""
    try:
        if capture_output:
            result = subprocess.run(
                command, cwd=cwd, check=False, capture_output=True, text=True
            )
            captured_stderr = result.stderr
        else:
            result = subprocess.run(command, cwd=cwd, check=False)
    except OSError as error:
        raise GenerationError(stage, f"{context}: {error}") from error
    if result.returncode != 0:
        message = f"{context}: exited with code {result.returncode}"
        if captured_stderr:
            message += f"\n{captured_stderr.strip()}"
        raise GenerationError(stage, message, result.returncode)
    return result
