"""Opt-in checks of actual release archives, including a wheel built from sdist."""

import os
import subprocess
import tarfile
import tomllib
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile

import pytest


@pytest.mark.skipif(
    os.environ.get("WAGTAIL_GENERATE_TEST_DISTRIBUTION") != "1",
    reason="set WAGTAIL_GENERATE_TEST_DISTRIBUTION=1 to build release artifacts",
)
def test_release_artifacts_include_license(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    expected_license = (root / "LICENSE").read_bytes()
    assert b"Copyright (c) 2026 Nick Moreton" in expected_license
    assert project["license"] == "MIT"

    subprocess.run(
        ["uv", "build", "--sdist", "--out-dir", str(tmp_path), str(root)],
        check=True,
        cwd=tmp_path,
    )
    (sdist,) = tmp_path.glob("*.tar.gz")
    with tarfile.open(sdist) as archive:
        (license_path,) = (
            name for name in archive.getnames() if name.endswith("/LICENSE")
        )
        license_file = archive.extractfile(license_path)
        assert license_file is not None
        assert license_file.read() == expected_license
        package_root = license_path.rsplit("/", 1)[0]
        metadata_file = archive.extractfile(f"{package_root}/PKG-INFO")
        assert metadata_file is not None
        sdist_metadata = BytesParser().parsebytes(metadata_file.read())

    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path), str(sdist)],
        check=True,
        cwd=tmp_path,
    )
    (wheel,) = tmp_path.glob("*.whl")
    with ZipFile(wheel) as archive:
        (metadata_path,) = (
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        )
        metadata_directory = metadata_path.rsplit("/", 1)[0]
        assert (
            archive.read(f"{metadata_directory}/licenses/LICENSE") == expected_license
        )
        wheel_metadata = BytesParser().parsebytes(archive.read(metadata_path))

    venv = tmp_path / "install"
    subprocess.run(["uv", "venv", "--python", "3.14", str(venv)], check=True)
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    executable = venv / (
        "Scripts/wagtail-generate.exe" if os.name == "nt" else "bin/wagtail-generate"
    )
    subprocess.run(
        ["uv", "pip", "install", "--python", str(python), str(wheel)],
        check=True,
    )
    isolated_env = os.environ | {"PYTHONPATH": ""}
    help_result = subprocess.run(
        [str(executable), "--help"],
        cwd=tmp_path,
        env=isolated_env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Generate an opinionated Wagtail CMS project" in help_result.stdout
    module_result = subprocess.run(
        [str(python), "-m", "wagtail_generate", "--version"],
        cwd=tmp_path,
        env=isolated_env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert module_result.stdout.strip() == "wagtail-generate 0.1.0"
    probe = subprocess.run(
        [
            str(python),
            "-c",
            "from wagtail_generate.rendering import template_text; "
            "from wagtail_generate.wagtail import ("
            "ProjectOptions, build_generation_plan); "
            "from pathlib import Path; "
            "assert 'Wagtail CMS project' in template_text('README.md.jinja'); "
            "print('ok')",
        ],
        cwd=tmp_path,
        env=isolated_env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert probe.stdout.strip() == "ok"

    for database in ("sqlite3", "postgresql", "mysql"):
        for source_layout in (None, Path("src")):
            check = subprocess.run(
                [
                    str(python),
                    "-c",
                    "from pathlib import Path; "
                    "from wagtail_generate.wagtail import ("
                    "ProjectOptions, build_generation_plan); "
                    "import sys; "
                    "options = ProjectOptions('example', 'Example', sys.argv[1], "
                    "Path('/tmp/generated'), None if sys.argv[2] == 'root' "
                    "else Path('src'), None); "
                    "plan = build_generation_plan(options, '3.14'); "
                    "assert plan.options.database == sys.argv[1]; print('ok')",
                    database,
                    "root" if source_layout is None else "src",
                ],
                cwd=tmp_path,
                env=isolated_env,
                check=True,
                capture_output=True,
                text=True,
            )
            assert check.stdout.strip() == "ok"

    for metadata in (sdist_metadata, wheel_metadata):
        assert metadata["License-Expression"] == project["license"]
        assert metadata.get_all("License-File") == ["LICENSE"]
