"""Tests for utility scripts copied into generated projects."""

import os
import subprocess
import sys
from pathlib import Path

from wagtail_generate.rendering import write_template


def test_django_template_check_detects_changes_without_modifying_source(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    template = project_root / "site" / "templates" / "example.html"
    template.parent.mkdir(parents=True)
    template.write_text("<p >Example</p>\n")

    checker = project_root / "scripts" / "check_django_templates.py"
    write_template(checker, "static/check_django_templates.py")

    executable_directory = tmp_path / "bin"
    executable_directory.mkdir()
    formatter = executable_directory / "djangofmt"
    formatter.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "from pathlib import Path\n"
        "for path in Path(sys.argv[1]).rglob('*.html'):\n"
        "    path.write_text(path.read_text().replace('<p >', '<p>'))\n"
    )
    formatter.chmod(0o755)
    environment = os.environ | {
        "PATH": f"{executable_directory}{os.pathsep}{os.environ['PATH']}"
    }

    result = subprocess.run(
        [sys.executable, checker],
        cwd=project_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "site/templates/example.html" in result.stderr
    assert template.read_text() == "<p >Example</p>\n"

    template.write_text("<p>Example</p>\n")
    result = subprocess.run(
        [sys.executable, checker],
        cwd=project_root,
        env=environment,
        check=False,
    )

    assert result.returncode == 0
