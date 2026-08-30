"""Create a UV environment and run Wagtail's project-generation command."""

import subprocess
from pathlib import Path


def run_wagtail_start(
    project_name: str,
    destination: Path | None = None,
    template: Path | None = None,
) -> int:
    """Initialize a UV project, install Wagtail, and generate into that project."""
    project_directory = destination or Path.cwd()

    commands = [
        ["uv", "init", "--bare", "--no-workspace"],
        ["uv", "add", "wagtail"],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=project_directory, check=False)
        if result.returncode != 0:
            return result.returncode

    command = ["uv", "run", "wagtail", "start", project_name, "."]
    if template is not None:
        command.append(f"--template={template}")

    return subprocess.run(
        command,
        cwd=project_directory,
        check=False,
    ).returncode
