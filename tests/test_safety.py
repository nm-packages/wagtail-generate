"""Tests for generation safety checks."""

from pathlib import Path

import pytest

import wagtail_generate.safety as safety
from wagtail_generate.safety import (
    destination_is_in_source_checkout,
    source_checkout_root,
    validate_source_package,
)


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("json", "conflicts with Python's standard library"),
        ("django", "conflicts with a generated-project dependency"),
    ],
)
def test_source_package_conflicts_are_rejected(name: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_source_package(name)


def test_source_checkout_root_returns_none_without_project_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_file = tmp_path / "lib" / "wagtail_generate" / "safety.py"
    module_file.parent.mkdir(parents=True)
    monkeypatch.setattr(safety, "__file__", str(module_file))

    assert source_checkout_root() is None


def test_source_checkout_root_returns_none_for_another_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_file = tmp_path / "lib" / "wagtail_generate" / "safety.py"
    module_file.parent.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "another-project"\n')
    monkeypatch.setattr(safety, "__file__", str(module_file))

    assert source_checkout_root() is None


def test_source_checkout_is_detected() -> None:
    checkout = source_checkout_root()

    assert checkout is not None
    assert checkout.name == "wagtail-generate"


def test_checkout_root_is_an_unsafe_destination(tmp_path: Path) -> None:
    checkout = tmp_path / "tool"

    assert destination_is_in_source_checkout(checkout, checkout)


def test_checkout_child_is_an_unsafe_destination(tmp_path: Path) -> None:
    checkout = tmp_path / "tool"

    assert destination_is_in_source_checkout(checkout / "src", checkout)


def test_unrelated_directory_is_safe(tmp_path: Path) -> None:
    checkout = tmp_path / "tool"

    assert not destination_is_in_source_checkout(tmp_path / "site", checkout)
