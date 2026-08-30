"""Check Django template formatting without changing source files."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _django_templates(project_root: Path) -> list[Path]:
    return sorted(
        path
        for path in project_root.rglob("*.html")
        if "templates" in path.parts and ".venv" not in path.parts
    )


def main() -> int:
    """Return a nonzero status when djangofmt would change a template."""
    project_root = Path.cwd()
    templates = _django_templates(project_root)
    if not templates:
        return 0

    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_root = Path(temporary_directory)
        copies: list[tuple[Path, Path]] = []
        for index, source in enumerate(templates):
            destination = temporary_root / str(index) / source.name
            destination.parent.mkdir(parents=True)
            shutil.copyfile(source, destination)
            copies.append((source, destination))

        result = subprocess.run(
            ["djangofmt", temporary_root],
            check=False,
        )
        if result.returncode != 0:
            return result.returncode

        changed = [
            source
            for source, formatted_copy in copies
            if source.read_bytes() != formatted_copy.read_bytes()
        ]

    if changed:
        print("Django templates require formatting:", file=sys.stderr)
        for template in changed:
            print(f"  {template.relative_to(project_root)}", file=sys.stderr)
        print("Run `uv run djangofmt .` to format them.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
