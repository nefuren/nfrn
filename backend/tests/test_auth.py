from conftest import ORIGIN, TOKEN, login

from app.auth import RateLimiter, SessionStore


def test_login_success_sets_strict_httponly_cookie(client):
    r = login(client)
    assert r.status_code == 204
    cookie = r.headers["set-cookie"].lower()
    assert "desk_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/" in cookie
    assert TOKEN.lower() not in cookie  # トークン自体は Cookie に入れない


def test_login_wrong_token(client):
    assert login(client, "wrong" * 10).status_code == 401
    assert client.get("/api/session").json() == {"authenticated": False}


def test_login_rate_limited(client):
    for _ in range(5):
        assert login(client, "bad").status_code == 401
    assert login(client, "bad").status_code == 429
    assert login(client).status_code == 429  # 制限中は正しいトークンでも拒否


def test_login_rejects_foreign_origin(client):
    r = client.post("/api/login", json={"token": TOKEN}, headers={"origin": "http://evil.example"})
    assert r.status_code == 403


def test_login_rejects_huge_token(client):
    assert login(client, "a" * 5000).status_code == 422


def test_snapshot_requires_session(client):
    assert client.get("/api/snapshot").status_code == 401
    login(client)
    r = client.get("/api/snapshot")
    assert r.status_code == 200
    assert r.json()["tick"]["type"] == "tick"
    assert r.headers["cache-control"] == "no-store"


def test_logout_revokes(client):
    login(client)
    assert client.get("/api/session").json() == {"authenticated": True}
    assert client.post("/api/logout", headers={"origin": ORIGIN}).status_code == 204
    assert client.get("/api/snapshot").status_code == 401


def test_session_store_expiry():
    now = [1000.0]
    store = SessionStore(ttl_seconds=60, clock=lambda: now[0])
    sid = store.create()
    assert store.valid(sid)
    now[0] += 61
    assert not store.valid(sid)
    assert not store.valid(None)
    assert not store.valid("")


def test_rate_limiter_window():
    now = [0.0]
    rl = RateLimiter(max_failures=2, window_seconds=10, clock=lambda: now[0])
    assert rl.allow("k")
    rl.record_failure("k")
    rl.record_failure("k")
    assert not rl.allow("k")
    now[0] += 11
    assert rl.allow("k")


# ---------- Origin ヘッダーの検査（Issue #8） ----------

def test_login_rejects_missing_origin(client):
    r = client.post("/api/login", json={"token": TOKEN})  # Origin なし
    assert r.status_code == 403
    assert "set-cookie" not in r.headers
    assert client.get("/api/session").json() == {"authenticated": False}


def test_login_allows_configured_origin(client):
    assert client.post("/api/login", json={"token": TOKEN}, headers={"origin": ORIGIN}).status_code == 204


def test_logout_rejects_missing_origin(client):
    login(client)
    assert client.post("/api/logout").status_code == 403  # Origin なし
    assert client.get("/api/session").json() == {"authenticated": True}  # セッションは残る


def test_logout_rejects_foreign_origin(client):
    login(client)
    assert client.post("/api/logout", headers={"origin": "http://evil.example"}).status_code == 403
    assert client.get("/api/session").json() == {"authenticated": True}


def test_origin_rejection_does_not_consume_rate_limit(client):
    for _ in range(10):
        assert client.post("/api/login", json={"token": "bad"}).status_code == 403
    assert login(client).status_code == 204
