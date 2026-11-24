"""`.gitleaks.toml` の例外指定が広がっていないことを確認する（Issue #10）。

本物らしい秘密情報はどのディレクトリにあっても検出され、
`fake-desk-token-` で始まる明らかな偽物だけが許可される状態を保つ。
"""

import re
import secrets
import tomllib

from app.config import REPO_DIR

CONFIG = tomllib.loads((REPO_DIR / ".gitleaks.toml").read_text(encoding="utf-8"))
ALLOW = CONFIG.get("allowlist", {})


def allowlisted(value: str) -> bool:
    return any(re.search(pattern, value) for pattern in ALLOW.get("regexes", []))


def test_no_path_or_commit_allowlist():
    # ディレクトリやコミット単位でスキャン対象外にしない
    assert not ALLOW.get("paths")
    assert not ALLOW.get("commits")


def test_fake_values_are_allowlisted():
    assert allowlisted("fake-desk-token-" + "a" * 32)
    assert allowlisted("DESK_TOKEN=fake-desk-token-example0123456789")


def test_real_looking_values_are_not_allowlisted():
    for value in (
        secrets.token_urlsafe(32),
        "DESK_TOKEN=" + secrets.token_urlsafe(32),
        "test-token-" + "z" * 40,  # 既存テストのダミーも「偽物の約束」には当たらない
        "token-desk-fake-" + "a" * 32,
    ):
        assert not allowlisted(value), value


def test_desk_token_rule_still_detects_real_tokens():
    rule = next(r for r in CONFIG["rules"] if r["id"] == "desk-token")
    assert re.search(rule["regex"], "DESK_TOKEN=" + secrets.token_urlsafe(32))
    assert re.search(rule["regex"], 'DESK_TOKEN = "' + secrets.token_urlsafe(32) + '"')
    assert not re.search(rule["regex"], "DESK_TOKEN=")  # .env.example の空欄は検出しない
