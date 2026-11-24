"""実際のログを誤ってコミットしないための .gitignore の検査（Issue #14）。

`git check-ignore --no-index` で、ファイルが無くても「無視されるかどうか」をルールだけで判定する。
"""

import shutil
import subprocess

import pytest

from app.config import REPO_DIR

GIT = shutil.which("git")
pytestmark = pytest.mark.skipif(
    GIT is None or not (REPO_DIR / ".git").exists(), reason="git リポジトリ内でのみ実行"
)


def ignored(path: str) -> bool:
    res = subprocess.run(  # 固定の引数のみ（shell=False）
        [GIT, "check-ignore", "--no-index", "-q", path],
        cwd=REPO_DIR,
        capture_output=True,
        check=False,
    )
    assert res.returncode in (0, 1), res.stderr
    return res.returncode == 0


@pytest.mark.parametrize(
    "path",
    [
        "server.log",
        "backend/server.log",
        "backend/debug.log",
        "backend/data/desk.log",
        "frontend/npm-debug.log",
        "logs/app.log",
        "backend/tests/auth.log",  # fixtures 以外のテスト用ディレクトリも対象
    ],
)
def test_log_files_are_ignored(path):
    assert ignored(path), path


@pytest.mark.parametrize(
    "path",
    [
        "backend/tests/fixtures/auth.log",
        "backend/tests/fixtures/new_sample.log",
    ],
)
def test_test_fixture_logs_are_tracked(path):
    assert not ignored(path), path


def test_other_files_unaffected():
    for path in ("README.md", "backend/app/main.py", "backend/tests/fixtures/pip_audit.json"):
        assert not ignored(path), path
