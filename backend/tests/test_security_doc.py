"""SECURITY.md の「設計上の安全策」が実装と揃っていることを確認する（Issue #18）。"""

from app.config import REPO_DIR

DOC = (REPO_DIR / "SECURITY.md").read_text(encoding="utf-8")
DESIGN = DOC.split("## 設計上の安全策", 1)[1]


def bullet_with(*words: str) -> str | None:
    return next((line for line in DESIGN.splitlines() if line.startswith("- ") and all(w in line for w in words)), None)


def test_design_mentions_origin_required_on_auth_api():
    line = bullet_with("/api/login", "/api/logout", "Origin")
    assert line is not None
    assert "無い" in line  # Origin ヘッダーが無い場合も拒否することまで書く


def test_design_still_mentions_websocket_origin_check():
    assert bullet_with("WebSocket", "Origin") is not None
