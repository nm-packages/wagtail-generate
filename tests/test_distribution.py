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

    for metadata in (sdist_metadata, wheel_metadata):
        assert metadata["License-Expression"] == project["license"]
        assert metadata.get_all("License-File") == ["LICENSE"]
