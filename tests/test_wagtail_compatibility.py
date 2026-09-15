"""Opt-in smoke tests against the real Wagtail project generator."""

import os
import subprocess
from pathlib import Path

import pytest

from wagtail_generate.generation import run_wagtail_start

COMPATIBILITY_ENABLED = os.environ.get("WAGTAIL_GENERATE_TEST_COMPATIBILITY") == "1"


def _generated_python(project_root: Path) -> Path:
    """Return the Python executable in a generated project's environment."""
    executable = "python.exe" if os.name == "nt" else "python"
    directory = "Scripts" if os.name == "nt" else "bin"
    return project_root / ".venv" / directory / executable


@pytest.mark.parametrize(
    ("layout_name", "site_subfolder"),
    [("root", None), ("src", Path("src"))],
)
@pytest.mark.parametrize(
    "custom_user,custom_images",
    [(False, False), (True, False), (False, True), (True, True)],
)
@pytest.mark.skipif(
    not COMPATIBILITY_ENABLED,
    reason=(
        "set WAGTAIL_GENERATE_TEST_COMPATIBILITY=1 to run real Wagtail "
        "compatibility checks"
    ),
)
def test_real_wagtail_output_passes_django_checks_and_migrations(
    layout_name: str,
    custom_user: bool,
    custom_images: bool,
    site_subfolder: Path | None,
    tmp_path: Path,
) -> None:
    """Ensure current Wagtail output remains compatible with our transformations."""
    project_root = tmp_path / layout_name
    result = run_wagtail_start(
        "example",
        site_name="Example Website",
        project_root=project_root,
        site_subfolder=site_subfolder,
        custom_user=custom_user,
        custom_images=custom_images,
    )

    assert result == 0
    assert (project_root / "manage.py").is_file()
    assert _generated_python(project_root).is_file()

    source_root = (
        project_root if site_subfolder is None else project_root / site_subfolder
    )
    settings_path = (
        "example/settings/base.py" if site_subfolder is None else "settings/base.py"
    )
    settings_file = source_root / settings_path
    assert settings_file.is_file()
    assert 'WAGTAIL_SITE_NAME = "Example Website"' in settings_file.read_text()

    python_files = (
        path for path in project_root.rglob("*.py") if ".venv" not in path.parts
    )
    for python_file in python_files:
        compile(python_file.read_text(), str(python_file), "exec")

    generated_python = _generated_python(project_root)
    subprocess.run(
        [str(generated_python), "manage.py", "check"],
        cwd=project_root,
        check=True,
    )
    subprocess.run(
        [str(generated_python), "manage.py", "migrate", "--noinput"],
        cwd=project_root,
        check=True,
    )

    for arguments in (("makemigrations", "--check", "--dry-run"), ("test",)):
        subprocess.run(
            [str(generated_python), "manage.py", *arguments],
            cwd=project_root,
            check=True,
        )
    for app, enabled in (("accounts", custom_user), ("images", custom_images)):
        assert (
            source_root / app / "migrations" / "0001_initial.py"
        ).exists() == enabled


@pytest.mark.skipif(not COMPATIBILITY_ENABLED, reason="opt-in real Wagtail check")
@pytest.mark.parametrize("site_subfolder", [None, Path("src")])
def test_real_starter_homepage_response(tmp_path, site_subfolder):
    project_root = tmp_path / "homepage"
    assert (
        run_wagtail_start(
            "example",
            project_root=project_root,
            site_subfolder=site_subfolder,
            starter_homepage=True,
        )
        == 0
    )
    source = project_root / (site_subfolder or Path("."))
    assert not (source / "home/templates/home/welcome_page.html").exists()
    assert not (source / "home/static/css/welcome_page.css").exists()
    python = str(_generated_python(project_root))
    subprocess.run(
        [python, "manage.py", "migrate", "--noinput"],
        cwd=project_root,
        check=True,
    )
    subprocess.run(
        [
            python,
            "manage.py",
            "shell",
            "-c",
            """
from django.test import Client, override_settings
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.views import serve
from django.test import RequestFactory
with override_settings(ALLOWED_HOSTS=['testserver']):
    response = Client().get('/')
assert response.status_code == 200
html = response.content.decode()
assert 'A new beginning' in html
assert 'href="/admin/"' in html
assert 'An admin account is required.' in html
assert 'Welcome to your new Wagtail site' not in html
assert '/static/home/css/starter-homepage.css' in html
assert finders.find('home/css/starter-homepage.css')
response = serve(RequestFactory().get('/static/home/css/starter-homepage.css'),
                 'home/css/starter-homepage.css', insecure=True)
assert response.status_code == 200
assert b'clamp(' in b''.join(response.streaming_content)
""",
        ],
        cwd=project_root,
        check=True,
    )
