"""Opt-in execution of the documented recipe in real generated sites."""

import json
import os
import signal
import socket
import subprocess
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

from wagtail_generate.generation import run_wagtail_start

pytestmark = pytest.mark.skipif(
    os.environ.get("WAGTAIL_GENERATE_TEST_FRONTEND") != "1",
    reason="set WAGTAIL_GENERATE_TEST_FRONTEND=1; requires Node/npm and network",
)


def run(root, *args, **kwargs):
    return subprocess.run(args, cwd=root, check=True, timeout=180, **kwargs)


def wait_for(check, process, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        assert process.poll() is None, "development command exited unexpectedly"
        if check():
            return
        time.sleep(0.2)
    pytest.fail("timed out waiting for development output")


def group_exists(pid):
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return False
    return True


def assert_group_stopped(pid):
    deadline = time.monotonic() + 10
    while group_exists(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not group_exists(pid), "development command left child processes running"


@contextmanager
def development(root, command=None, env=None):
    with (root / "frontend-test.log").open("w+") as log:
        process = subprocess.Popen(
            command or ["npm", "run", "dev"],
            cwd=root,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            yield process
        finally:
            if group_exists(process.pid):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
            log.seek(0)
            print(log.read())


def verify_compose(root, recipe, package, port):
    """Exercise the documented service and launcher, including both failure exits."""
    override = root / "compose.frontend.json"
    fragment = json.loads(recipe.split("```json\n")[2].split("```", 1)[0])
    override.write_text(json.dumps(fragment))
    launcher = root / "frontend-compose.sh"
    launcher.write_text(recipe.split("```sh\n", 1)[1].split("```", 1)[0])
    ignore = root / ".dockerignore"
    ignore.write_text(ignore.read_text() + "\nnode_modules\ncollected\n")
    (root / "package.json").write_text(json.dumps(package))
    env = os.environ | {
        "COMPOSE_FILE": "compose.yaml" + os.pathsep + override.name,
        "COMPOSE_PROJECT_NAME": "frontend-check-" + uuid.uuid4().hex[:10],
        "WEB_PORT": str(port),
    }
    try:
        # Pull/build before timing the interactive lifecycle checks.
        run(root, "docker", "compose", "pull", "frontend", env=env)
        run(root, "docker", "compose", "build", "web", env=env)
        with development(root, ["sh", launcher.name], env) as process:
            wait_for(lambda: port_open(port), process, timeout=120)
            os.killpg(process.pid, signal.SIGINT)
            process.wait(timeout=45)
            running = run(
                root,
                "docker",
                "compose",
                "ps",
                "--status",
                "running",
                "--quiet",
                env=env,
                capture_output=True,
                text=True,
            )
            assert not running.stdout.strip()

        for failing_service in ("frontend", "web"):
            services = json.loads(json.dumps(fragment))
            services["services"].setdefault(failing_service, {})["command"] = [
                "sh",
                "-c",
                "sleep 3; exit 7",
            ]
            override.write_text(json.dumps(services))
            with development(root, ["sh", launcher.name], env) as process:
                assert process.wait(timeout=120) != 0
                running = run(
                    root,
                    "docker",
                    "compose",
                    "ps",
                    "--status",
                    "running",
                    "--quiet",
                    env=env,
                    capture_output=True,
                    text=True,
                )
                assert not running.stdout.strip()
    finally:
        # Only this test's unique disposable project and volumes are removed.
        run(root, "docker", "compose", "down", "--volumes", env=env)


def port_open(port):
    with socket.socket() as connection:
        connection.settimeout(0.2)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def verify_collected_assets(root, stylesheet, javascript):
    fixture = Path(__file__).parent / "fixtures/frontend_verify.py"
    run(
        root,
        "uv",
        "run",
        "python",
        "manage.py",
        "shell",
        "-c",
        fixture.read_text(),
        env=os.environ | {"FRONTEND_CSS": stylesheet, "FRONTEND_JS": javascript},
    )


@pytest.mark.parametrize("subfolder", [None, Path("src")])
def test_frontend_recipe_builds_and_serves_assets(tmp_path, subfolder):
    root = tmp_path / "site"
    assert (
        run_wagtail_start(
            "example",
            project_root=root,
            site_subfolder=subfolder,
            starter_homepage=True,
        )
        == 0
    )
    source = root / (subfolder or Path("."))
    static = source / "home/static/home"
    templates = source / ("example/templates" if subfolder is None else "templates")
    base = templates / "base.html"
    original_base = base.read_text()
    run(root, "uv", "run", "python", "manage.py", "migrate", "--noinput")

    # Follow plain mode first, including a relative image URL, without npm.
    for directory in ("css", "js", "images"):
        (static / directory).mkdir(parents=True, exist_ok=True)
    (static / "images/logo.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'
    )
    (static / "css/site.css").write_text(
        '.recipe { background: url("../images/logo.svg"); }'
    )
    (static / "js/site.js").write_text("window.frontendRecipe = 'initial';")

    def wire_assets(css, js):
        base.write_text(
            original_base.replace(
                "</head>",
                '<link rel="stylesheet" href="{% static \'' + css + "' %}\">\n"
                "<script defer src=\"{% static '" + js + "' %}\"></script>\n</head>",
            )
        )

    wire_assets("home/css/site.css", "home/js/site.js")
    verify_collected_assets(root, "home/css/site.css", "home/js/site.js")
    assert not (root / "package.json").exists()

    # Execute scripts from the shipped recipe, so documentation regressions fail.
    skill = root / ".agents/skills/wagtail-frontend-setup"
    recipe = (skill / "references/sass-esbuild.md").read_text()
    package = json.loads(recipe.split("```json\n", 1)[1].split("```", 1)[0])
    package_file = root / "package.json"
    package_file.write_text(json.dumps(package))
    for directory in ("scss", "js"):
        (root / "frontend" / directory).mkdir(parents=True)
    partial = root / "frontend/scss/_colours.scss"
    partial.write_text("$accent: #13579b;")
    (root / "frontend/scss/site.scss").write_text(
        '@use "colours"; .recipe { color: colours.$accent; '
        'background: url("../../images/logo.svg"); }'
    )
    javascript = root / "frontend/js/site.js"
    javascript.write_text("window.frontendRecipe = 'initial';")
    run(
        root,
        "npm",
        "install",
        "--save-dev",
        "--save-exact",
        "sass",
        "esbuild",
        "concurrently",
    )
    lock = (root / "package-lock.json").read_bytes()
    run(root, "npm", "ci", "--include=dev")
    assert (root / "package-lock.json").read_bytes() == lock
    run(root, "npm", "run", "build")
    run(root, "npm", "ls", "--depth=0")
    wire_assets("home/build/css/site.css", "home/build/js/site.js")
    verify_collected_assets(root, "home/build/css/site.css", "home/build/js/site.js")

    valid_sass = (root / "frontend/scss/site.scss").read_text()
    (root / "frontend/scss/site.scss").write_text(".broken { color: ;")
    failed = subprocess.run(["npm", "run", "build"], cwd=root, timeout=30)
    assert failed.returncode != 0
    (root / "frontend/scss/site.scss").write_text(valid_sass)

    if os.name == "nt":
        pytest.skip("build verified; process-group lifecycle checks require POSIX")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    package = json.loads(package_file.read_text())
    package["scripts"]["dev:django"] += f" 127.0.0.1:{port}"
    package_file.write_text(json.dumps(package))
    with development(root) as process:
        wait_for(lambda: port_open(port), process)
        # Allow both watchers to start before editing their inputs.
        wait_for(
            lambda: "watching for changes" in (root / "frontend-test.log").read_text(),
            process,
        )
        partial.write_text("$accent: #2468ac;")
        javascript.write_text("window.frontendRecipe = 'updated';")
        wait_for(
            lambda: "#2468ac" in (static / "build/css/site.css").read_text(), process
        )
        wait_for(
            lambda: "updated" in (static / "build/js/site.js").read_text(), process
        )
        os.killpg(process.pid, signal.SIGINT)
        process.wait(timeout=15)
        assert_group_stopped(process.pid)
        assert not port_open(port)

    for failing_child in ("watch:js", "dev:django"):
        failing_package = json.loads(json.dumps(package))
        failing_package["scripts"][failing_child] = (
            'node -e "setTimeout(() => process.exit(7), 2500)"'
        )
        package_file.write_text(json.dumps(failing_package))
        with development(root) as process:
            assert process.wait(timeout=30) != 0
            assert_group_stopped(process.pid)
            assert not port_open(port)

    if os.environ.get("WAGTAIL_GENERATE_TEST_FRONTEND_DOCKER") == "1":
        verify_compose(root, recipe, package, port)
