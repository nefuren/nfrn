from fastapi.testclient import TestClient

from app.main import create_app
from conftest import FakeMonitor


def test_security_headers_on_every_response(client):
    for path in ("/api/session", "/api/snapshot", "/does-not-exist"):
        r = client.get(path)
        csp = r.headers["content-security-policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "object-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["referrer-policy"] == "no-referrer"
        assert r.headers["x-frame-options"] == "DENY"


def test_host_header_rejected(settings):
    # DNS rebinding 対策: 許可していない Host は拒否
    app = create_app(settings, monitor=FakeMonitor())
    with TestClient(app, base_url="http://evil.example:8787") as c:
        assert c.get("/api/session").status_code == 400


def test_api_docs_disabled(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_static_frontend_served_with_headers(settings, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>x</title>", encoding="utf-8")
    s = settings.model_copy(update={"frontend_dist": dist})
    app = create_app(s, monitor=FakeMonitor())
    with TestClient(app, base_url="http://127.0.0.1:8787") as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "content-security-policy" in r.headers
