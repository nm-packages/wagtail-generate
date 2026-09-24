"""Run via a generated site's manage.py shell to probe collected static assets."""

import os
import re
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import urlopen

from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.management import call_command
from django.test import Client, override_settings

root = Path.cwd() / "collected"
with override_settings(
    DEBUG=False,
    ALLOWED_HOSTS=["testserver"],
    STATIC_URL="/static/",
    STATIC_ROOT=root / "static",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
        },
    },
):
    call_command("collectstatic", interactive=False, verbosity=0, clear=True)
    response = Client().get("/")
    assert response.status_code == 200
    html = response.content.decode()
    assert "A new beginning" in html  # The starter homepage still renders.
    assert "home/css/starter-homepage." in html
    css_url = staticfiles_storage.url(os.environ["FRONTEND_CSS"])
    js_url = staticfiles_storage.url(os.environ["FRONTEND_JS"])
    assert css_url in html and js_url in html
    assert css_url != "/static/" + os.environ["FRONTEND_CSS"]
    handler = partial(SimpleHTTPRequestHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(origin + css_url, timeout=10) as asset:
            css = asset.read().decode()
        with urlopen(origin + js_url, timeout=10) as asset:
            assert b"frontendRecipe" in asset.read()
        image_url = re.search(r"url\(['\"]?([^)'\"]+)", css).group(1)
        assert "logo." in image_url and "logo.svg" not in image_url
        with urlopen(urljoin(origin + css_url, image_url), timeout=10) as asset:
            assert b"<svg" in asset.read()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=10)
