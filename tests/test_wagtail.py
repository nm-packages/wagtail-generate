"""Tests for the Wagtail command integration."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

from wagtail_generate.wagtail import run_wagtail_start


@patch("wagtail_generate.wagtail.subprocess.run")
def test_run_wagtail_start_streams_native_command(run: Mock) -> None:
    run.return_value = subprocess.CompletedProcess([], returncode=0)

    result = run_wagtail_start(
        "example",
        destination=Path("generated"),
        template=Path("custom-template"),
    )

    assert result == 0
    assert run.call_args_list == [
        (
            (["uv", "init", "--bare", "--no-workspace"],),
            {"cwd": Path("generated"), "check": False},
        ),
        ((["uv", "add", "wagtail"],), {"cwd": Path("generated"), "check": False}),
        (
            (
                [
                    "uv",
                    "run",
                    "wagtail",
                    "start",
                    "example",
                    ".",
                    "--template=custom-template",
                ],
            ),
            {"cwd": Path("generated"), "check": False},
        ),
    ]


@patch("wagtail_generate.wagtail.subprocess.run")
def test_run_wagtail_start_stops_after_failed_uv_command(run: Mock) -> None:
    run.return_value = subprocess.CompletedProcess([], returncode=2)

    assert run_wagtail_start("example", destination=Path("generated")) == 2
    run.assert_called_once_with(
        ["uv", "init", "--bare", "--no-workspace"],
        cwd=Path("generated"),
        check=False,
    )
