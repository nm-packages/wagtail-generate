"""Tests for generation safety checks."""

from pathlib import Path

from wagtail_generate.safety import (
    destination_is_in_source_checkout,
    source_checkout_root,
)


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
