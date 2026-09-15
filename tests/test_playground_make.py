"""Exercise Make recipes without generating or replacing a real playground."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from wagtail_generate import playground


@pytest.fixture
def make_environment(tmp_path: Path) -> dict[str, str]:
    stub = tmp_path / "uv"
    stub.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "print(json.dumps({'argv': sys.argv[1:], "
        "'extra': os.environ.get('PLAYGROUND_ARGS', ''), "
        "'distribution': os.environ.get('WAGTAIL_GENERATE_TEST_DISTRIBUTION', ''), "
        "'compatibility': os.environ.get("
        "'WAGTAIL_GENERATE_TEST_COMPATIBILITY', '')}))\n"
    )
    stub.chmod(0o755)
    environment = os.environ.copy()
    for name in (
        "SITE_DIRECTORY",
        "PROJECT_NAME",
        "SITE_NAME",
        "DATABASE",
        "TEMPLATE",
        "PLAYGROUND_ARGS",
        "PLAYGROUND_PRESET",
        "MAKEFLAGS",
        "MFLAGS",
    ):
        environment.pop(name, None)
    environment["PATH"] = f"{tmp_path}{os.pathsep}{environment['PATH']}"
    return environment


def run_make(
    arguments: list[str], environment: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", "--no-print-directory", *arguments],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_make_playground_enables_all_features_with_sqlite(
    make_environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Old configuration variables must not override the single supported preset.
    make_environment.update(
        DATABASE="postgresql",
        SITE_DIRECTORY=".",
        PLAYGROUND_ARGS="--database mysql --no-custom-user",
    )
    result = run_make(["playground"], make_environment)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.splitlines()[-1])
    assert payload["argv"][:4] == ["run", "python", "-m", "wagtail_generate.playground"]
    monkeypatch.setattr(sys, "argv", ["playground", *payload["argv"][4:]])
    monkeypatch.setenv("PLAYGROUND_ARGS", payload["extra"])
    options = playground.parse_arguments()
    assert options == playground.PlaygroundOptions(
        reset=False,
        site_subfolder=Path("src"),
        database="sqlite3",
        starter_homepage=True,
        custom_user=True,
        custom_images=True,
    )


def test_make_reset_only_resets(make_environment: dict[str, str]) -> None:
    result = run_make(["playground-reset"], make_environment)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.splitlines()[-1])
    assert payload["argv"] == [
        "run",
        "python",
        "-m",
        "wagtail_generate.playground",
        "--reset",
    ]


@pytest.mark.parametrize(
    ("target", "expected_argv"),
    [
        ("sync", ["sync"]),
        ("lint", ["run", "ruff", "check", "."]),
        ("typecheck", ["run", "mypy"]),
        ("test", ["run", "pytest"]),
        ("pre-commit", ["run", "pre-commit", "run", "--all-files"]),
        (
            "coverage",
            [
                "run",
                "pytest",
                "--cov=wagtail_generate",
                "--cov-report=term-missing",
            ],
        ),
        (
            "test-distribution",
            ["run", "pytest", "tests/test_distribution.py"],
        ),
        (
            "test-compatibility",
            ["run", "pytest", "tests/test_wagtail_compatibility.py"],
        ),
    ],
)
def test_make_developer_target(
    make_environment: dict[str, str],
    target: str,
    expected_argv: list[str],
) -> None:
    result = run_make([target], make_environment)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.splitlines()[-1])
    assert payload["argv"] == expected_argv

    if target == "test-distribution":
        assert payload["distribution"] == "1"
        assert payload["compatibility"] == ""
    elif target == "test-compatibility":
        assert payload["distribution"] == ""
        assert payload["compatibility"] == "1"


def test_make_check_runs_routine_checks(
    make_environment: dict[str, str],
) -> None:
    result = run_make(["check"], make_environment)
    assert result.returncode == 0, result.stderr
    payloads = [
        json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")
    ]
    assert [payload["argv"] for payload in payloads] == [
        ["run", "ruff", "check", "."],
        ["run", "mypy"],
        ["run", "pytest"],
    ]
