"""Exercise published console scripts with a real, offline UV environment."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

from wagtail_generate.wagtail import (
    UV_COMMAND,
    ProjectOptions,
    _publish_generated_project,
    build_generation_plan,
)


@pytest.mark.parametrize("existing_destination", [False, True])
def test_console_script_runs_after_publication(
    tmp_path: Path, existing_destination: bool
) -> None:
    uv = shutil.which("uv")
    assert uv is not None, "UV is a prerequisite for this project"
    staging = tmp_path / "staging"
    staging.mkdir()
    destination = tmp_path / "published"
    if existing_destination:
        destination.mkdir()
    plan = build_generation_plan(
        ProjectOptions("example", "Example", "sqlite3", destination, None, None),
        f"{sys.version_info.major}.{sys.version_info.minor}",
    )
    environment_command = list(
        next(
            command.arguments[len(UV_COMMAND) :]
            for command in plan.setup_commands
            if command.arguments[len(UV_COMMAND)] == "venv"
        )
    )
    environment_command[environment_command.index("--python") + 1] = sys.executable
    subprocess.run(
        [uv, *environment_command, "--offline"],
        cwd=staging,
        check=True,
        capture_output=True,
    )

    # Build a dependency-free wheel locally so no package index is needed.
    wheel = tmp_path / "publication_probe-1.0-py3-none-any.whl"
    metadata = "publication_probe-1.0.dist-info"
    with ZipFile(wheel, "w") as archive:
        archive.writestr(
            "publication_probe.py", 'def main():\n    print("published")\n'
        )
        archive.writestr(
            f"{metadata}/METADATA",
            "Metadata-Version: 2.1\nName: publication-probe\nVersion: 1.0\n",
        )
        archive.writestr(
            f"{metadata}/WHEEL",
            "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        archive.writestr(
            f"{metadata}/entry_points.txt",
            "[console_scripts]\npublication-probe = publication_probe:main\n",
        )
        archive.writestr(f"{metadata}/RECORD", "")

    scripts = Path("Scripts" if os.name == "nt" else "bin")
    python = "python.exe" if os.name == "nt" else "python"
    subprocess.run(
        [
            uv,
            "pip",
            "install",
            "--offline",
            "--python",
            str(staging / ".venv" / scripts / python),
            str(wheel),
        ],
        check=True,
        capture_output=True,
    )
    assert _publish_generated_project(staging, destination)
    # Match TemporaryDirectory cleanup for publication into an existing directory.
    if staging.exists():
        staging.rmdir()
    executable = "publication-probe.exe" if os.name == "nt" else "publication-probe"
    result = subprocess.run(
        [str(destination / ".venv" / scripts / executable)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "published"
