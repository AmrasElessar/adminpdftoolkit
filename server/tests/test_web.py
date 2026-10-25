from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from adminpdf.app import create_app
from adminpdf.config import Settings

from .conftest import LOCAL


def test_spa_serving_and_headers(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>x</title>")
    (dist / "assets" / "app-abc.js").write_text("export {}")
    (dist / "manifest.webmanifest").write_text("{}")
    (dist / "sw.js").write_text("//")
    settings = Settings(data_dir=tmp_path / "data", web_dist=dist)
    with TestClient(create_app(settings), base_url="http://localhost", client=LOCAL) as c:
        r = c.get("/assets/app-abc.js")
        assert r.headers["content-type"].startswith("text/javascript")
        assert "immutable" in r.headers["cache-control"]
        assert c.get("/manifest.webmanifest").headers["content-type"].startswith("application/manifest+json")
        assert c.get("/sw.js").headers["cache-control"] == "no-cache"
        deep = c.get("/some/client/route")
        assert deep.status_code == 200 and "<title>x" in deep.text
        assert c.get("/api/nope").status_code == 404
        assert c.get("/../../etc/passwd").status_code in (200, 404)  # never escapes dist
        assert "root:" not in c.get("/..%2f..%2fetc%2fpasswd").text
