"""Tests for the disposable developer workflow."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from wagtail_generate import playground


@pytest.fixture
def destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(playground, "source_checkout_root", lambda: tmp_path)
    return tmp_path / ".playground"


def test_reset_removes_only_recognized_playground(destination: Path) -> None:
    destination.mkdir()
    (destination / playground.MARKER).touch()
    (destination / "db.sqlite3").touch()
    playground.reset_playground(destination)
    assert not destination.exists()


def test_reset_refuses_unrecognized_directory(destination: Path) -> None:
    destination.mkdir()
    valuable = destination / "keep.txt"
    valuable.write_text("keep")
    with pytest.raises(ValueError, match="unrecognized"):
        playground.reset_playground(destination)
    assert valuable.read_text() == "keep"


def test_reset_refuses_symlink(destination: Path, tmp_path: Path) -> None:
    target = tmp_path / "valuable"
    target.mkdir()
    (target / playground.MARKER).touch()
    destination.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        playground.reset_playground(destination)
    assert target.exists()


def test_reset_refuses_other_directory(destination: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside"):
        playground.reset_playground(tmp_path)


@pytest.mark.parametrize(
    ("arguments", "site_subfolder"),
    [
        ([], None),
        (["--site-directory", "."], None),
        (["--site-directory", "src"], Path("src")),
    ],
)
def test_workflow_runs_all_steps(
    destination: Path,
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
    site_subfolder: Path | None,
) -> None:
    def generate(**kwargs: object) -> int:
        assert kwargs["project_root"] == destination
        assert kwargs["site_subfolder"] == site_subfolder
        destination.mkdir()
        return 0

    monkeypatch.setattr(playground, "run_wagtail_start", generate)
    run = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr(playground.subprocess, "run", run)
    monkeypatch.setenv("VIRTUAL_ENV", "/generator/venv")
    assert playground.main(arguments) == 0
    commands = [
        call.args[0][len(playground.UV_COMMAND) :] for call in run.call_args_list
    ]
    assert commands == [
        ["sync", "--locked"],
        ["run", "python", "manage.py", "migrate", "--noinput"],
        [
            "run",
            "python",
            "manage.py",
            "createsuperuser",
            "--noinput",
            "--username",
            "admin",
            "--email",
            "admin@example.test",
        ],
        ["run", "python", "manage.py", "check"],
        ["run", "python", "manage.py", "runserver", "127.0.0.1:8000"],
    ]
    assert all(call.kwargs["cwd"] == destination for call in run.call_args_list)
    assert "VIRTUAL_ENV" not in run.call_args.kwargs["env"]
    assert (
        run.call_args_list[2].kwargs["env"]["DJANGO_SUPERUSER_PASSWORD"] == "playground"
    )
    assert "DJANGO_SUPERUSER_PASSWORD" not in run.call_args.kwargs["env"]
    assert (destination / playground.MARKER).is_file()
    assert playground.main(["--reset"]) == 0
    assert not destination.exists()


def test_generation_failure_does_not_start_server(
    destination: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(playground, "run_wagtail_start", Mock(return_value=1))
    run = Mock()
    monkeypatch.setattr(playground.subprocess, "run", run)
    assert playground.main([]) == 1
    run.assert_not_called()


@pytest.mark.parametrize("failure_step", [2, 3])
def test_setup_failure_stops_before_server(
    destination: Path, monkeypatch: pytest.MonkeyPatch, failure_step: int
) -> None:
    def generate(**kwargs: object) -> int:
        destination.mkdir()
        return 0

    monkeypatch.setattr(playground, "run_wagtail_start", generate)
    run = Mock(side_effect=[Mock(returncode=0)] * failure_step + [Mock(returncode=1)])
    monkeypatch.setattr(playground.subprocess, "run", run)
    assert playground.main([]) == 1
    assert run.call_count == failure_step + 1


@pytest.mark.parametrize("value", ["../src", "/tmp/src", "invalid"])
def test_invalid_site_directory_does_not_reset(
    destination: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    reset = Mock()
    monkeypatch.setattr(playground, "reset_playground", reset)
    with pytest.raises(SystemExit) as error:
        playground.main(["--site-directory", value])
    assert error.value.code == 2
    reset.assert_not_called()
